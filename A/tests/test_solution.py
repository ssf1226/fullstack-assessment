"""Unit tests for Task A - Inventory Reservation Ledger.

Run:  python3 -m unittest discover -s tests  (from the A/ directory)
"""

import unittest

from solution import Ledger, run, process_command


class TestReserve(unittest.TestCase):
    def test_reserve_succeeds_when_enough_stock(self):
        ledger = Ledger(on_hand=10)
        out = process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        self.assertEqual(out, "OK 10 4")

    def test_reserve_rejected_when_not_enough_stock(self):
        ledger = Ledger(on_hand=10)
        out = process_command(ledger, ["RESERVE", "e1", "o1", "100"])
        self.assertEqual(out, "REJECTED 10 0")

    def test_reserve_uses_available_not_on_hand(self):
        # reserved 4, available is 6, so reserving 6 is fine but 7 is not.
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        self.assertEqual(process_command(ledger, ["RESERVE", "e2", "o2", "6"]), "OK 10 10")
        self.assertEqual(process_command(ledger, ["RESERVE", "e3", "o3", "1"]), "REJECTED 10 10")


class TestRelease(unittest.TestCase):
    def test_release_frees_reservation(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        out = process_command(ledger, ["RELEASE", "e2", "o1", "4"])
        self.assertEqual(out, "OK 10 0")

    def test_release_cannot_exceed_reserved(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        out = process_command(ledger, ["RELEASE", "e2", "o1", "5"])
        self.assertEqual(out, "REJECTED 10 4")


class TestShip(unittest.TestCase):
    def test_ship_reduces_on_hand_and_reserved(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        out = process_command(ledger, ["SHIP", "e2", "o1", "2"])
        self.assertEqual(out, "OK 8 2")
        self.assertEqual(ledger.on_hand, 8)

    def test_ship_cannot_exceed_reserved(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "2"])
        out = process_command(ledger, ["SHIP", "e2", "o1", "3"])
        self.assertEqual(out, "REJECTED 10 2")


class TestIdempotency(unittest.TestCase):
    def test_replay_returns_duplicate(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        out = process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        self.assertEqual(out, "DUPLICATE 10 4")

    def test_rejected_op_still_counts_as_processed(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "100"])  # rejected
        out = process_command(ledger, ["RESERVE", "e1", "o1", "100"])
        self.assertEqual(out, "DUPLICATE 10 0")


class TestReset(unittest.TestCase):
    def test_reset_recalibrates_on_hand_keeps_reservations(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        out = process_command(ledger, ["RESET", "e2", "20"])
        self.assertEqual(out, "OK 20 4")  # stock corrected, reservation kept
        self.assertEqual(ledger.available(), 16)

    def test_reset_is_idempotent(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESET", "e1", "5"])
        out = process_command(ledger, ["RESET", "e1", "5"])
        self.assertEqual(out, "DUPLICATE 5 0")


class TestMalformed(unittest.TestCase):
    def test_malformed_rejected_without_state_change(self):
        ledger = Ledger(on_hand=10)
        process_command(ledger, ["RESERVE", "e1", "o1", "4"])
        out = process_command(ledger, ["RESERVE", "e2", "o1"])  # missing qty
        self.assertEqual(out, "REJECTED 10 4")
        self.assertEqual(ledger.total_reserved(), 4)

    def test_negative_qty_rejected(self):
        ledger = Ledger(on_hand=10)
        out = process_command(ledger, ["RESERVE", "e1", "o1", "-5"])
        self.assertEqual(out, "REJECTED 10 0")

    def test_unknown_command_rejected(self):
        ledger = Ledger(on_hand=10)
        out = process_command(ledger, ["FROB", "e1", "o1", "5"])
        self.assertEqual(out, "REJECTED 10 0")


class TestFullExample(unittest.TestCase):
    def test_assessment_style_example(self):
        header = "10 6"
        commands = [
            "RESERVE e1 o1 4",
            "RESERVE e2 o2 2",
            "SHIP e3 o1 2",
            "RELEASE e4 o1 2",
            "RESERVE e5 o2 9",
            "RESERVE e1 o1 1",  # idempotency demo
        ]
        output = run(header, commands)
        self.assertEqual(output, [
            "OK 10 4",
            "OK 10 6",
            "OK 8 4",
            "OK 8 2",
            "REJECTED 8 2",
            "DUPLICATE 8 2",
            "OPEN RESERVATIONS: o2",
        ])

    def test_large_n_is_fast(self):
        # 50k commands complete well within the limit even on slow machines.
        # This guards against an accidental O(N^2) regression; absolute time
        # depends on the host. 40s is far above an O(N) run yet far below what
        # an O(N^2) implementation would take.
        import time
        n = 50_000
        ledger = Ledger(on_hand=10 ** 12)
        commands = [f"RESERVE e{i} o{i} 1" for i in range(n)]
        start = time.perf_counter()
        for cmd in commands:
            process_command(ledger, cmd.split())
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 40.0)


if __name__ == "__main__":
    unittest.main()
