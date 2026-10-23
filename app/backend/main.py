"""Variant PDP backend — FastAPI.

Endpoints:
  GET  /api/products/{id}  -> product, options and SKU data
  POST /api/cart/items     -> add a SKU + quantity to the cart (idempotency-key)
  GET  /api/cart           -> current cart and total item count

Server-side rules:
  * SKU existence, quantity and current stock are validated on the server.
    Price/stock sent by the client is never trusted (the client sends only
    sku_id + quantity).
  * add-to-cart accepts an idempotency-key; a repeated key does not add twice.
  * Structured error responses for invalid input, insufficient stock and
    unexpected failures.
  * Overselling is prevented by an atomic check-and-decrement (see db.py).

Run:  uvicorn main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from db import get_db, UNAVAILABLE_COMBOS
from schemas import AddCartItemRequest, CartResponse, CartLine, http_error

app = FastAPI(title="Variant PDP API", version="1.0.0")

# Cart is in-memory (no auth/session in scope): sku_id -> quantity.
_cart: dict[str, int] = {}


def reset_cart() -> None:
    """Clear the in-memory cart (used by tests for isolation)."""
    _cart.clear()


def _cart_line(sku_id: str, quantity: int) -> CartLine:
    db = get_db()
    product = db.get_product(1)
    sku = next((s for s in product["skus"] if s["id"] == sku_id), None)
    assert sku is not None, "cart item should reference an existing sku"
    return CartLine(
        sku_id=sku_id,
        colour=sku["colour"],
        size=sku["size"],
        price=sku["price"],
        quantity=quantity,
        line_total=round(sku["price"] * quantity, 2),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    db = get_db()
    product = db.get_product(product_id)
    if product is None:
        raise http_error(404, "product_not_found", "Product not found")
    product["unavailable_combos"] = [
        {"colour": c, "size": s} for (c, s) in sorted(UNAVAILABLE_COMBOS)
    ]
    return product


@app.post("/api/cart/items", status_code=201)
def add_cart_item(body: AddCartItemRequest):
    db = get_db()
    sku_id = body.sku_id
    quantity = body.quantity
    key = body.idempotency_key

    # ---- idempotency: a repeated key returns the existing result, no re-add ----
    if key is not None:
        existing = db.get_key(key)
        if existing is not None:
            prev_sku, prev_qty = existing
            return {"sku_id": prev_sku, "quantity": prev_qty, "duplicate": True,
                    "cart": _current_cart()}

    if not db.sku_exists(sku_id):
        raise http_error(404, "sku_not_found", "SKU does not exist")

    if not db.reserve_stock(sku_id, quantity):
        raise http_error(409, "insufficient_stock", "Insufficient stock for this SKU")

    # Only remember the idempotency key after a successful, committed reserve.
    if key is not None:
        db.remember_key(key, sku_id, quantity)

    _cart[sku_id] = _cart.get(sku_id, 0) + quantity
    return {"sku_id": sku_id, "quantity": quantity, "duplicate": False,
            "cart": _current_cart()}


@app.get("/api/cart")
def get_cart() -> CartResponse:
    return _current_cart()


def _current_cart() -> CartResponse:
    lines = []
    total_units = 0
    total_price = 0.0
    for sku_id, quantity in _cart.items():
        line = _cart_line(sku_id, quantity)
        lines.append(line)
        total_units += line.quantity
        total_price += line.line_total
    return CartResponse(items=lines, total_item_count=total_units,
                        total_price=round(total_price, 2))


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    # Structured fallback so unexpected failures are still JSON, not HTML.
    return http_error(500, "internal_error", "Unexpected server error")
