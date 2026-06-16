from __future__ import annotations

import unittest
from pathlib import Path

from agent_taste_etl.extract import extract_signals
from agent_taste_etl.io import load_chat_history


class ChatHistoryInputTest(unittest.TestCase):
    def test_loads_long_multiturn_multimodal_history(self) -> None:
        messages = load_chat_history(Path("examples/long_multiturn_chat_history.json"))

        self.assertEqual(len(messages), 18)
        self.assertEqual(messages[0].content_blocks[0]["type"], "text")
        self.assertIn("premium", messages[0].content)
        self.assertIn("moodboard", messages[0].content)
        self.assertEqual(messages[0].metadata["user_intent"], "creative_brief")

    def test_extracts_feedback_from_long_review_process(self) -> None:
        messages = load_chat_history(Path("examples/long_multiturn_chat_history.json"))
        signals = extract_signals(messages)
        subjects = {signal.subject: signal for signal in signals}

        self.assertEqual(subjects["corporate explainer voice"].polarity, "negative")
        self.assertEqual(subjects["cinematic product closeups"].polarity, "positive")
        self.assertEqual(subjects["fast cuts"].scope, "session")
        self.assertEqual(subjects["synthetic skin texture"].polarity, "negative")
        self.assertNotIn("sharper first second", subjects)
        self.assertEqual(subjects["chaotic"].scope, "campaign")
        self.assertEqual(subjects["polished"].scope, "durable")


if __name__ == "__main__":
    unittest.main()
