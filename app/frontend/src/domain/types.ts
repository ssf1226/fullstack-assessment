// Domain types for the Variant PDP — mirror the backend contract.

export interface Sku {
  id: string;
  price: number;
  available_quantity: number;
  image: string;
  colour: string;
  size: string;
}

export interface OptionDimension {
  name: string;
  values: string[];
}

export interface UnavailableCombo {
  colour: string;
  size: string;
}

export interface Product {
  id: number;
  name: string;
  description: string;
  image: string;
  options: OptionDimension[];
  skus: Sku[];
  unavailable_combos: UnavailableCombo[];
}

export interface CartLine {
  sku_id: string;
  colour: string;
  size: string;
  price: number;
  quantity: number;
  line_total: number;
}

export interface Cart {
  items: CartLine[];
  total_item_count: number;
  total_price: number;
}

export interface AddResult {
  sku_id: string;
  quantity: number;
  duplicate: boolean;
  cart: Cart;
}
