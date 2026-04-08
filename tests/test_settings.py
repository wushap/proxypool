import os
import unittest
from unittest.mock import patch

from proxypool.settings import load_settings


class TestSettings(unittest.TestCase):
    def test_default_backend_is_singbox(self) -> None:
        with patch.dict(os.environ, {"PROXYPOOL_BACKEND_ENGINE": ""}, clear=False):
            settings = load_settings()
            self.assertEqual(settings.backend_engine, "singbox")
            self.assertEqual(settings.backend_health_check_sec, 30)
            self.assertEqual(settings.backend_auto_restart_max, 3)


if __name__ == "__main__":
    unittest.main()
