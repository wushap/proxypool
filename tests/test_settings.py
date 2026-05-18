import os
from pathlib import Path
import unittest
from unittest.mock import patch

from proxypool.settings import _default_mihomo_binary, load_settings


class TestSettings(unittest.TestCase):
    def test_default_backend_is_singbox(self) -> None:
        with patch.dict(os.environ, {"PROXYPOOL_BACKEND_ENGINE": ""}, clear=False):
            settings = load_settings()
            self.assertEqual(settings.backend_engine, "singbox")
            self.assertEqual(settings.backend_health_check_sec, 30)
            self.assertEqual(settings.backend_auto_restart_max, 3)

    def test_default_mihomo_binary_prefers_neighbor_proxy_project(self) -> None:
        root = Path("/tmp/workspace/proxypool")
        neighbor = root.parent / "proxy" / "mihomo" / "mihomo"
        with patch.object(Path, "exists", lambda self: self == neighbor):
            self.assertEqual(_default_mihomo_binary(root), str(neighbor))


if __name__ == "__main__":
    unittest.main()
