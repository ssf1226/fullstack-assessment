import { describe, it, expect } from "vitest";
import { findSku, isComboDisabled, isOutOfStock, maxQuantity } from "../src/domain/variant";
import { product } from "./fixtures";

describe("variant resolution", () => {
  it("resolves the concrete SKU for a valid selection", () => {
    const sku = findSku(product, { colour: "Red", size: "S" });
    expect(sku?.id).toBe("ts-red-s");
    expect(sku?.price).toBe(19.99);
  });

  it("returns null for a combination with no SKU (unavailable combo)", () => {
    expect(findSku(product, { colour: "Green", size: "M" })).toBeNull();
  });

  it("flags out-of-stock combinations", () => {
    expect(isOutOfStock(product, { colour: "Green", size: "S" })).toBe(true);
    expect(isOutOfStock(product, { colour: "Red", size: "S" })).toBe(false);
  });

  it("disables only unavailable combos; out-of-stock stays selectable", () => {
    // Green-M has no SKU -> disabled.
    expect(isComboDisabled(product, { colour: "Green", size: "M" })).toBe(true);
    // Green-S has a SKU but is out of stock -> NOT disabled (selectable to see status).
    expect(isComboDisabled(product, { colour: "Green", size: "S" })).toBe(false);
    expect(isComboDisabled(product, { colour: "Red", size: "S" })).toBe(false);
  });

  it("caps quantity at available stock", () => {
    expect(maxQuantity(product, { colour: "Red", size: "S" })).toBe(10);
    expect(maxQuantity(product, { colour: "Green", size: "S" })).toBe(0);
  });
});
