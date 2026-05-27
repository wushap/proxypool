"""
Tests for NodePool module.
"""
from __future__ import annotations

import unittest

from proxypool.pool.node_pool import NodeEntry, NodePool


class TestNodeEntry(unittest.TestCase):
    """Test NodeEntry dataclass."""

    def test_init(self):
        """Test NodeEntry initialization."""
        entry = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
        )

        self.assertEqual(entry.key, "node1")
        self.assertEqual(entry.protocol, "trojan")
        self.assertEqual(entry.host, "example.com")
        self.assertEqual(entry.port, 443)
        self.assertEqual(entry.failure_count, 0)
        self.assertFalse(entry.circuit_open)
        self.assertIsNone(entry.score)
        self.assertIsNone(entry.circuit_breaker)

    def test_defaults(self):
        """Test NodeEntry default values."""
        entry = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
        )

        self.assertEqual(entry.name, "")
        self.assertEqual(entry.tags, [])
        self.assertEqual(entry.failure_count, 0)
        self.assertFalse(entry.circuit_open)
        self.assertEqual(entry.egress_ip, "")
        self.assertEqual(entry.egress_region, "")
        self.assertIsNone(entry.latency_ms)
        self.assertFalse(entry.routeable)
        self.assertEqual(entry.last_success_at, "")
        self.assertEqual(entry.last_failure_at, "")


class TestNodePool(unittest.TestCase):
    """Test NodePool class."""

    def test_init(self):
        """Test NodePool initialization."""
        pool = NodePool(
            name="test-pool",
            pool_type="exit",
            regex_filters=[".*trojan.*", ".*ss.*"],
        )

        self.assertEqual(pool.name, "test-pool")
        self.assertEqual(pool.pool_type, "exit")
        self.assertEqual(pool.regex_filters, [".*trojan.*", ".*ss.*"])
        self.assertEqual(len(pool._compiled_filters), 2)

    def test_compile_filters(self):
        """Test compile_filters static method."""
        filters = NodePool.compile_filters([".*trojan.*", ".*ss.*"])
        self.assertEqual(len(filters), 2)
        self.assertTrue(hasattr(filters[0], "search"))

    def test_matches_node(self):
        """Test matches_node with regex patterns."""
        pool = NodePool(
            name="test-pool",
            pool_type="exit",
            regex_filters=[".*trojan.*", ".*us.*"],
        )

        # Should match
        self.assertTrue(pool.matches_node("key1", "us-trojan-node", []))
        self.assertTrue(pool.matches_node("key2", "node-name", ["us", "trojan"]))

        # Should not match
        self.assertFalse(pool.matches_node("key3", "sg-vmess-node", []))
        self.assertFalse(pool.matches_node("key4", "node-name", ["sg", "vmess"]))

    def test_matches_node_no_filters(self):
        """Test matches_node with no filters returns False."""
        pool = NodePool(
            name="test-pool",
            pool_type="exit",
            regex_filters=[],
        )
        self.assertFalse(pool.matches_node("key1", "any-node", []))

    def test_should_include_by_default(self):
        """Test should_include_by_default."""
        # Exit pool should include trojan, vless, vmess
        exit_pool = NodePool("exit-pool", "exit", [])
        self.assertTrue(exit_pool.should_include_by_default({"protocol": "trojan"}))
        self.assertTrue(exit_pool.should_include_by_default({"protocol": "vless"}))
        self.assertTrue(exit_pool.should_include_by_default({"protocol": "vmess"}))
        self.assertTrue(exit_pool.should_include_by_default({"protocol": "ss"}))
        self.assertFalse(exit_pool.should_include_by_default({"protocol": "wireguard"}))

        # Front pool should only include http, socks, ss
        front_pool = NodePool("front-pool", "front", [])
        self.assertTrue(front_pool.should_include_by_default({"protocol": "http"}))
        self.assertTrue(front_pool.should_include_by_default({"protocol": "socks"}))
        self.assertTrue(front_pool.should_include_by_default({"protocol": "ss"}))
        self.assertFalse(front_pool.should_include_by_default({"protocol": "trojan"}))

    def test_add_and_get_node(self):
        """Test add_node and get_node."""
        pool = NodePool("test-pool", "exit", [])

        entry = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
        )

        pool.add_node(entry)
        retrieved = pool.get_node("node1")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "node1")
        self.assertEqual(retrieved.protocol, "trojan")

    def test_get_node_nonexistent(self):
        """Test get_node with nonexistent key returns None."""
        pool = NodePool("test-pool", "exit", [])
        self.assertIsNone(pool.get_node("nonexistent"))

    def test_remove_node(self):
        """Test remove_node."""
        pool = NodePool("test-pool", "exit", [])

        entry = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
        )

        pool.add_node(entry)
        pool.remove_node("node1")
        self.assertIsNone(pool.get_node("node1"))

    def test_remove_nonexistent_node(self):
        """Test removing nonexistent node doesn't raise error."""
        pool = NodePool("test-pool", "exit", [])
        pool.remove_node("nonexistent")  # Should not raise

    def test_get_all_nodes(self):
        """Test get_all_nodes."""
        pool = NodePool("test-pool", "exit", [])

        entry1 = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
        )
        entry2 = NodeEntry(
            key="node2",
            protocol="ss",
            host="example2.com",
            port=8388,
            raw_link="ss://password@example2.com:8388",
        )

        pool.add_node(entry1)
        pool.add_node(entry2)

        all_nodes = pool.get_all_nodes()
        self.assertEqual(len(all_nodes), 2)

    def test_get_healthy_nodes(self):
        """Test get_healthy_nodes."""
        pool = NodePool("test-pool", "exit", [])

        entry1 = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
            circuit_open=False,
            routeable=True,
        )
        entry2 = NodeEntry(
            key="node2",
            protocol="ss",
            host="example2.com",
            port=8388,
            raw_link="ss://password@example2.com:8388",
            circuit_open=True,  # Unhealthy
            routeable=True,
        )
        entry3 = NodeEntry(
            key="node3",
            protocol="vmess",
            host="example3.com",
            port=443,
            raw_link="vmess://uuid@example3.com:443",
            circuit_open=False,
            routeable=False,  # Not routeable
        )

        pool.add_node(entry1)
        pool.add_node(entry2)
        pool.add_node(entry3)

        healthy = pool.get_healthy_nodes()
        self.assertEqual(len(healthy), 1)
        self.assertEqual(healthy[0].key, "node1")

    def test_update_node_health_success(self):
        """Test update_node_health with success."""
        pool = NodePool("test-pool", "exit", [])

        entry = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
            failure_count=3,
            circuit_open=True,
        )

        pool.add_node(entry)
        updated = pool.update_node_health(
            "node1",
            success=True,
            egress_ip="1.2.3.4",
            latency_ms=100,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.failure_count, 0)
        self.assertFalse(updated.circuit_open)
        self.assertEqual(updated.egress_ip, "1.2.3.4")
        self.assertEqual(updated.latency_ms, 100)
        self.assertNotEqual(updated.last_success_at, "")

    def test_update_node_health_failure(self):
        """Test update_node_health with failure."""
        pool = NodePool("test-pool", "exit", [])

        entry = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
            failure_count=0,
            circuit_open=False,
        )

        pool.add_node(entry)
        updated = pool.update_node_health(
            "node1",
            success=False,
            max_failures=3,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.failure_count, 1)
        self.assertFalse(updated.circuit_open)
        self.assertNotEqual(updated.last_failure_at, "")

    def test_update_node_health_circuit_open(self):
        """Test update_node_health opens circuit after max failures."""
        pool = NodePool("test-pool", "exit", [])

        entry = NodeEntry(
            key="node1",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
            failure_count=2,
            circuit_open=False,
        )

        pool.add_node(entry)
        updated = pool.update_node_health(
            "node1",
            success=False,
            max_failures=3,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.failure_count, 3)
        self.assertTrue(updated.circuit_open)

    def test_update_node_health_nonexistent(self):
        """Test update_node_health with nonexistent node returns None."""
        pool = NodePool("test-pool", "exit", [])
        result = pool.update_node_health("nonexistent", success=True)
        self.assertIsNone(result)

    def test_rebuild_with_filters(self):
        """Test rebuild with regex filters."""
        pool = NodePool(
            name="test-pool",
            pool_type="exit",
            regex_filters=[".*trojan.*"],
        )

        all_nodes = {
            "key1": {
                "protocol": "trojan",
                "host": "example.com",
                "port": 443,
                "raw_link": "trojan://password@example.com:443",
                "name": "us-trojan-node",
                "tags": [],
            },
            "key2": {
                "protocol": "ss",
                "host": "example2.com",
                "port": 8388,
                "raw_link": "ss://password@example2.com:8388",
                "name": "sg-ss-node",
                "tags": [],
            },
        }

        matched = pool.rebuild(all_nodes)

        self.assertEqual(len(matched), 1)
        self.assertIn("key1", matched)
        self.assertEqual(len(pool.get_all_nodes()), 1)

    def test_rebuild_without_filters(self):
        """Test rebuild without filters uses default inclusion."""
        pool = NodePool(
            name="test-pool",
            pool_type="exit",
            regex_filters=[],
        )

        all_nodes = {
            "key1": {
                "protocol": "trojan",
                "host": "example.com",
                "port": 443,
                "raw_link": "trojan://password@example.com:443",
                "name": "node1",
                "tags": [],
            },
            "key2": {
                "protocol": "ss",
                "host": "example2.com",
                "port": 8388,
                "raw_link": "ss://password@example2.com:8388",
                "name": "node2",
                "tags": [],
            },
            "key3": {
                "protocol": "wireguard",
                "host": "example3.com",
                "port": 51820,
                "raw_link": "wireguard://...",
                "name": "node3",
                "tags": [],
            },
        }

        matched = pool.rebuild(all_nodes)

        # Should include trojan and ss, but not wireguard
        self.assertEqual(len(matched), 2)
        self.assertIn("key1", matched)
        self.assertIn("key2", matched)
        self.assertNotIn("key3", matched)

    def test_rebuild_clears_existing_nodes(self):
        """Test rebuild clears existing nodes."""
        pool = NodePool(
            name="test-pool",
            pool_type="exit",
            regex_filters=[],
        )

        # Add a node
        entry = NodeEntry(
            key="old-node",
            protocol="trojan",
            host="example.com",
            port=443,
            raw_link="trojan://password@example.com:443",
        )
        pool.add_node(entry)
        self.assertEqual(len(pool.get_all_nodes()), 1)

        # Rebuild with empty nodes
        pool.rebuild({})
        self.assertEqual(len(pool.get_all_nodes()), 0)


if __name__ == "__main__":
    unittest.main()
