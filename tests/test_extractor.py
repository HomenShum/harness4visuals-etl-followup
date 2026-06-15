from __future__ import annotations

import unittest
from pathlib import Path

from agent_taste_etl.extract import extract_signals
from agent_taste_etl.io import load_chat_history


class ExtractorTest(unittest.TestCase):
    def test_extracts_positive_negative_scoped_signals_with_provenance(self) -> None:
        messages = load_chat_history(Path("examples/chat_history.json"))
        signals = extract_signals(messages)
        by_subject = {signal.subject: signal for signal in signals}

        self.assertEqual(by_subject["purple gradients"].polarity, "negative")
        self.assertEqual(by_subject["purple gradients"].scope, "durable")
        self.assertEqual(by_subject["concise captions"].kind, "voice")
        self.assertEqual(by_subject["chaotic"].scope, "campaign")
        self.assertEqual(by_subject["fast cuts"].scope, "session")
        self.assertEqual(by_subject["fake testimonials"].kind, "trust")

        for signal in signals:
            self.assertTrue(signal.source_turn_ids)
            self.assertTrue(signal.evidence)


if __name__ == "__main__":
    unittest.main()

