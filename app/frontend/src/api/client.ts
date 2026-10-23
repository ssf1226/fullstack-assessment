// API layer — the only place that talks to the backend. UI never touches
// fetch directly, so the domain stays testable.

import type { AddResult, Cart, Product } from "../domain/types";

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  (typeof window !== "undefined" ? "" : "http://localhost:8000");

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  constructor(status: number, errorCode: string, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function parse<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const code =
      body?.detail?.error_code ?? body?.error_code ?? "unknown_error";
    const message = body?.detail?.message ?? body?.message ?? `HTTP ${res.status}`;
    throw new ApiError(res.status, code, message);
  }
  return body as T;
}

export async function fetchProduct(id = 1): Promise<Product> {
  const res = await fetch(`${API_BASE}/api/products/${id}`);
  return parse<Product>(res);
}

export async function addCartItem(
  skuId: string,
  quantity: number,
  idempotencyKey: string,
): Promise<AddResult> {
  const res = await fetch(`${API_BASE}/api/cart/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sku_id: skuId, quantity, idempotency_key: idempotencyKey }),
  });
  return parse<AddResult>(res);
}

export async function fetchCart(): Promise<Cart> {
  const res = await fetch(`${API_BASE}/api/cart`);
  return parse<Cart>(res);
}
