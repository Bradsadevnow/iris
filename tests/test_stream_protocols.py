from __future__ import annotations

import json
import threading
import unittest

from iris.server import parse_anthropic_stream, parse_openai_stream


class StreamProtocolTest(unittest.TestCase):
    def test_anthropic_thinking_text_and_usage(self) -> None:
        packets = [
            {"type": "message_start", "message": {"usage": {"input_tokens": 12}}},
            {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "Consider."}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}},
            {"type": "message_delta", "usage": {"output_tokens": 3}},
        ]
        stream = []
        for packet in packets:
            stream.extend([f"event: {packet['type']}\n".encode(),
                           f"data: {json.dumps(packet)}\n".encode(), b"\n"])
        events = []
        answer, reasoning, usage = parse_anthropic_stream(
            stream, lambda event, data: events.append((event, data)), threading.Event())
        self.assertEqual(answer, "Hello")
        self.assertEqual(reasoning, "Consider.")
        self.assertEqual(usage, {"input_tokens": 12, "output_tokens": 3})
        self.assertIn("assistant.reasoning.delta", [event for event, _ in events])
        self.assertIn("assistant.delta", [event for event, _ in events])

    def test_openai_reasoning_text_and_usage(self) -> None:
        packets = [
            {"choices": [{"delta": {"reasoning_content": "Consider."}}]},
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}},
        ]
        stream = [f"data: {json.dumps(packet)}\n".encode() for packet in packets] + [b"data: [DONE]\n"]
        answer, reasoning, usage = parse_openai_stream(stream, lambda *_: None, threading.Event())
        self.assertEqual(answer, "Hello")
        self.assertEqual(reasoning, "Consider.")
        self.assertEqual(usage["total_tokens"], 15)


if __name__ == "__main__":
    unittest.main()
