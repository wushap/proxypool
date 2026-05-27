"""
Tests for ChainBuilder module.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from proxypool.pool.chain_builder import ChainBuilder
from proxypool.pool.node_pool import NodeEntry


class TestChainBuilder(unittest.TestCase):
    """Test ChainBuilder class."""

    def setUp(self):
        """Set up test fixtures."""
        self.storage = MagicMock()
        self.builder = ChainBuilder(self.storage, backend_type="singbox")

    def test_init(self):
        """Test ChainBuilder initialization."""
        self.assertEqual(self.builder.backend_type, "singbox")
        self.assertIs(self.builder.storage, self.storage)

    def test_build_chain_config_compatible_nodes(self):
        """Test build_chain_config with compatible nodes."""
        # Mock storage response - needs to return proper dict format
        self.storage.get_proxy_by_key.return_value = {
            "protocol": "trojan",
            "host": "example.com",
            "port": 443,
            "password": "test-password",
            "name": "test-node",
        }

        # Create compatible nodes
        front_node = NodeEntry(
            key="front-key",
            protocol="trojan",
            host="front.example.com",
            port=443,
            raw_link="trojan://password@front.example.com:443",
        )
        exit_node = NodeEntry(
            key="exit-key",
            protocol="trojan",
            host="exit.example.com",
            port=443,
            raw_link="trojan://password@exit.example.com:443",
        )

        with patch('proxypool.pool.chain_builder.check_nodes_compatibility') as mock_check, \
             patch('proxypool.pool.chain_builder.build_singbox_outbound') as mock_build:
            mock_check.return_value = {
                "compatible": True,
                "incompatible_nodes": [],
            }

            # Mock build_singbox_outbound to return valid outbound
            mock_build.return_value = {
                "type": "trojan",
                "server": "example.com",
                "server_port": 443,
                "password": "test-password",
                "tag": "test-tag",
            }

            config = self.builder.build_chain_config(
                inbound_port=1080,
                front_node=front_node,
                exit_node=exit_node,
            )

            # Verify config structure
            self.assertIn("log", config)
            self.assertIn("inbounds", config)
            self.assertIn("outbounds", config)
            self.assertIn("route", config)

            # Verify inbound
            self.assertEqual(len(config["inbounds"]), 1)
            self.assertEqual(config["inbounds"][0]["type"], "http")
            self.assertEqual(config["inbounds"][0]["listen_port"], 1080)

            # Verify outbounds (exit, front, direct)
            self.assertEqual(len(config["outbounds"]), 3)

            # Verify routing
            self.assertEqual(config["route"]["final"], "direct")

    def test_build_chain_config_incompatible_nodes(self):
        """Test build_chain_config with incompatible nodes."""
        front_node = NodeEntry(
            key="front-key",
            protocol="vless",
            host="front.example.com",
            port=443,
            raw_link="vless://uuid@front.example.com:443",
        )
        exit_node = NodeEntry(
            key="exit-key",
            protocol="vmess",
            host="exit.example.com",
            port=443,
            raw_link="vmess://uuid@exit.example.com:443",
        )

        with patch('proxypool.pool.chain_builder.check_nodes_compatibility') as mock_check:
            mock_check.return_value = {
                "compatible": False,
                "incompatible_nodes": [
                    {"node_key": "front-key", "protocol": "vless"},
                    {"node_key": "exit-key", "protocol": "vmess"},
                ],
            }

            with self.assertRaises(RuntimeError) as context:
                self.builder.build_chain_config(
                    inbound_port=1080,
                    front_node=front_node,
                    exit_node=exit_node,
                )

            self.assertIn("Protocol incompatible", str(context.exception))

    def test_build_probe_config(self):
        """Test build_probe_config."""
        self.storage.get_proxy_by_key.return_value = {
            "protocol": "trojan",
            "host": "example.com",
            "port": 443,
            "password": "test-password",
            "name": "test-node",
        }

        front_node = NodeEntry(
            key="front-key",
            protocol="trojan",
            host="front.example.com",
            port=443,
            raw_link="trojan://password@front.example.com:443",
        )
        exit_node = NodeEntry(
            key="exit-key",
            protocol="trojan",
            host="exit.example.com",
            port=443,
            raw_link="trojan://password@exit.example.com:443",
        )

        with patch('proxypool.pool.chain_builder.check_nodes_compatibility') as mock_check, \
             patch('proxypool.pool.chain_builder.build_singbox_outbound') as mock_build:
            mock_check.return_value = {
                "compatible": True,
                "incompatible_nodes": [],
            }

            # Mock build_singbox_outbound to return valid outbound
            mock_build.return_value = {
                "type": "trojan",
                "server": "example.com",
                "server_port": 443,
                "password": "test-password",
                "tag": "test-tag",
            }

            config = self.builder.build_probe_config(
                front_node=front_node,
                exit_node=exit_node,
                target_url="https://example.com",
            )

            # Verify config structure
            self.assertIn("inbounds", config)
            self.assertIn("outbounds", config)
            self.assertEqual(config["inbounds"][0]["listen_port"], 0)  # Random port

    def test_check_nodes_compatibility(self):
        """Test check_nodes_compatibility wrapper."""
        nodes = [
            {"protocol": "trojan", "normalized_key": "key1"},
            {"protocol": "trojan", "normalized_key": "key2"},
        ]

        with patch('proxypool.pool.chain_builder.check_nodes_compatibility') as mock_check:
            mock_check.return_value = {"compatible": True, "incompatible_nodes": []}
            result = self.builder.check_nodes_compatibility(nodes)

            self.assertTrue(result["compatible"])
            mock_check.assert_called_once_with(nodes, "singbox")

    def test_filter_compatible_nodes(self):
        """Test filter_compatible_nodes wrapper."""
        nodes = [
            {"protocol": "trojan", "normalized_key": "key1"},
            {"protocol": "vless", "normalized_key": "key2"},
        ]

        with patch('proxypool.pool.chain_builder.filter_compatible_nodes') as mock_filter:
            mock_filter.return_value = [nodes[0]]
            result = self.builder.filter_compatible_nodes(nodes)

            self.assertEqual(len(result), 1)
            mock_filter.assert_called_once_with(nodes, "singbox")

    def test_build_chain_proxy_url(self):
        """Test build_chain_proxy_url."""
        front_node = NodeEntry(
            key="front-key",
            protocol="trojan",
            host="front.example.com",
            port=443,
            raw_link="trojan://password@front.example.com:443",
        )
        exit_node = NodeEntry(
            key="exit-key",
            protocol="trojan",
            host="exit.example.com",
            port=443,
            raw_link="trojan://password@exit.example.com:443",
        )

        url = self.builder.build_chain_proxy_url(front_node, exit_node)
        self.assertEqual(url, "trojan://exit.example.com:443")


if __name__ == "__main__":
    unittest.main()
