from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_taste_etl.etl import run_pipeline, write_result
from agent_taste_etl.evaluate import assert_thresholds, evaluate_files
from agent_taste_etl.io import load_chat_history


class EvaluatorTest(unittest.TestCase):
    def test_scores_pipeline_against_golden_fixture(self) -> None:
        messages = load_chat_history(Path("examples/chat_history.json"))
        result = run_pipeline(messages)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_result(result, out_dir)
            evaluation = evaluate_files(out_dir / "signals.jsonl", Path("examples/golden_signals.jsonl"))

        self.assertEqual(evaluation.metrics["schema_validity_rate"], 1.0)
        self.assertEqual(evaluation.metrics["provenance_rate"], 1.0)
        self.assertGreaterEqual(evaluation.metrics["f1"], 0.8)
        assert_thresholds(evaluation, min_f1=0.8, max_hallucination_rate=0.2)


if __name__ == "__main__":
    unittest.main()

