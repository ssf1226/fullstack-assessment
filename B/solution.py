"""Task B - Fulfilment Split Optimiser

An order of exactly Q units may be fulfilled from multiple warehouses. Choose
an allocation that satisfies the requested quantity while optimising business
priorities, in this order:

  1. Minimise the number of warehouses used (a warehouse is "used" when it is
     allocated more than zero units).
  2. Then minimise total shipping cost:
         sum over used warehouses of (fixed_cost + allocated_qty * unit_cost).
  3. Then choose the lexicographically smallest allocation list when sorted
     by warehouse_id.

Constraints: W <= 20, Q <= 2000, 0 <= stock <= 2000, non-negative costs.
sum(stock) may be less than Q (then the order cannot be fulfilled: print -1).
No external solver libraries are used; only the standard library.

Approach (DP, no subset brute-force):
  dp[q] holds the best triple (warehouses_used, total_cost, allocation) for
  producing exactly q units using the warehouses processed so far. Because the
  comparison is done on the tuple (warehouses, cost, allocation) the natural
  Python tuple ordering implements the three-level objective exactly. Warehouses
  are consumed with 0/1 semantics (each used at most once) by iterating q in
  reverse. The allocation is kept sorted by warehouse_id, so its lexicographic
  comparison matches the specification.

Complexity: O(W * Q * avg_stock) time, O(Q * W) space for the allocation
backpointers (bounded by 2000 * 20). This comfortably handles W=20, Q=2000.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Warehouse:
    wid: str
    stock: int
    fixed: int
    unit: int


def solve(header: str, rows: list[str]) -> list[str]:
    w_part, q_part = header.split()
    w = int(w_part)
    q = int(q_part)
    if not (1 <= w <= 20):
        raise ValueError("W out of range")
    if not (1 <= q <= 2000):
        raise ValueError("Q out of range")
    if len(rows) != w:
        raise ValueError(f"expected {w} warehouse rows, got {len(rows)}")

    warehouses: list[Warehouse] = []
    for row in rows:
        parts = row.split()
        if len(parts) != 4:
            raise ValueError(f"malformed warehouse row: {row}")
        wid, stock_s, fixed_s, unit_s = parts
        stock = int(stock_s)
        fixed = int(fixed_s)
        unit = int(unit_s)
        if stock < 0 or fixed < 0 or unit < 0:
            raise ValueError("costs/stock must be non-negative")
        warehouses.append(Warehouse(wid, stock, fixed, unit))

    total_stock = sum(wh.stock for wh in warehouses)
    if total_stock < q:
        return ["-1"]

    # Skip warehouses with zero stock (they can never be "used").
    usable = [wh for wh in warehouses if wh.stock > 0]
    if not usable:
        return ["-1"]

    # State: best (warehouses_used, total_cost, allocation) to reach `q` units.
    # allocation is a tuple of (warehouse_id, qty) sorted by warehouse_id.
    INF = (float("inf"), float("inf"), None)
    dp = [INF] * (q + 1)
    dp[0] = (0, 0, ())

    for wh in usable:
        # Reverse iteration gives 0/1 semantics: each warehouse used at most once.
        for cur in range(q, -1, -1):
            if dp[cur][0] == float("inf"):
                continue
            max_alloc = min(wh.stock, q - cur)
            if max_alloc <= 0:
                continue
            best_for_cur = dp[cur]
            for a in range(1, max_alloc + 1):
                nxt = cur + a
                if nxt > q:
                    continue
                prev = dp[cur]
                new_k = prev[0] + 1
                new_cost = prev[1] + wh.fixed + a * wh.unit
                # allocation: insert (wh.wid, a) then keep sorted by id
                alloc = list(prev[2])
                # insertion sort into id-sorted list (ids are unique in a solution)
                item = (wh.wid, a)
                j = len(alloc)
                alloc.append(item)
                # sort by warehouse_id
                alloc.sort(key=lambda t: t[0])
                alloc_t = tuple(alloc)
                candidate = (new_k, new_cost, alloc_t)
                if candidate < dp[nxt]:
                    dp[nxt] = candidate

    if dp[q][0] == float("inf"):
        return ["-1"]

    k, cost, alloc = dp[q]
    out = [f"{k} {cost}"]
    out.extend(f"{wid} {qty}" for wid, qty in alloc)  # already sorted by id
    return out


def main() -> None:
    data = sys.stdin.read().splitlines()
    if not data:
        return
    header = data[0]
    rows = data[1:]
    try:
        for line in solve(header, rows):
            print(line)
    except ValueError as exc:
        print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
