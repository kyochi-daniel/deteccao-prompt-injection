import json
import hashlib
import unittest

from dataset import build_dataset
from infer import ROOT, classify, tokenize


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((ROOT / "model" / "model.json").read_text())

    def test_groups_and_duplicates(self):
        rows = build_dataset()
        self.assertEqual(len(rows), 816)
        self.assertEqual(len({row["text"] for row in rows}), len(rows))
        group_splits = {}
        for row in rows:
            group_splits.setdefault(row["group"], set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in group_splits.values()))
        for split in ["train", "validation", "test", "challenge"]:
            labels = [row["label"] for row in rows if row["split"] == split]
            self.assertEqual(labels.count(0), labels.count(1))

    def test_feature_contract(self):
        model = self.model
        self.assertEqual(len(model["vocabulary"]), len(model["idf"]))
        self.assertEqual(len(model["idf"]), len(model["coefficients"]))
        self.assertEqual(sorted(model["vocabulary"].values()), list(range(len(model["idf"]))))
        self.assertEqual(tokenize("AÇÃO cafe\u0301 1 API_TOKEN"), ["acao", "cafe", "api_token"])

    def test_portable_fixture_parity(self):
        fixtures = json.loads((ROOT / "tests" / "parity-fixtures.json").read_text())
        for fixture in fixtures:
            result = classify(fixture["text"], self.model)
            self.assertAlmostEqual(result["probability"], fixture["probability"], places=12)
            self.assertEqual(result["label"], fixture["label"])

    def test_validation_and_unknown_text(self):
        for text in [None, 2, "", "  ", "a" * 12001]:
            with self.assertRaises(ValueError):
                classify(text, self.model)
        unknown = classify("漢字 🙂", self.model)
        self.assertEqual(unknown["knownTerms"], 0)
        self.assertEqual(unknown["score"], self.model["intercept"])
        self.assertEqual(unknown["signals"], [])

    def test_export_copies_equal(self):
        self.assertEqual((ROOT / "space" / "model.json").read_bytes(), (ROOT / "model" / "model.json").read_bytes())
        self.assertEqual((ROOT / "space" / "metrics.json").read_bytes(), (ROOT / "reports" / "metrics.json").read_bytes())

    def test_provenance_and_recorded_metrics(self):
        digest = hashlib.sha256((ROOT / "data" / "dataset.jsonl").read_bytes()).hexdigest()
        self.assertEqual(digest, self.model["training"]["dataset_sha256"])
        metrics = json.loads((ROOT / "reports" / "metrics.json").read_text())
        self.assertEqual(digest, metrics["training"]["dataset_sha256"])
        for split in ["validation", "test", "challenge"]:
            rows = [row for row in build_dataset() if row["split"] == split]
            confusion = [[0, 0], [0, 0]]
            for row in rows:
                predicted = int(classify(row["text"], self.model)["label"] == "injecao")
                confusion[row["label"]][predicted] += 1
            self.assertEqual(confusion, metrics["evaluations"][split]["model"]["confusion_matrix"])

    def test_unicode_limit(self):
        self.assertEqual(classify("🙂" * 12000, self.model)["tokenCount"], 0)
        with self.assertRaises(ValueError):
            classify("🙂" * 12001, self.model)


if __name__ == "__main__":
    unittest.main()
