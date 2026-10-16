"""Tests for modules.keywords: merchant-key derivation and the shared
collapse-then-classify helper both import paths use."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import keywords


class KeywordFromDesc(unittest.TestCase):
    def test_drops_amazon_order_id(self):
        self.assertEqual(keywords.keyword_from_desc("Amazon.com*NN6BD0FE3"), "amazon.com")

    def test_keeps_merchant_after_star_when_id_leads_with_name(self):
        self.assertEqual(keywords.keyword_from_desc("WF *WAYFAIR4641067361"), "wf *wayfair")

    def test_drops_trailing_store_number_and_city(self):
        self.assertEqual(
            keywords.keyword_from_desc("WHOLEFOODS #123 NEW YORK NY"), "wholefoods")

    def test_plain_merchant_lowercased(self):
        self.assertEqual(keywords.keyword_from_desc("STARBUCKS"), "starbucks")

    def test_multiword_merchant_capped_at_three_words(self):
        self.assertEqual(keywords.keyword_from_desc("THE HOME DEPOT STORE"), "the home depot")

    def test_result_is_substring_of_lowercased_original(self):
        # The categorizer matches keywords by substring, so the derived key MUST
        # re-appear inside the original description next month.
        for desc in ["Amazon.com*NN6BD0FE3", "WHOLEFOODS #123 NEW YORK NY", "STARBUCKS"]:
            self.assertIn(keywords.keyword_from_desc(desc), desc.lower())


class ClassifyDescriptions(unittest.TestCase):
    def test_same_merchant_classified_once_and_shared(self):
        calls = []

        def fake_classify(reps, names, progress_cb=None):
            calls.append(list(reps))
            return {r: "Shopping" for r in reps}

        descs = ["AMAZON.COM*A1", "AMAZON.COM*B2", "AMAZON.COM*C3"]
        result = keywords.classify_descriptions(descs, ["Shopping"], fake_classify)

        self.assertEqual(len(calls), 1)               # one batch
        self.assertEqual(len(calls[0]), 1)            # one representative merchant
        self.assertIn(calls[0][0], descs)             # a real description, not a stub key
        self.assertEqual(set(result.values()), {"Shopping"})
        self.assertEqual(set(result), set(descs))     # every description answered

    def test_distinct_merchants_each_classified(self):
        def fake_classify(reps, names, progress_cb=None):
            return {r: "Groceries" if "whole" in r.lower() else "Coffee" for r in reps}

        result = keywords.classify_descriptions(
            ["WHOLEFOODS #1", "STARBUCKS #9"], ["Groceries", "Coffee"], fake_classify)
        self.assertEqual(result["WHOLEFOODS #1"], "Groceries")
        self.assertEqual(result["STARBUCKS #9"], "Coffee")

    def test_unknown_merchant_is_uncategorized(self):
        result = keywords.classify_descriptions(
            ["MYSTERY LLC"], ["Groceries"], lambda reps, names, progress_cb=None: {})
        self.assertEqual(result, {"MYSTERY LLC": "Uncategorized"})

    def test_blank_descriptions_skipped(self):
        result = keywords.classify_descriptions(
            ["", "   ", "STARBUCKS"], ["Coffee"],
            lambda reps, names, progress_cb=None: {r: "Coffee" for r in reps})
        self.assertEqual(result, {"STARBUCKS": "Coffee"})

    def test_empty_input_makes_no_call(self):
        called = []
        keywords.classify_descriptions(
            [], ["Coffee"], lambda *a, **k: called.append(1) or {})
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
