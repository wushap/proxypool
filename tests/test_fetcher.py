import unittest
from unittest.mock import patch

from proxypool.collector.fetcher import fetch_text


class _DummyResponse:
    def __init__(self, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _DummyOpener:
    def __init__(self, response: _DummyResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, float]] = []

    def open(self, req, timeout: float = 0):
        self.calls.append((req.full_url, timeout))
        return self.response


class TestFetcher(unittest.TestCase):
    def test_fetch_text_uses_proxy_disabled_opener(self) -> None:
        dummy = _DummyOpener(_DummyResponse(b"hello"))
        with patch("proxypool.collector.fetcher.build_opener", return_value=dummy) as mocked_build:
            text = fetch_text("https://example.com/sub.txt", timeout_sec=9.5)

        self.assertEqual(text, "hello")
        mocked_build.assert_called_once()
        self.assertEqual(len(dummy.calls), 1)
        self.assertEqual(dummy.calls[0][0], "https://example.com/sub.txt")
        self.assertEqual(dummy.calls[0][1], 9.5)


if __name__ == "__main__":
    unittest.main()
