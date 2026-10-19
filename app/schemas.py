from typing import Annotated, Literal
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.validators import validate_cnpj, validate_phone


CategoryName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: CategoryName = Field(examples=["Eletrônicos"])


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class ErrorResponse(BaseModel):
    detail: str


class SupplierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    cnpj: Annotated[str, StringConstraints(strip_whitespace=True, min_length=14, max_length=18)] = Field(
        examples=["12.ABC.345/01DE-35"],
        description="CNPJ numerico ou alfanumerico, com ou sem mascara; digitos verificadores validos.",
    )
    email: EmailStr = Field(max_length=254, examples=["contato@example.com"])
    telefone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=30)] = Field(
        examples=["(75) 99999-1234"],
        description="De 8 a 15 digitos; aceita + inicial, espacos, parenteses, ponto e hifen.",
    )

    @field_validator("cnpj")
    @classmethod
    def check_cnpj(cls, value: str) -> str:
        return validate_cnpj(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Regra do sistema: emails nao diferenciam maiusculas de minusculas.
        return value.lower()

    @field_validator("telefone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return validate_phone(value)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str
    email: str
    telefone: str


Money = Annotated[
    Decimal, Field(ge=0, le=Decimal("9999999999.99"), max_digits=12, decimal_places=2)
]
ReferenceId = Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    sku: Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )] = Field(examples=["CANETA-001"])
    preco_custo: Money = Field(examples=["2.50"])
    preco_venda: Money = Field(examples=["4.90"])
    estoque_minimo: Annotated[int, Field(strict=True, ge=0, le=2147483647)] = Field(
        description="Limite para identificar produtos que precisam de reposicao."
    )
    categoria_id: ReferenceId
    fornecedor_id: ReferenceId

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.upper()


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    sku: str
    preco_custo: Decimal
    preco_venda: Decimal
    quantidade_em_estoque: int
    estoque_minimo: int
    data_cadastro: datetime
    categoria_id: int
    fornecedor_id: int


class StockMovementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_id: ReferenceId = Field(examples=[1])
    tipo: Literal["entrada", "saida"]
    quantidade: Annotated[int, Field(strict=True, gt=0, le=2147483647)] = Field(examples=[5])


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: int
    fornecedor_id: int
    tipo: Literal["entrada", "saida"]
    quantidade: int
    data: datetime
