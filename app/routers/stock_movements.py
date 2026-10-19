from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Product, StockMovement
from app.schemas import ErrorResponse, StockMovementInput, StockMovementRead


router = APIRouter(prefix="/movimentacoes", tags=["Movimentacoes"])
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
        500: {"model": ErrorResponse, "description": "Erro interno no banco"},
        503: {"model": ErrorResponse, "description": "Banco indisponivel"},
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
