"""Menu delete helpers in glowgrid.py: selection parsing and file removal.

Run from the repo root:  python3 -m unittest tests.test_menu -v
"""
import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_parity import gc  # noqa: E402,F401  (stubs the Pi driver before glowgrid imports it)
import glowgrid  # noqa: E402


class ParseSelection(unittest.TestCase):
    def test_numbers_and_ranges(self):
        self.assertEqual(glowgrid.parse_selection("3,1,7-9,3", 10), [1, 3, 7, 8, 9])

    def test_single_and_edges(self):
        self.assertEqual(glowgrid.parse_selection("1-3", 3), [1, 2, 3])
        self.assertEqual(glowgrid.parse_selection("2-2", 5), [2])
        self.assertEqual(glowgrid.parse_selection("12", 12), [12])

    def test_spaces_around_commas_are_fine(self):
        self.assertEqual(glowgrid.parse_selection("1, 3 ,5 - 5".replace(" - ", "-"), 9), [1, 3, 5])

    def test_space_without_comma_is_rejected_not_joined(self):
        # "1 2" must never become 12, and "12" must never become 1 and 2
        for bad in ("1 2", "3 5 7-9", "1,2 3"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                glowgrid.parse_selection(bad, 20)

    def test_rejects_bad_input_without_partial_results(self):
        for bad in ("0", "4", "2-5", "9-7", "x", "1-", "-3", "1,q", "", ",", "1,,2", "1,"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                glowgrid.parse_selection(bad, 3)


class DeleteImages(unittest.TestCase):
    def test_deletes_only_named_files(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("a.png", "b.png", "c.png"):
                open(os.path.join(d, n), "w").close()
            old, glowgrid.IMAGES_DIR = glowgrid.IMAGES_DIR, d
            try:
                deleted, failed = glowgrid.delete_images(["a.png", "c.png", "missing.png"])
            finally:
                glowgrid.IMAGES_DIR = old
            self.assertEqual((deleted, failed), (["a.png", "c.png"], ["missing.png"]))
            self.assertEqual(os.listdir(d), ["b.png"])


if __name__ == "__main__":
    unittest.main()
