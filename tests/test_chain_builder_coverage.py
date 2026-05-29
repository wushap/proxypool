"""
Additional tests for ChainBuilder to cover missing lines (53, 58, 95, 121).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from proxypool.pool.chain_builder import ChainBuilder
from proxypool.pool.node_pool import NodeEntry


class TestChainBuilderMissingLines(unittest.TestCase):
    """Test ChainBuilder error paths and edge cases."""

    def setUp(self):
        self.storage = MagicMock()
        self.builder = ChainBuilder(self.storage, backend_type="singbox")

    def _make_node(self, key: str = "n1", protocol: str = "trojan", host: str = "h.example.com", port: int = 443) -> NodeEntry:
        return NodeEntry(
            key=key,
            protocol=protocol,
            host=host,
            port=port,
            raw_link=f"{protocol}://{host}:{port}",
        )

    # -- line 121: _build_outbound returns None when proxy not found ----

    def test_build_outbound_returns_none_when_proxy_missing(self):
        """_build_outbound returns None when storage has no proxy for the key."""
        self.storage.get_proxy_by_key.return_value = None
        node = self._make_node()
        result = self.builder._build_outbound(node, "tag1")
        self.assertIsNone(result)

    # -- line 53: build_chain_config raises when front outbound is None --

    def test_build_chain_config_raises_on_front_outbound_none(self):
        """build_chain_config raises RuntimeError when front outbound is None."""
        front_node = self._make_node(key="front", host="front.ex.com")
        exit_node = self._make_node(key="exit", host="exit.ex.com")

        def proxy_side_effect(key):
            if key == "exit":
                return {"protocol": "trojan", "host": "exit.ex.com", "port": 443, "password": "pw"}
            return None

        self.storage.get_proxy_by_key.side_effect = proxy_side_effect

        with (
            patch("proxypool.pool.chain_builder.check_nodes_compatibility") as mock_check,
            patch("proxypool.pool.chain_builder.build_singbox_outbound", side_effect=lambda p, tag: {"type": p.get("protocol"), "tag": tag}),
        ):
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            with self.assertRaises(RuntimeError) as ctx:
                self.builder.build_chain_config(1080, front_node, exit_node)
            self.assertIn("front node", str(ctx.exception))

    # -- line 58: build_chain_config raises when exit outbound is None ---

    def test_build_chain_config_raises_on_exit_outbound_none(self):
        """build_chain_config raises RuntimeError when exit outbound is None."""
        front_node = self._make_node(key="front", host="front.ex.com")
        exit_node = self._make_node(key="exit", host="exit.ex.com")

        def proxy_side_effect(key):
            if key == "front":
                return {"protocol": "trojan", "host": "front.ex.com", "port": 443, "password": "pw"}
            return None

        self.storage.get_proxy_by_key.side_effect = proxy_side_effect

        with (
            patch("proxypool.pool.chain_builder.check_nodes_compatibility") as mock_check,
            patch("proxypool.pool.chain_builder.build_singbox_outbound", side_effect=lambda p, tag: {"type": p.get("protocol"), "tag": tag}),
        ):
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            with self.assertRaises(RuntimeError) as ctx:
                self.builder.build_chain_config(1080, front_node, exit_node)
            self.assertIn("exit node", str(ctx.exception))

    # -- line 95: build_probe_config raises when outbound is None --------

    def test_build_probe_config_raises_on_outbound_none(self):
        """build_probe_config raises RuntimeError when either outbound is None."""
        front_node = self._make_node(key="front")
        exit_node = self._make_node(key="exit")
        self.storage.get_proxy_by_key.return_value = None

        with self.assertRaises(RuntimeError) as ctx:
            self.builder.build_probe_config(front_node, exit_node, "https://example.com")
        self.assertIn("probe", str(ctx.exception))

    # -- extra: detour is set on exit outbound in build_chain_config -----

    def test_build_chain_config_sets_detour_on_exit(self):
        """build_chain_config chains exit -> front via detour."""
        self.storage.get_proxy_by_key.return_value = {
            "protocol": "trojan", "host": "h.com", "port": 443, "password": "pw",
        }
        front_node = self._make_node(key="front")
        exit_node = self._make_node(key="exit")

        with (
            patch("proxypool.pool.chain_builder.check_nodes_compatibility") as mock_check,
            patch("proxypool.pool.chain_builder.build_singbox_outbound") as mock_build,
        ):
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            mock_build.return_value = {"type": "trojan", "tag": "t"}

            config = self.builder.build_chain_config(1080, front_node, exit_node)

            # exit outbound should have detour pointing to front tag
            exit_out = config["outbounds"][0]
            self.assertEqual(exit_out["detour"], "out-0-hop-0")

    # -- extra: build_probe_config detour on exit outbound ---------------

    def test_build_probe_config_sets_detour_on_exit(self):
        """build_probe_config chains exit -> front via detour."""
        self.storage.get_proxy_by_key.return_value = {
            "protocol": "ss", "host": "h.com", "port": 8388, "password": "pw",
        }
        front_node = self._make_node(key="f")
        exit_node = self._make_node(key="e")

        with (
            patch("proxypool.pool.chain_builder.check_nodes_compatibility"),
            patch("proxypool.pool.chain_builder.build_singbox_outbound") as mock_build,
        ):
            mock_build.return_value = {"type": "ss", "tag": "t"}
            config = self.builder.build_probe_config(front_node, exit_node, "https://example.com")
            exit_out = config["outbounds"][0]
            self.assertEqual(exit_out["detour"], "out-front")

    # -- extra: build_chain_proxy_url with custom temp_port --------------

    def test_build_chain_proxy_url_ignores_temp_port(self):
        """build_chain_proxy_url returns exit node URL regardless of temp_port."""
        front = self._make_node(key="f", host="a.com", port=1080)
        exit_n = self._make_node(key="e", host="b.com", port=443)
        url = self.builder.build_chain_proxy_url(front, exit_n, temp_port=12345)
        self.assertEqual(url, "trojan://b.com:443")

    # -- extra: mihomo backend_type passthrough -------------------------

    def test_mihomo_backend_type(self):
        """ChainBuilder works with mihomo backend_type."""
        builder = ChainBuilder(self.storage, backend_type="mihomo")
        self.assertEqual(builder.backend_type, "mihomo")

        nodes = [{"protocol": "http", "normalized_key": "k1"}]
        with patch("proxypool.pool.chain_builder.check_nodes_compatibility") as mock_check:
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            result = builder.check_nodes_compatibility(nodes)
            mock_check.assert_called_once_with(nodes, "mihomo")
            self.assertTrue(result["compatible"])

    # -- extra: default listen address ----------------------------------

    def test_build_chain_config_default_listen(self):
        """build_chain_config uses 127.0.0.1 by default."""
        self.storage.get_proxy_by_key.return_value = {
            "protocol": "trojan", "host": "h.com", "port": 443, "password": "pw",
        }
        front_node = self._make_node(key="f")
        exit_node = self._make_node(key="e")

        with (
            patch("proxypool.pool.chain_builder.check_nodes_compatibility") as mock_check,
            patch("proxypool.pool.chain_builder.build_singbox_outbound") as mock_build,
        ):
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            mock_build.return_value = {"type": "trojan", "tag": "t"}
            config = self.builder.build_chain_config(8080, front_node, exit_node)
            self.assertEqual(config["inbounds"][0]["listen"], "127.0.0.1")

    # -- extra: custom listen address -----------------------------------

    def test_build_chain_config_custom_listen(self):
        """build_chain_config uses custom listen address."""
        self.storage.get_proxy_by_key.return_value = {
            "protocol": "trojan", "host": "h.com", "port": 443, "password": "pw",
        }
        front_node = self._make_node(key="f")
        exit_node = self._make_node(key="e")

        with (
            patch("proxypool.pool.chain_builder.check_nodes_compatibility") as mock_check,
            patch("proxypool.pool.chain_builder.build_singbox_outbound") as mock_build,
        ):
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            mock_build.return_value = {"type": "trojan", "tag": "t"}
            config = self.builder.build_chain_config(8080, front_node, exit_node, listen="0.0.0.0")
            self.assertEqual(config["inbounds"][0]["listen"], "0.0.0.0")

    # -- extra: direct outbound always present --------------------------

    def test_chain_config_has_direct_outbound(self):
        """Chain config always includes a direct outbound."""
        self.storage.get_proxy_by_key.return_value = {
            "protocol": "trojan", "host": "h.com", "port": 443, "password": "pw",
        }
        with (
            patch("proxypool.pool.chain_builder.check_nodes_compatibility") as mock_check,
            patch("proxypool.pool.chain_builder.build_singbox_outbound") as mock_build,
        ):
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            mock_build.return_value = {"type": "trojan", "tag": "t"}
            config = self.builder.build_chain_config(
                8080, self._make_node("f"), self._make_node("e"),
            )
            direct_outs = [o for o in config["outbounds"] if o.get("type") == "direct"]
            self.assertEqual(len(direct_outs), 1)
            self.assertEqual(direct_outs[0]["tag"], "direct")


if __name__ == "__main__":
    unittest.main()
