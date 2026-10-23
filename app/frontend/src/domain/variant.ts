// Pure variant-resolution logic, kept free of React/UI so it is directly
// unit-testable. Given a selection of option values, resolve the concrete SKU
// and whether the combination is selectable.

import type { Product, Sku } from "./types";

export interface Selection {
  colour: string;
  size: string;
}

/** Resolve the concrete SKU for a selection, or null if none exists. */
export function findSku(product: Product, sel: Selection): Sku | null {
  return (
    product.skus.find((s) => s.colour === sel.colour && s.size === sel.size) ??
    null
  );
}

/** A combination is unavailable when no SKU exists for it. */
export function hasNoSku(product: Product, sel: Selection): boolean {
  return findSku(product, sel) === null;
}

/** A combination is out of stock when a SKU exists but has zero availability. */
export function isOutOfStock(product: Product, sel: Selection): boolean {
  const sku = findSku(product, sel);
  return sku !== null && sku.available_quantity <= 0;
}

/**
 * Whether a button for this combination should be disabled (i.e. cannot be
 * selected). Only combinations with NO SKU are disabled. Out-of-stock SKUs are
 * left selectable so the buyer can see the "out of stock" status (add-to-cart
 * is disabled separately when the resolved SKU has zero availability).
 */
export function isComboDisabled(product: Product, sel: Selection): boolean {
  return hasNoSku(product, sel);
}

/** Max quantity the buyer may add for the resolved SKU (1..available stock). */
export function maxQuantity(product: Product, sel: Selection): number {
  const sku = findSku(product, sel);
  return sku ? sku.available_quantity : 0;
}
