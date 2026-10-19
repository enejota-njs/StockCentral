from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Product, StockMovement
from app.schemas import ErrorResponse, StockMovementFilters, StockMovementInput, StockMovementRead


router = APIRouter(
    prefix="/movimentacoes", tags=["Movimentacoes"],
    responses={
        500: {"model": ErrorResponse, "description": "Erro interno no banco"},
        503: {"model": ErrorResponse, "description": "Banco indisponivel"},
    },
)
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post(
    "", response_model=StockMovementRead, status_code=status.HTTP_201_CREATED,
    summary="Registrar entrada ou saida de estoque",
    description=(
        "Registra a movimentacao e atualiza o saldo na mesma transacao. "
        "Fornecedor e data sao preenchidos pelo servidor. "
        "Saidas exigem saldo suficiente; entradas respeitam o limite de 2147483647 unidades."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Produto nao encontrado"},
        409: {"model": ErrorResponse, "description": "Saldo insuficiente ou limite de estoque excedido"},
    },
)
def create_stock_movement(
    payload: StockMovementInput, session: SessionDependency,
) -> StockMovementRead:
    # O contexto confirma saldo e historico juntos; qualquer excecao desfaz ambos.
    with session.begin():
        # Serializa as movimentacoes do mesmo produto ate o fim da transacao.
        product = session.scalar(
            select(Product).where(Product.id == payload.produto_id).with_for_update()
        )
        if product is None:
            raise HTTPException(status_code=404, detail="Produto nao encontrado.")

        balance = product.quantidade_em_estoque
        if payload.tipo == "saida":
            if payload.quantidade > balance:
                raise HTTPException(status_code=409, detail="Estoque insuficiente para essa saida.")
            balance -= payload.quantidade
        else:
            balance += payload.quantidade
            if balance > 2147483647:
                raise HTTPException(status_code=409, detail="Limite de quantidade em estoque excedido.")

        product.quantidade_em_estoque = balance
        movement = StockMovement(
            produto_id=product.id,
            fornecedor_id=product.fornecedor_id,
            tipo=payload.tipo,
            quantidade=payload.quantidade,
        )
        session.add(movement)
        session.flush()
        # Captura os campos gerados pelo banco antes de encerrar a transacao.
        result = StockMovementRead.model_validate(movement)
    return result


@router.get(
    "", response_model=list[StockMovementRead], summary="Consultar historico de movimentacoes",
    description=(
        "Combina filtros por produto, fornecedor historico, tipo e periodo. "
        "As datas incluem os limites e devem informar fuso horario. "
        "Ordena por data decrescente, com desempate pelo ID decrescente, antes de paginar. "
        "Sem resultados retorna uma lista vazia."
    ),
)
def list_stock_movements(
    filters: Annotated[StockMovementFilters, Query()], session: SessionDependency,
) -> list[StockMovement]:
    query = select(StockMovement)
    if filters.produto_id is not None:
        query = query.where(StockMovement.produto_id == filters.produto_id)
    if filters.fornecedor_id is not None:
        query = query.where(StockMovement.fornecedor_id == filters.fornecedor_id)
    if filters.tipo is not None:
        query = query.where(StockMovement.tipo == filters.tipo)
    if filters.data_inicio is not None:
        query = query.where(StockMovement.data >= filters.data_inicio)
    if filters.data_fim is not None:
        query = query.where(StockMovement.data <= filters.data_fim)
    query = query.order_by(StockMovement.data.desc(), StockMovement.id.desc())
    return list(session.scalars(query.offset(filters.offset).limit(filters.limit)))


@router.get(
    "/{movement_id}", response_model=StockMovementRead,
    summary="Consultar movimentacao pelo ID",
    responses={404: {"model": ErrorResponse, "description": "Movimentacao nao encontrada"}},
)
def read_stock_movement(
    movement_id: Annotated[int, Path(gt=0, le=2147483647)], session: SessionDependency,
) -> StockMovement:
    movement = session.get(StockMovement, movement_id)
    if movement is None:
        raise HTTPException(status_code=404, detail="Movimentacao nao encontrada.")
    return movement
