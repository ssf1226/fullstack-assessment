import { useCallback, useEffect, useRef, useState } from "react";
import type { Cart, Product } from "../domain/types";
import { findSku, isComboDisabled } from "../domain/variant";
import { addCartItem, ApiError, fetchCart, fetchProduct } from "../api/client";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; product: Product };

type Feedback = { kind: "success" | "error"; message: string };

function friendlyError(e: unknown): string {
  if (e instanceof ApiError) {
    switch (e.errorCode) {
      case "insufficient_stock":
        return "库存不足，无法加入购物车。";
      case "sku_not_found":
        return "该商品规格不存在，请重新选择。";
      case "internal_error":
        return "服务暂时出错，请稍后重试。";
      default:
        return e.message;
    }
  }
  return "网络错误，请稍后重试。";
}

export function ProductPage() {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [colour, setColour] = useState<string>("");
  const [size, setSize] = useState<string>("");
  const [quantity, setQuantity] = useState<number>(1);
  const [cart, setCart] = useState<Cart | null>(null);
  const [adding, setAdding] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const inFlight = useRef(false);

  const loadAll = useCallback(async () => {
    setLoad({ status: "loading" });
    try {
      const [product, cartData] = await Promise.all([fetchProduct(1), fetchCart()]);
      setLoad({ status: "ready", product });
      setCart(cartData);
    } catch (e) {
      setLoad({ status: "error", message: friendlyError(e) });
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  if (load.status === "loading") {
    return <div role="status" className="page">加载中…</div>;
  }
  if (load.status === "error") {
    return (
      <div className="page">
        <p role="alert">{load.message}</p>
        <button className="btn" onClick={() => void loadAll()}>重试</button>
      </div>
    );
  }

  const { product } = load;
  const sizes = product.options.find((o) => o.name === "size")?.values ?? [];
  const colours = product.options.find((o) => o.name === "colour")?.values ?? [];
  const selComplete = colour !== "" && size !== "";
  const sku = selComplete ? findSku(product, { colour, size }) : null;
  const outOfStock = sku !== null && sku.available_quantity <= 0;
  const invalidCombo = selComplete && sku === null;
  const canAdd = selComplete && sku !== null && sku.available_quantity > 0;
  const maxQty = canAdd ? sku!.available_quantity : 0;

  async function handleAdd() {
    if (!canAdd || !sku || inFlight.current) return;
    inFlight.current = true;
    setAdding(true);
    setFeedback(null);
    try {
      const result = await addCartItem(sku.id, quantity, crypto.randomUUID());
      setCart(result.cart);
      setFeedback({ kind: "success", message: `已加入 ${quantity} 件 ${colour}/${size}` });
    } catch (e) {
      setFeedback({ kind: "error", message: friendlyError(e) });
    } finally {
      inFlight.current = false;
      setAdding(false);
    }
  }

  return (
    <div className="page pdp">
      <header className="topbar">
        <span className="brand">{product.name}</span>
        <span className="cart-count" aria-label={`购物车共 ${cart?.total_item_count ?? 0} 件`}>
          购物车 · {cart?.total_item_count ?? 0} 件
        </span>
      </header>

      <main className="layout">
        <img className="hero" src={product.image} alt={product.name} />

        <section className="info">
          <h1>{product.name}</h1>
          <p className="desc">{product.description}</p>

          {/* Colour dimension */}
          <fieldset>
            <legend>颜色</legend>
            <div className="swatches" role="group" aria-label="选择颜色">
              {colours.map((c) => {
                const disabled =
                  size !== "" && isComboDisabled(product, { colour: c, size });
                const selected = colour === c;
                return (
                  <button
                    key={c}
                    type="button"
                    className={`chip ${selected ? "chip--on" : ""}`}
                    aria-pressed={selected}
                    disabled={disabled}
                    onClick={() => { setColour(c); setQuantity(1); setFeedback(null); }}
                  >
                    {c}
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Size dimension */}
          <fieldset>
            <legend>尺码</legend>
            <div className="swatches" role="group" aria-label="选择尺码">
              {sizes.map((s) => {
                const disabled =
                  colour !== "" && isComboDisabled(product, { colour, size: s });
                const selected = size === s;
                return (
                  <button
                    key={s}
                    type="button"
                    className={`chip ${selected ? "chip--on" : ""}`}
                    aria-pressed={selected}
                    disabled={disabled}
                    onClick={() => { setSize(s); setQuantity(1); setFeedback(null); }}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          </fieldset>

          <p className="status" role="status">
            {!selComplete && "请选择颜色和尺码。"}
            {invalidCombo && "该颜色和尺码的组合不可用，请选择其他规格。"}
            {outOfStock && "该规格暂时缺货。"}
            {canAdd && (
              <>
                价格：<strong>${sku!.price.toFixed(2)}</strong> · 库存 {sku!.available_quantity} 件
              </>
            )}
          </p>

          <div className="buy">
            <label>
              数量
              <input
                type="number"
                min={1}
                max={maxQty || 1}
                value={quantity}
                disabled={!canAdd}
                aria-label="购买数量"
                onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
              />
            </label>
            <button
              className="btn btn--primary"
              disabled={!canAdd || adding}
              onClick={() => void handleAdd()}
            >
              {adding ? "加入中…" : canAdd ? "加入购物车" : "不可加入"}
            </button>
          </div>

          {feedback && (
            <p
              role={feedback.kind === "error" ? "alert" : "status"}
              className={`feedback feedback--${feedback.kind}`}
            >
              {feedback.message}
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
