import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embed import lsb_embed
from positions import block_and_intra_order


class TestEmbed(unittest.TestCase):
    def test_round_trip_random(self):
        rng = np.random.default_rng(0)
        values = rng.integers(0, 256, size=5000, dtype=np.uint8)
        bits = rng.integers(0, 2, size=5000, dtype=np.uint8)
        out = lsb_embed(values, bits, rng)
        self.assertTrue(np.array_equal(out & 1, bits))

    def test_edge_values_0_and_255(self):
        rng = np.random.default_rng(1)
        values = np.array([0, 255, 0, 255], dtype=np.uint8)
        bits = np.array([1, 0, 0, 1], dtype=np.uint8)
        out = lsb_embed(values, bits, rng)
        self.assertTrue(np.array_equal(out & 1, bits))
        self.assertTrue(np.all(out >= 0) and np.all(out <= 255))

    def test_no_change_when_bit_already_matches(self):
        rng = np.random.default_rng(2)
        values = np.array([10, 11, 200, 201], dtype=np.uint8)  # LSB: 0,1,0,1
        bits = np.array([0, 1, 0, 1], dtype=np.uint8)
        out = lsb_embed(values, bits, rng)
        self.assertTrue(np.array_equal(out, values))


class TestPositions(unittest.TestCase):
    def test_block_and_intra_order_are_permutations(self):
        block_order, intra_order = block_and_intra_order(seed=123, n_blocks=7, block_size=50)
        self.assertEqual(sorted(block_order.tolist()), list(range(7)))
        self.assertEqual(sorted(intra_order.tolist()), list(range(50)))

    def test_deterministic_for_same_seed(self):
        b1, i1 = block_and_intra_order(42, 5, 20)
        b2, i2 = block_and_intra_order(42, 5, 20)
        self.assertTrue(np.array_equal(b1, b2))
        self.assertTrue(np.array_equal(i1, i2))

    def test_differs_for_different_seed(self):
        b1, i1 = block_and_intra_order(1, 20, 200)
        b2, i2 = block_and_intra_order(2, 20, 200)
        self.assertFalse(np.array_equal(b1, b2) and np.array_equal(i1, i2))


if __name__ == "__main__":
    unittest.main()
