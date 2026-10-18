from typing import Annotated

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
