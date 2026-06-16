from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_taste_etl.etl import run_pipeline
from agent_taste_etl.integrations import (
    build_clickhouse_rows,
    build_pioneer_decoder_sft_rows,
    build_pioneer_training_job_request,
    write_clickhouse_export,
    write_pioneer_export,
)
from agent_taste_etl.io import load_chat_history, read_jsonl


class IntegrationExportsTest(unittest.TestCase):
    def test_builds_clickhouse_json_each_row_exports(self) -> None:
        result = run_pipeline(load_chat_history(Path("examples/long_multiturn_chat_history.json")))
        rows = build_clickhouse_rows(
            result,
            conversation_id="conv_h4v_launch_video_001",
            user_id="user_demo",
            dataset_name="harness4visuals_preference_sft",
        )

        self.assertEqual(len(rows["runs"]), 1)
        self.assertEqual(len(rows["preference_signals"]), len(result.signals))
        self.assertEqual(rows["preference_signals"][0]["conversation_id"], "conv_h4v_launch_video_001")
        self.assertIn("payload_json", rows["training_examples"][0])
        json.loads(rows["training_examples"][0]["payload_json"])

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_clickhouse_export(rows, out_dir)
            self.assertTrue((out_dir / "preference_signals.jsonl").exists())
            self.assertEqual(len(read_jsonl(out_dir / "preference_signals.jsonl")), len(result.signals))

    def test_builds_pioneer_decoder_sft_export(self) -> None:
        result = run_pipeline(load_chat_history(Path("examples/long_multiturn_chat_history.json")))
        rows = build_pioneer_decoder_sft_rows(result)

        self.assertEqual(len(rows), len(result.training_examples))
        messages = rows[0]["messages"]
        self.assertEqual([message["role"] for message in messages], ["system", "user", "assistant"])
        self.assertIn("taste_signals", messages[1]["content"])
        json.loads(messages[2]["content"])

        request = build_pioneer_training_job_request(
            dataset_name="harness4visuals_preference_sft",
            model_name="harness4visuals-preference-prompt-adapter",
        )
        self.assertEqual(request["training_algorithm"], "sft")
        self.assertEqual(request["training_type"], "lora")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_pioneer_export(
                result,
                out_dir,
                dataset_name="harness4visuals_preference_sft",
                model_name="harness4visuals-preference-prompt-adapter",
            )
            self.assertTrue((out_dir / "decoder_sft.jsonl").exists())
            self.assertTrue((out_dir / "training_job_request.json").exists())


if __name__ == "__main__":
    unittest.main()
