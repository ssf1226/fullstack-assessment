"""Task A - Inventory Reservation Ledger

Deterministic command processor for a single SKU.

The system tracks three pieces of state:
  - on_hand          : physically available units on the shelf
  - reserved_by_order: units reserved per order_id
  - processed        : set of event_ids already seen (idempotency)

Available stock is defined as:  on_hand - sum(reserved_by_order.values())

Commands (one per line, after the "S N" header):
  RESERVE event_id order_id qty
  RELEASE event_id order_id qty
  SHIP    event_id order_id qty
  RESET   event_id qty

Behaviour rules (from the assessment):
  * All quantities are positive integers. Malformed input is rejected with
    no partial state change.
  * RESERVE succeeds only when enough stock is available.
  * RELEASE / SHIP cannot exceed the quantity currently reserved for that order.
  * SHIP reduces both on_hand and that order's reserved quantity.
  * Every event_id is idempotent: replaying an already processed event returns
    DUPLICATE and must not change state.
  * A rejected business operation is still considered processed (so replaying it
    returns DUPLICATE).

Output, for every command:
  OK | REJECTED | DUPLICATE <on_hand> <total_reserved>
and after all commands a line listing open reservations ordered by order_id.

The processor is O(N) in the number of commands (dict/set lookups are O(1)).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass
class Ledger:
    """State for a single SKU."""
    on_hand: int
    reserved_by_order: dict[str, int] = field(default_factory=dict)
    processed: set[str] = field(default_factory=set)

    def total_reserved(self) -> int:
        return sum(self.reserved_by_order.values())

    def available(self) -> int:
        return self.on_hand - self.total_reserved()

    def reserved_for(self, order_id: str) -> int:
        return self.reserved_by_order.get(order_id, 0)


def process_command(ledger: Ledger, tokens: list[str]) -> str:
    """Apply a single command; returns the output line for it.

    Malformed or unknown commands are rejected with REJECTED and no state
    change. A well-formed command that is refused on business grounds (e.g.
    insufficient stock) is also REJECTED but still counts as processed for
    idempotency, per the assessment.
    """
    if not tokens:
        return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"
    verb = tokens[0].upper()
    event_id = tokens[1] if len(tokens) > 1 else None

    # ---- idempotency gate: replaying a processed event changes nothing ----
    if event_id is not None and event_id in ledger.processed:
        return f"DUPLICATE {ledger.on_hand} {ledger.total_reserved()}"

    def mark() -> None:
        # A processed event (success OR business rejection) is remembered.
        ledger.processed.add(event_id)

    if verb == "RESERVE":
        if len(tokens) != 4 or not _positive(tokens[3]):
            return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"
        _, eid, order_id, qty_s = tokens
        qty = int(qty_s)
        if ledger.available() >= qty:
            ledger.reserved_by_order[order_id] = ledger.reserved_for(order_id) + qty
            mark()
            return f"OK {ledger.on_hand} {ledger.total_reserved()}"
        mark()  # rejected business op still counts as processed
        return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"

    if verb == "RELEASE":
        if len(tokens) != 4 or not _positive(tokens[3]):
            return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"
        _, eid, order_id, qty_s = tokens
        qty = int(qty_s)
        if ledger.reserved_for(order_id) >= qty:
            ledger.reserved_by_order[order_id] = ledger.reserved_for(order_id) - qty
            if ledger.reserved_by_order[order_id] == 0:
                del ledger.reserved_by_order[order_id]
            mark()
            return f"OK {ledger.on_hand} {ledger.total_reserved()}"
        mark()
        return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"

    if verb == "SHIP":
        if len(tokens) != 4 or not _positive(tokens[3]):
            return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"
        _, eid, order_id, qty_s = tokens
        qty = int(qty_s)
        if ledger.reserved_for(order_id) >= qty:
            ledger.on_hand -= qty
            ledger.reserved_by_order[order_id] = ledger.reserved_for(order_id) - qty
            if ledger.reserved_by_order[order_id] == 0:
                del ledger.reserved_by_order[order_id]
            mark()
            return f"OK {ledger.on_hand} {ledger.total_reserved()}"
        mark()
        return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"

    if verb == "RESET":
        if len(tokens) != 3 or not _nonnegative(tokens[2]):
            return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"
        _, eid, qty_s = tokens
        qty = int(qty_s)
        # Assumption: RESET recalibrates the physical stock level to `qty`,
        # e.g. after a stocktake. Existing per-order reservations are kept so
        # that "available = on_hand - reserved" remains consistent.
        ledger.on_hand = qty
        mark()
        return f"OK {ledger.on_hand} {ledger.total_reserved()}"

    return f"REJECTED {ledger.on_hand} {ledger.total_reserved()}"


def _positive(text: str) -> bool:
    try:
        return int(text) > 0
    except ValueError:
        return False


def _nonnegative(text: str) -> bool:
    try:
        return int(text) >= 0
    except ValueError:
        return False


def run(header: str, commands: list[str]) -> list[str]:
    """Execute the full input and return the output lines."""
    s_part, n_part = header.split()
    s = int(s_part)
    n = int(n_part)
    if s < 0:
        raise ValueError("initial stock must be non-negative")
    if not (1 <= n <= 200_000):
        raise ValueError("command count out of range")
    if len(commands) != n:
        raise ValueError(f"expected {n} commands, got {len(commands)}")

    ledger = Ledger(on_hand=s)
    output: list[str] = []
    for line in commands:
        # process_command returns a status line for every input (malformed or
        # unknown commands are REJECTED without any state change), so nothing
        # here can raise.
        output.append(process_command(ledger, line.split()))
    open_ids = sorted(ledger.reserved_by_order.keys())
    if open_ids:
        output.append("OPEN RESERVATIONS: " + " ".join(open_ids))
    return output


def main() -> None:
    data = sys.stdin.read().splitlines()
    if not data:
        return
    header = data[0]
    commands = data[1:]
    try:
        for line in run(header, commands):
            print(line)
    except ValueError as exc:
        print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
