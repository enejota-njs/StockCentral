from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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
