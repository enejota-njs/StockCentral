from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Supplier
from app.schemas import ErrorResponse, SupplierInput, SupplierRead


router = APIRouter(
    prefix="/fornecedores",
    tags=["Fornecedores"],
    responses={
        500: {"model": ErrorResponse, "description": "Erro interno no banco"},
        503: {"model": ErrorResponse, "description": "Banco indisponivel"},
    },
)
SessionDependency = Annotated[Session, Depends(get_session)]
SupplierId = Annotated[int, Path(gt=0, le=2147483647)]
not_found = {404: {"model": ErrorResponse, "description": "Fornecedor nao encontrado"}}
conflict = {409: {"model": ErrorResponse, "description": "Conflito com dados existentes"}}


def find_supplier(supplier_id: int, session: Session) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Fornecedor nao encontrado.")
    return supplier


def save_supplier(supplier: Supplier, session: Session) -> Supplier:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        messages = {
            "uq_fornecedores_cnpj": "Ja existe um fornecedor com esse CNPJ.",
            "uq_fornecedores_email_ci": "Ja existe um fornecedor com esse email.",
        }
        if constraint in messages:
            raise HTTPException(status_code=409, detail=messages[constraint]) from None
        raise
    session.refresh(supplier)
    return supplier


@router.post(
    "", response_model=SupplierRead, status_code=status.HTTP_201_CREATED,
    summary="Cadastrar fornecedor", responses=conflict,
)
def create_supplier(payload: SupplierInput, session: SessionDependency) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    session.add(supplier)
    return save_supplier(supplier, session)


@router.get("", response_model=list[SupplierRead], summary="Listar fornecedores")
def list_suppliers(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0, description="Quantidade de registros a pular")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Tamanho da pagina")] = 50,
) -> list[Supplier]:
    query = select(Supplier).order_by(Supplier.id).offset(offset).limit(limit)
    return list(session.scalars(query))


@router.get(
    "/{supplier_id}", response_model=SupplierRead,
    summary="Consultar fornecedor pelo ID", responses=not_found,
)
def read_supplier(supplier_id: SupplierId, session: SessionDependency) -> Supplier:
    return find_supplier(supplier_id, session)


@router.put(
    "/{supplier_id}", response_model=SupplierRead,
    summary="Atualizar fornecedor", responses={**not_found, **conflict},
)
def update_supplier(
    supplier_id: SupplierId, payload: SupplierInput, session: SessionDependency,
) -> Supplier:
    supplier = find_supplier(supplier_id, session)
    supplier.nome = payload.nome
    supplier.cnpj = payload.cnpj
    supplier.email = payload.email
    supplier.telefone = payload.telefone
    return save_supplier(supplier, session)


@router.delete(
    "/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
    summary="Excluir fornecedor", responses={**not_found, **conflict},
)
def delete_supplier(supplier_id: SupplierId, session: SessionDependency) -> Response:
    supplier = find_supplier(supplier_id, session)
    session.delete(supplier)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) in {"23001", "23503"}:
            raise HTTPException(
                status_code=409,
                detail="Fornecedor vinculado a outros registros nao pode ser excluido.",
            ) from None
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
