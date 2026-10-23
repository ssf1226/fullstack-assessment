import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ProductPage } from "../src/ui/ProductPage";
import type { AddResult, Cart } from "../src/domain/types";
import { product, emptyCart } from "./fixtures";

const addSpy = vi.fn();

vi.mock("../src/api/client", () => ({
  fetchProduct: vi.fn(async () => product),
  fetchCart: vi.fn(async () => emptyCart as Cart),
  addCartItem: (...args: unknown[]) => addSpy(...args),
  ApiError: class extends Error {
    status: number;
    errorCode: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.errorCode = code;
    }
  },
}));

async function renderPage() {
  render(<ProductPage />);
  await screen.findByRole("heading", { name: "Everyday Cotton Tee" });
}

function addResult(cart: Cart): AddResult {
  return { sku_id: "ts-red-s", quantity: 2, duplicate: false, cart };
}

describe("ProductPage", () => {
  beforeEach(() => {
    addSpy.mockReset();
  });

  it("renders product name, image and options after load", async () => {
    await renderPage();
    expect(screen.getByRole("img", { name: "Everyday Cotton Tee" })).toBeInTheDocument();
    expect(screen.getByText("Red")).toBeInTheDocument();
    expect(screen.getByText("M")).toBeInTheDocument();
  });

  it("disables buttons only for unavailable combinations", async () => {
    await renderPage();
    // pick Green: M and L have no SKU -> disabled; S exists (out of stock) -> selectable.
    fireEvent.click(screen.getByRole("button", { name: "Green" }));
    expect(screen.getByRole("button", { name: "M" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "L" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "S" })).not.toBeDisabled();
  });

  it("shows out-of-stock status and disables add-to-cart for a zero-stock SKU", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Green" }));
    fireEvent.click(screen.getByRole("button", { name: "S" }));
    expect(screen.getByText(/暂时缺货/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "不可加入" })).toBeDisabled();
  });

  it("adds to cart and shows the updated count on success", async () => {
    const cart: Cart = {
      items: [{ sku_id: "ts-red-s", colour: "Red", size: "S", price: 19.99, quantity: 2, line_total: 39.98 }],
      total_item_count: 2,
      total_price: 39.98,
    };
    addSpy.mockResolvedValue(addResult(cart));
    await renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Red" }));
    fireEvent.click(screen.getByRole("button", { name: "S" }));
    fireEvent.click(screen.getByRole("button", { name: "加入购物车" }));

    await waitFor(() => expect(screen.getByText(/购物车 · 2 件/)).toBeInTheDocument());
    expect(screen.getByText(/已加入/)).toBeInTheDocument();
  });

  it("prevents duplicate submissions on rapid repeated clicks", async () => {
    let resolveAdd: ((v: AddResult) => void) | undefined;
    addSpy.mockImplementation(
      () =>
        new Promise<AddResult>((resolve) => {
          resolveAdd = resolve;
        }),
    );
    await renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Red" }));
    fireEvent.click(screen.getByRole("button", { name: "S" }));
    const addBtn = screen.getByRole("button", { name: "加入购物车" });
    fireEvent.click(addBtn);
    fireEvent.click(addBtn);
    fireEvent.click(addBtn);

    // Only the first click should have reached the API.
    expect(addSpy).toHaveBeenCalledTimes(1);

    // Resolve so the pending promise does not leak.
    const cart: Cart = { items: [], total_item_count: 0, total_price: 0 };
    resolveAdd?.(addResult(cart));
    await waitFor(() => expect(screen.getByText(/已加入/)).toBeInTheDocument());
  });
});
