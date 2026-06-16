from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_taste_etl.etl import run_pipeline
from agent_taste_etl.io import load_chat_history
from agent_taste_etl.omnigent import load_omnigent_chat_history, write_omnigent_chat_history


class OmnigentAdapterTest(unittest.TestCase):
    def test_normalizes_omnigent_session_events_for_etl(self) -> None:
        chat_history = load_omnigent_chat_history(Path("examples/omnigent_session_events.json"))

        self.assertEqual(chat_history["conversation_id"], "conv_omnigent_h4v_001")
        self.assertEqual(chat_history["source"], "omnigent_session_events")
        self.assertEqual(len(chat_history["messages"]), 5)
        self.assertEqual(chat_history["messages"][0]["content"][0]["type"], "text")
        self.assertEqual(chat_history["messages"][3]["phase"], "approval")
        self.assertEqual(chat_history["messages"][3]["metadata"]["omnigent_event_type"], "response.elicitation_request")

    def test_omnigent_history_feeds_existing_pipeline(self) -> None:
        payload = load_omnigent_chat_history(Path("examples/omnigent_session_events.json"))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat_history.json"
            write_omnigent_chat_history(payload, path)
            result = run_pipeline(load_chat_history(path))

        subjects = {signal.subject: signal for signal in result.signals}
        self.assertEqual(subjects["corporate explainer voice"].polarity, "negative")
        self.assertEqual(subjects["generic stock footage"].polarity, "negative")
        self.assertEqual(subjects["real workflow screens"].polarity, "positive")
        self.assertEqual(subjects["synthetic skin texture"].polarity, "negative")
        self.assertGreaterEqual(result.manifest["signal_count"], 5)


if __name__ == "__main__":
    unittest.main()
