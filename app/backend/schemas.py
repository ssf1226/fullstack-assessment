"""Pydantic request/response models and structured error responses.

Error responses are structured so the frontend can branch on a stable
`error_code` rather than parsing prose:
    {"error_code": "...", "message": "..."}
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AddCartItemRequest(BaseModel):
    sku_id: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=1000)
    # Idempotency key: repeating the same key must not add the item twice.
    idempotency_key: str | None = Field(None, min_length=1, max_length=128)


class CartLine(BaseModel):
    sku_id: str
    colour: str
    size: str
    price: float
    quantity: int
    line_total: float


class CartResponse(BaseModel):
    items: list[CartLine]
    total_item_count: int  # sum of quantities (units)
    total_price: float


class ApiError(BaseModel):
    error_code: str
    message: str


def http_error(status_code: int, error_code: str, message: str):
    from fastapi import HTTPException
    return HTTPException(status_code=status_code, detail={"error_code": error_code, "message": message})
