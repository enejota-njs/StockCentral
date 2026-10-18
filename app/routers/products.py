from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Product
from app.schemas import ErrorResponse, ProductInput, ProductRead


router = APIRouter(
    prefix="/produtos", tags=["Produtos"],
    responses={
        500: {"model": ErrorResponse, "description": "Erro interno no banco"},
        503: {"model": ErrorResponse, "description": "Banco indisponivel"},
    },
)
SessionDependency = Annotated[Session, Depends(get_session)]
ProductId = Annotated[int, Path(gt=0, le=2147483647)]
FilterId = Annotated[int | None, Query(gt=0, le=2147483647)]
not_found = {404: {"model": ErrorResponse, "description": "Produto nao encontrado"}}
conflict = {409: {"model": ErrorResponse, "description": "Conflito com dados existentes"}}
invalid_reference = {
    422: {
        "description": "Dados invalidos ou categoria/fornecedor inexistente",
        "content": {"application/json": {
            "schema": {
                "type": "object", "required": ["detail"],
                "properties": {"detail": {"oneOf": [
                    {"type": "string"}, {"type": "array", "items": {"type": "object"}},
                ]}},
            },
            "examples": {
                "categoria_inexistente": {"value": {"detail": "Categoria informada nao existe."}},
                "fornecedor_inexistente": {"value": {"detail": "Fornecedor informado nao existe."}},
                "campo_ausente": {"value": {"detail": [
                    {"type": "missing", "loc": ["body", "nome"], "msg": "Field required", "input": {}},
                ]}},
            },
        }},
    },
}


def find_product(product_id: int, session: Session) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado.")
    return product


def save_product(product: Product, session: Session) -> Product:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        # As FKs validam tambem se o cadastro foi excluido por outra requisicao.
        errors = {
            "uq_produtos_sku": (409, "Ja existe um produto com esse SKU."),
            "fk_produtos_categoria_id_categorias": (422, "Categoria informada nao existe."),
            "fk_produtos_fornecedor_id_fornecedores": (422, "Fornecedor informado nao existe."),
        }
        if constraint in errors:
            code, message = errors[constraint]
            raise HTTPException(status_code=code, detail=message) from None
        raise
    session.refresh(product)
    return product


@router.post(
    "", response_model=ProductRead, status_code=status.HTTP_201_CREATED,
    summary="Cadastrar produto com saldo inicial zero",
    responses={**conflict, **invalid_reference},
)
def create_product(payload: ProductInput, session: SessionDependency) -> Product:
    product = Product(**payload.model_dump())
    session.add(product)
    return save_product(product, session)


@router.get("", response_model=list[ProductRead], summary="Listar e filtrar produtos")
def list_products(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    categoria_id: FilterId = None,
    fornecedor_id: FilterId = None,
    estoque_baixo: Annotated[bool | None, Query(
        description="true: saldo <= minimo; false: saldo > minimo; omitido: todos."
    )] = None,
) -> list[Product]:
    query = select(Product)
    if categoria_id is not None:
        query = query.where(Product.categoria_id == categoria_id)
    if fornecedor_id is not None:
        query = query.where(Product.fornecedor_id == fornecedor_id)
    if estoque_baixo is True:
        query = query.where(Product.quantidade_em_estoque <= Product.estoque_minimo)
    elif estoque_baixo is False:
        query = query.where(Product.quantidade_em_estoque > Product.estoque_minimo)
    return list(session.scalars(query.order_by(Product.id).offset(offset).limit(limit)))


@router.get(
    "/{product_id}", response_model=ProductRead,
    summary="Consultar produto pelo ID", responses=not_found,
)
def read_product(product_id: ProductId, session: SessionDependency) -> Product:
    return find_product(product_id, session)


@router.put(
    "/{product_id}", response_model=ProductRead,
    summary="Atualizar cadastro do produto sem alterar o saldo",
    responses={**not_found, **conflict, **invalid_reference},
)
def update_product(
    product_id: ProductId, payload: ProductInput, session: SessionDependency,
) -> Product:
    product = find_product(product_id, session)
    product.nome = payload.nome
    product.sku = payload.sku
    product.preco_custo = payload.preco_custo
    product.preco_venda = payload.preco_venda
    product.estoque_minimo = payload.estoque_minimo
    product.categoria_id = payload.categoria_id
    product.fornecedor_id = payload.fornecedor_id
    return save_product(product, session)


@router.delete(
    "/{product_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
    summary="Excluir produto", responses={**not_found, **conflict},
)
def delete_product(product_id: ProductId, session: SessionDependency) -> Response:
    product = find_product(product_id, session)
    session.delete(product)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) in {"23001", "23503"}:
            raise HTTPException(
                status_code=409,
                detail="Produto vinculado a outros registros nao pode ser excluido.",
            ) from None
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
