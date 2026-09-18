from __future__ import annotations

import unittest

from rag.chunker import _slice_text


class SliceTextTests(unittest.TestCase):
    def test_short_text_is_unchanged(self) -> None:
        self.assertEqual(_slice_text("short paragraph", 1200), ["short paragraph"])

    def test_prefers_sentence_end_in_lookback(self) -> None:
        text = ("a" * 35) + ". extra extra extra extra extra"
        pieces = _slice_text(text, 40)
        self.assertEqual(pieces[0], ("a" * 35) + ".")
        self.assertTrue(pieces[1].startswith(" extra"))
        self.assertEqual("".join(pieces), text)

    def test_falls_back_to_whitespace(self) -> None:
        text = ("a" * 36) + " " + ("b" * 40)
        pieces = _slice_text(text, 40)
        self.assertEqual(pieces[0], ("a" * 36) + " ")
        self.assertTrue(pieces[1].startswith("b"))
        self.assertFalse(pieces[0].endswith("b"))
        self.assertEqual("".join(pieces), text)

    def test_hard_cuts_when_no_boundary(self) -> None:
        text = "a" * 80
        pieces = _slice_text(text, 40)
        self.assertEqual(pieces, ["a" * 40, "a" * 40])

    def test_pieces_stay_within_size(self) -> None:
        text = ("Risk sentence. " * 80) + ("word " * 40)
        pieces = _slice_text(text, 120)
        self.assertTrue(all(len(piece) <= 120 for piece in pieces))
        self.assertEqual("".join(pieces), text)
        self.assertGreater(len(pieces), 1)
        for piece in pieces[:-1]:
            self.assertRegex(piece, r"[\s.!?]$")


if __name__ == "__main__":
    unittest.main()
