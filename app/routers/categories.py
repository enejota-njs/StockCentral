from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Category
from app.schemas import CategoryInput, CategoryRead, ErrorResponse


router = APIRouter(
    prefix="/categorias",
    tags=["Categorias"],
    responses={
        500: {"model": ErrorResponse, "description": "Erro interno no banco"},
        503: {"model": ErrorResponse, "description": "Banco indisponivel"},
    },
)
SessionDependency = Annotated[Session, Depends(get_session)]
CategoryId = Annotated[int, Path(gt=0)]
not_found = {404: {"model": ErrorResponse, "description": "Categoria nao encontrada"}}
conflict = {409: {"model": ErrorResponse, "description": "Conflito com dados existentes"}}


def find_category(category_id: int, session: Session) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Categoria nao encontrada.")
    return category


def save_category(category: Category, session: Session) -> Category:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_categorias_nome_ci":
            raise HTTPException(
                status_code=409,
                detail="Ja existe uma categoria com esse nome.",
            ) from None
        raise
    session.refresh(category)
    return category


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar categoria",
    responses=conflict,
)
def create_category(payload: CategoryInput, session: SessionDependency) -> Category:
    category = Category(nome=payload.nome)
    session.add(category)
    return save_category(category, session)


@router.get("", response_model=list[CategoryRead], summary="Listar categorias")
def list_categories(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0, description="Quantidade de registros a pular")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Tamanho da pagina")] = 50,
) -> list[Category]:
    query = select(Category).order_by(Category.id).offset(offset).limit(limit)
    return list(session.scalars(query))


@router.get(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Consultar categoria pelo ID",
    responses=not_found,
)
def read_category(category_id: CategoryId, session: SessionDependency) -> Category:
    return find_category(category_id, session)


@router.put(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Atualizar categoria",
    responses={**not_found, **conflict},
)
def update_category(
    category_id: CategoryId,
    payload: CategoryInput,
    session: SessionDependency,
) -> Category:
    category = find_category(category_id, session)
    category.nome = payload.nome
    return save_category(category, session)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Excluir categoria",
    responses={**not_found, **conflict},
)
def delete_category(category_id: CategoryId, session: SessionDependency) -> Response:
    category = find_category(category_id, session)
    session.delete(category)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23503":
            raise HTTPException(
                status_code=409,
                detail="Categoria vinculada a outros registros nao pode ser excluida.",
            ) from None
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
