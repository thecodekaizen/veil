import json
from pathlib import Path
import tempfile
import unittest

from thermal_investigator.review import review_run
from thermal_investigator.run import run_case


class OfflineReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "case"
        result = run_case(self.directory, 23, False, "fixed", 2)
        self.assertNotEqual(result.get("status"), "failed", result)

    def tearDown(self):
        self.temp.cleanup()

    def test_saved_record_can_be_reviewed_without_model_or_lab(self):
        checked = review_run(self.directory)
        self.assertTrue(checked["valid"], checked)
        self.assertEqual(checked["model_calls_made_by_review"], 0)

    def test_modified_prediction_is_detected(self):
        path = self.directory / "prediction-commit.json"
        record = json.loads(path.read_text())
        record["prediction"]["temperature_c"][5][0] += 1.
        path.write_text(json.dumps(record))
        checked = review_run(self.directory)
        self.assertFalse(checked["valid"])
        self.assertIn("Prediction file does not match its recorded commitment", checked["errors"])

    def test_changed_score_is_detected_independently(self):
        path = self.directory / "result.json"
        result = json.loads(path.read_text())
        result["mean_rmse_c"] = 0.
        path.write_text(json.dumps(result))
        checked = review_run(self.directory)
        self.assertFalse(checked["valid"])
        self.assertIn("Stored mean score does not match recomputed error", checked["errors"])

    def test_reordered_ledger_is_detected(self):
        path = self.directory / "events.jsonl"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(reversed(lines)) + "\n")
        self.assertFalse(review_run(self.directory)["valid"])

    def test_missing_record_fails_closed(self):
        (self.directory / "prediction-commit.json").unlink()
        self.assertFalse(review_run(self.directory)["valid"])


if __name__ == "__main__":
    unittest.main()
