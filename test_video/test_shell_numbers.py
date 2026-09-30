import unittest
import numpy as np
from scripts.detect_shell_numbers import candidates, digit_candidates


class ShellNumbersTest(unittest.TestCase):
    def test_blue_proposals_and_literal_digits_only(self):
        rgb = np.full((300,300,3), (120,150,60), dtype=np.uint8)
        rgb[130:147,140:146] = (30,40,140)
        ink, boxes = candidates(rgb)
        self.assertTrue(any(x0<=140<x1 and y0<=130<y1 for x0,y0,x1,y1 in boxes))
        self.assertEqual(int(ink[135,142]),255)
        self.assertEqual(candidates(np.full_like(rgb,(120,150,60)))[1], [])
        rgb[:80] = (30,40,140)  # Blue background must not become shell marks.
        self.assertTrue(all(y0>80 for x0,y0,x1,y1 in candidates(rgb)[1]))
        reads = [{"texts": [{"text": s} for s in [" 3 ","S","I","N1V10C3","12","5"]]}]
        self.assertEqual(digit_candidates(reads), ["3","5"])


if __name__ == "__main__":
    unittest.main()
