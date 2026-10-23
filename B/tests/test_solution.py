"""Unit tests for Task B - Fulfilment Split Optimiser.

Run:  python3 -m unittest discover -s tests  (from the B/ directory)
"""

import unittest

from solution import solve


class TestBasic(unittest.TestCase):
    def test_minimise_warehouses_then_cost(self):
        # A(9, fixed3, unit2), B(8, fixed7, unit1), C(4, fixed3, unit4), Q=7.
        # One warehouse can fulfil 7 (A or B); min cost among them is B -> 14.
        header = "3 7"
        rows = ["A 9 3 2", "B 8 7 1", "C 4 3 4"]
        self.assertEqual(solve(header, rows), ["1 14", "B 7"])

    def test_exact_allocation(self):
        # Neither warehouse can fulfil 7 alone (stock 4 < 7), so two are used.
        # A 4 + C 3 -> (3+4*2)+(3+3*4)=11+15=26 ; A 3 + C 4 -> 9+19=28.
        header = "2 7"
        rows = ["A 4 3 2", "C 4 3 4"]
        self.assertEqual(solve(header, rows), ["2 26", "A 4", "C 3"])

    def test_impossible_order(self):
        header = "2 10"
        rows = ["A 3 1 1", "B 4 1 1"]  # total stock 7 < 10
        self.assertEqual(solve(header, rows), ["-1"])

    def test_zero_stock_warehouse(self):
        header = "3 5"
        rows = ["A 0 5 5", "B 5 2 1", "C 0 9 9"]  # zero-stock warehouses unusable
        self.assertEqual(solve(header, rows), ["1 7", "B 5"])


class TestTieBreaking(unittest.TestCase):
    def test_lexicographically_smallest_on_equal_cost(self):
        # A alone vs B alone give the same cost; pick the smaller warehouse_id.
        header = "2 4"
        rows = ["B 6 5 1", "A 6 5 1"]  # A: 5+4=9, B: 5+4=9
        self.assertEqual(solve(header, rows), ["1 9", "A 4"])

    def test_lex_order_with_two_warehouses(self):
        header = "3 7"
        # Every warehouse has stock 6 < 7, so exactly two are required.
        # Any two warehouses give cost 17, but the lexicographically smallest
        # sorted allocation is A 1 + B 6 (compared with A 1 + C 6 etc.).
        rows = ["A 6 5 1", "B 6 5 1", "C 6 5 1"]
        self.assertEqual(solve(header, rows), ["2 17", "A 1", "B 6"])


class TestLarge(unittest.TestCase):
    def test_large_quantity_performance(self):
        import time
        w, q = 20, 2000
        rows = [f"WH{i:02d} {2000} {i + 1} {i + 1}" for i in range(w)]
        start = time.perf_counter()
        out = solve(f"{w} {q}", rows)
        elapsed = time.perf_counter() - start
        self.assertNotEqual(out[0], "-1")
        allocated = sum(int(line.split()[1]) for line in out[1:])
        self.assertEqual(allocated, q)
        self.assertLess(elapsed, 60.0)


if __name__ == "__main__":
    unittest.main()
