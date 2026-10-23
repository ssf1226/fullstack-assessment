import type { Product } from "../src/domain/types";

/** Shared fixture: 6 SKUs with one unavailable combo (Green-M) and one
 *  out-of-stock SKU (Green-S), mirroring the backend seed. */
export const product: Product = {
  id: 1,
  name: "Everyday Cotton Tee",
  description: "A soft cotton tee.",
  image: "img.jpg",
  options: [
    { name: "colour", values: ["Red", "Blue", "Green"] },
    { name: "size", values: ["S", "M", "L"] },
  ],
  skus: [
    { id: "ts-red-s", price: 19.99, available_quantity: 10, image: "", colour: "Red", size: "S" },
    { id: "ts-red-m", price: 19.99, available_quantity: 8, image: "", colour: "Red", size: "M" },
    { id: "ts-red-l", price: 21.99, available_quantity: 5, image: "", colour: "Red", size: "L" },
    { id: "ts-blue-s", price: 19.99, available_quantity: 6, image: "", colour: "Blue", size: "S" },
    { id: "ts-blue-m", price: 20.99, available_quantity: 4, image: "", colour: "Blue", size: "M" },
    { id: "ts-green-s", price: 19.99, available_quantity: 0, image: "", colour: "Green", size: "S" },
  ],
  unavailable_combos: [
    { colour: "Green", size: "M" },
    { colour: "Green", size: "L" },
    { colour: "Blue", size: "L" },
  ],
};

export const emptyCart = { items: [], total_item_count: 0, total_price: 0 };
