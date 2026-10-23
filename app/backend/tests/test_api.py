"""API tests for the Variant PDP backend.

Covers: success, validation, idempotency, and the stock race (overselling).
Run (from app/backend):  .venv/bin/python -m pytest tests -q
"""

import threading

import pytest
from fastapi.testclient import TestClient

from db import reset_db_for_tests
from main import app, reset_cart


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    # Isolate each test in its own on-disk SQLite file and clear the cart.
    reset_db_for_tests(str(tmp_path / "test.db"))
    reset_cart()
    yield


def client():
    return TestClient(app)


# ---------------------------------------------------------------- success
def test_get_product():
    r = client().get("/api/products/1")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert len(data["skus"]) == 6
    # one SKU is out of stock
    assert any(s["available_quantity"] == 0 for s in data["skus"])
    # unavailable combinations exposed
    assert any(c["colour"] == "Green" and c["size"] == "M" for c in data["unavailable_combos"])


def test_add_to_cart_success_and_get_cart():
    c = client()
    r = c.post("/api/cart/items", json={"sku_id": "ts-red-s", "quantity": 2})
    assert r.status_code == 201
    assert r.json()["quantity"] == 2

    cart = c.get("/api/cart").json()
    assert cart["total_item_count"] == 2
    assert cart["items"][0]["sku_id"] == "ts-red-s"


# ------------------------------------------------------------- validation
def test_invalid_quantity_rejected():
    r = client().post("/api/cart/items", json={"sku_id": "ts-red-s", "quantity": 0})
    assert r.status_code == 422  # pydantic rejects quantity < 1


def test_unknown_sku_404():
    r = client().post("/api/cart/items", json={"sku_id": "nope", "quantity": 1})
    assert r.status_code == 404
    assert r.json()["detail"]["error_code"] == "sku_not_found"


def test_insufficient_stock_409():
    c = client()
    # ts-red-s has 10 units; adding 11 must fail.
    r = c.post("/api/cart/items", json={"sku_id": "ts-red-s", "quantity": 11})
    assert r.status_code == 409
    assert r.json()["detail"]["error_code"] == "insufficient_stock"


# ------------------------------------------------------------ idempotency
def test_idempotency_key_prevents_double_add():
    c = client()
    body = {"sku_id": "ts-red-s", "quantity": 2, "idempotency_key": "req-1"}
    first = c.post("/api/cart/items", json=body)
    assert first.status_code == 201
    second = c.post("/api/cart/items", json=body)
    assert second.status_code == 201
    assert second.json()["duplicate"] is True
    # quantity not added twice
    assert second.json()["cart"]["total_item_count"] == 2


# ---------------------------------------------------------------- race
def test_overselling_prevented_on_final_unit():
    c = client()
    # Drain ts-red-s (10 units) down to the last 1.
    c.post("/api/cart/items", json={"sku_id": "ts-red-s", "quantity": 9})

    barrier = threading.Barrier(2)
    results: list[tuple[int, int]] = []

    def worker(idx: int) -> None:
        barrier.wait()
        cw = client()
        r = cw.post("/api/cart/items", json={
            "sku_id": "ts-red-s", "quantity": 1, "idempotency_key": f"race-{idx}"})
        results.append((idx, r.status_code))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    statuses = sorted(code for _, code in results)
    # exactly one succeeds (201), the other gets insufficient stock (409)
    assert statuses == [201, 409]
