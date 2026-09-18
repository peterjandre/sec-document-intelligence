from __future__ import annotations

import unittest

from rag.tickers import detect_tickers, resolve_query_tickers


class TickerRoutingTests(unittest.TestCase):
    def test_detects_company_name_and_possessive(self) -> None:
        self.assertEqual(
            detect_tickers("How does Apple describe its risks related to manufacturing its products?"),
            ["AAPL"],
        )
        self.assertEqual(detect_tickers("What is Apple's supply chain model?"), ["AAPL"])

    def test_detects_ticker_symbol(self) -> None:
        self.assertEqual(detect_tickers("NVDA data center risks"), ["NVDA"])

    def test_google_aliases_map_to_goog(self) -> None:
        self.assertEqual(detect_tickers("How does Alphabet describe competition?"), ["GOOG"])
        self.assertEqual(detect_tickers("Google advertising revenue"), ["GOOG"])

    def test_multiple_companies_are_all_detected(self) -> None:
        self.assertEqual(
            detect_tickers("Compare Apple and Amazon manufacturing risks"),
            ["AAPL", "AMZN"],
        )

    def test_generic_question_has_no_ticker(self) -> None:
        self.assertEqual(detect_tickers("What do these 10-Ks say about human capital?"), [])

    def test_meta_does_not_match_metadata(self) -> None:
        self.assertEqual(detect_tickers("What metadata appears in the signatures table?"), [])

    def test_resolve_routes_named_issuers(self) -> None:
        self.assertEqual(
            resolve_query_tickers("How does Netflix describe content costs?"),
            ["NFLX"],
        )
        self.assertEqual(resolve_query_tickers("Compare Apple and Amazon"), ["AAPL", "AMZN"])

    def test_resolve_skips_generic(self) -> None:
        self.assertEqual(resolve_query_tickers("What are common risk factors?"), [])

    def test_explicit_ticker_overrides_detection(self) -> None:
        self.assertEqual(
            resolve_query_tickers("How does Apple describe manufacturing?", ticker="NVDA"),
            ["NVDA"],
        )


if __name__ == "__main__":
    unittest.main()
