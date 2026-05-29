"""Additional tests for NodePool to cover remaining branches."""

from __future__ import annotations

import time
import unittest
from dataclasses import dataclass, field

from proxypool.pool.node_pool import (
    DEFAULT_PROTOCOLS_BY_POOL_TYPE,
    NodeEntry,
    NodePool,
)
from proxypool.pool.scoring import NodeScore, ScoreGrade


def _make_score(key: str = "n1", final: float = 80.0) -> NodeScore:
    """Build a minimal NodeScore for testing sort logic."""
    return NodeScore(
        node_key=key,
        timestamp=time.time(),
        success_rate=1.0,
        avg_latency_ms=50,
        purity_score=None,
        stability_score=1.0,
        availability_score=1.0,
        latency_score=0.8,
        purity_score_normalized=0.5,
        raw_score=75.0,
        final_score=final,
        grade=ScoreGrade.A,
        confidence=0.9,
    )


class TestNodePoolHealthyNodesScored(unittest.TestCase):
    """Cover the sort_key branch where score is not None (line 104)."""

    def test_get_healthy_nodes_sorted_by_score(self):
        pool = NodePool("p", "exit", [])
        low = NodeEntry(
            key="low", protocol="ss", host="a", port=1, raw_link="",
            circuit_open=False, routeable=True,
            score=_make_score("low", 30.0),
        )
        high = NodeEntry(
            key="high", protocol="ss", host="b", port=2, raw_link="",
            circuit_open=False, routeable=True,
            score=_make_score("high", 90.0),
        )
        no_score = NodeEntry(
            key="noscore", protocol="ss", host="c", port=3, raw_link="",
            circuit_open=False, routeable=True,
            score=None,
        )
        pool.add_node(high)
        pool.add_node(no_score)
        pool.add_node(low)

        healthy = pool.get_healthy_nodes()
        keys = [n.key for n in healthy]
        # Highest score first, None-score at end
        self.assertEqual(keys, ["high", "low", "noscore"])


class TestNodePoolUpdateHealthBranches(unittest.TestCase):
    """Cover branches 137->139 and 139->147 in update_node_health."""

    def _pool_with_entry(self) -> tuple[NodePool, NodeEntry]:
        pool = NodePool("p", "exit", [])
        entry = NodeEntry(
            key="n1", protocol="ss", host="h", port=1, raw_link="",
        )
        pool.add_node(entry)
        return pool, entry

    def test_success_no_egress_ip_no_latency(self):
        pool, _ = self._pool_with_entry()
        updated = pool.update_node_health(
            "n1", success=True, egress_ip="", latency_ms=None,
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.egress_ip, "")
        self.assertIsNone(updated.latency_ms)
        self.assertFalse(updated.circuit_open)
        self.assertEqual(updated.failure_count, 0)

    def test_success_with_egress_no_latency(self):
        pool, _ = self._pool_with_entry()
        updated = pool.update_node_health(
            "n1", success=True, egress_ip="10.0.0.1", latency_ms=None,
        )
        self.assertEqual(updated.egress_ip, "10.0.0.1")
        self.assertIsNone(updated.latency_ms)

    def test_success_no_egress_with_latency(self):
        pool, _ = self._pool_with_entry()
        updated = pool.update_node_health(
            "n1", success=True, egress_ip="", latency_ms=120,
        )
        self.assertEqual(updated.egress_ip, "")
        self.assertEqual(updated.latency_ms, 120)


class TestNodePoolRebuildEdgeCases(unittest.TestCase):
    """Cover additional rebuild branches."""

    def test_rebuild_with_filter_matching_tags(self):
        pool = NodePool("p", "exit", [".*premium.*"])
        all_nodes = {
            "k1": {
                "protocol": "trojan", "host": "h", "port": 443,
                "raw_link": "", "name": "node1", "tags": ["premium", "us"],
            },
        }
        matched = pool.rebuild(all_nodes)
        self.assertIn("k1", matched)

    def test_rebuild_with_filter_not_matching(self):
        pool = NodePool("p", "exit", [".*premium.*"])
        all_nodes = {
            "k1": {
                "protocol": "trojan", "host": "h", "port": 443,
                "raw_link": "", "name": "basic-node", "tags": ["free"],
            },
        }
        matched = pool.rebuild(all_nodes)
        self.assertEqual(len(matched), 0)

    def test_rebuild_empty_nodes(self):
        pool = NodePool("p", "exit", [".*.*"])
        matched = pool.rebuild({})
        self.assertEqual(len(matched), 0)


class TestDefaultProtocols(unittest.TestCase):
    """Cover the DEFAULT_PROTOCOLS_BY_POOL_TYPE constant."""

    def test_front_protocols(self):
        protos = DEFAULT_PROTOCOLS_BY_POOL_TYPE["front"]
        self.assertIn("http", protos)
        self.assertIn("socks", protos)
        self.assertIn("ss", protos)

    def test_exit_protocols(self):
        protos = DEFAULT_PROTOCOLS_BY_POOL_TYPE["exit"]
        self.assertIn("trojan", protos)
        self.assertIn("vless", protos)
        self.assertIn("vmess", protos)
        self.assertIn("hysteria2", protos)

    def test_should_include_by_default_unknown_pool(self):
        pool = NodePool("p", "unknown_type", [])
        # Unknown pool_type returns empty set from dict, so nothing included
        self.assertFalse(pool.should_include_by_default({"protocol": "http"}))

    def test_should_include_by_default_missing_protocol(self):
        pool = NodePool("p", "exit", [])
        self.assertFalse(pool.should_include_by_default({}))
        self.assertFalse(pool.should_include_by_default({"protocol": ""}))
        self.assertFalse(pool.should_include_by_default({"protocol": "  "}))

    def test_should_include_by_default_whitespace_protocol(self):
        pool = NodePool("p", "exit", [])
        self.assertTrue(pool.should_include_by_default({"protocol": " Trojan "}))


class TestMatchesNodeTagMatching(unittest.TestCase):
    """Covers tag-based matching in matches_node."""

    def test_match_on_tag_not_name(self):
        pool = NodePool("p", "exit", [".*us-west.*"])
        self.assertTrue(pool.matches_node("k", "unknown", ["us-west", "premium"]))
        self.assertFalse(pool.matches_node("k", "unknown", ["eu", "basic"]))

    def test_multiple_filters_any_matches(self):
        pool = NodePool("p", "exit", [".*alpha.*", ".*beta.*"])
        self.assertTrue(pool.matches_node("k", "alpha-node", []))
        self.assertTrue(pool.matches_node("k", "beta-node", []))
        self.assertFalse(pool.matches_node("k", "gamma-node", []))


if __name__ == "__main__":
    unittest.main()
