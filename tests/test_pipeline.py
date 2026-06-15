from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_taste_etl.etl import run_pipeline, write_result
from agent_taste_etl.io import load_chat_history, read_jsonl


class PipelineTest(unittest.TestCase):
    def test_writes_model_ready_outputs(self) -> None:
        messages = load_chat_history(Path("examples/chat_history.json"))
        result = run_pipeline(messages)

        self.assertGreaterEqual(len(result.signals), 10)
        self.assertEqual(len(result.prompts), 1)
        self.assertEqual(len(result.training_examples), 1)
        self.assertIn("run_fingerprint", result.manifest)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_result(result, out_dir)
            self.assertTrue((out_dir / "signals.jsonl").exists())
            self.assertTrue((out_dir / "taste_profile.json").exists())
            self.assertTrue((out_dir / "prompts.jsonl").exists())
            self.assertTrue((out_dir / "training.jsonl").exists())
            self.assertTrue((out_dir / "manifest.json").exists())

            training_rows = read_jsonl(out_dir / "training.jsonl")
            self.assertEqual(training_rows[0]["metadata"]["format"], "slm_jsonl")
            profile = json.loads((out_dir / "taste_profile.json").read_text(encoding="utf-8"))
            self.assertTrue(profile["durable"])


if __name__ == "__main__":
    unittest.main()

