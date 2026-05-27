"""Shared helpers for HTTP proxy endpoint status computation."""
from __future__ import annotations

import contextlib
from typing import Any


def proxy_status_summary(proxy: dict | None, active_key: str = "") -> dict:
    if proxy is None:
        return {}
    key = str(proxy.get("normalized_key") or "")
    return {
        "key": key,
        "name": str(proxy.get("name") or ""),
        "protocol": str(proxy.get("protocol") or ""),
        "host": str(proxy.get("host") or ""),
        "port": int(proxy.get("port") or 0),
        "available": bool(proxy.get("available")),
        "healthy": bool(proxy.get("available")),
        "active": bool(active_key and key == active_key),
        "latency_ms": proxy.get("latency_ms"),
        "speed_mbps": proxy.get("speed_mbps"),
        "country": str(proxy.get("country") or ""),
        "city": str(proxy.get("city") or ""),
        "resolved_ip": str(proxy.get("resolved_ip") or ""),
        "openai_unlocked": proxy.get("openai_unlocked"),
        "last_checked_at": str(proxy.get("last_checked_at") or ""),
    }


def latest_active_hop_keys(endpoint_id: int, leases: list[dict], instances: list[dict]) -> list[str]:
    live_ids = {
        str(item.get("instance_id") or "")
        for item in instances
        if str(item.get("status") or "") == "running"
    }
    lease_candidates = [
        item for item in leases
        if list(item.get("hop_node_keys") or [])
        and (not live_ids or str(item.get("instance_id") or "") in live_ids)
    ]
    lease_candidates.sort(key=lambda item: str(item.get("last_accessed") or ""), reverse=True)
    if lease_candidates:
        return [str(key) for key in list(lease_candidates[0].get("hop_node_keys") or [])]
    instance_candidates = [
        item for item in instances
        if int(item.get("endpoint_id") or 0) == int(endpoint_id)
        and list(item.get("hop_node_keys") or [])
    ]
    instance_candidates.sort(
        key=lambda item: (str(item.get("status") or "") == "running", str(item.get("updated_at") or "")),
        reverse=True,
    )
    if instance_candidates:
        return [str(key) for key in list(instance_candidates[0].get("hop_node_keys") or [])]
    return []


def endpoint_route_health(chain_service: Any, endpoint_id: int, hop_node_keys: list[str]) -> dict:
    if hasattr(chain_service, "endpoint_route_health"):
        with contextlib.suppress(Exception):
            return dict(chain_service.endpoint_route_health(endpoint_id, hop_node_keys))
    return {
        "failed": False,
        "failure_expires_at": "",
        "known_healthy": False,
        "healthy_until": "",
    }


def build_hop_pool_status(
    storage: Any,
    endpoint_id: int,
    endpoint: dict | None,
    active_hop_keys: list[str],
) -> list[dict]:
    hop_status: list[dict] = []
    for index, hop in enumerate(list((endpoint or {}).get("hops") or [])):
        pool_id = int(hop.get("pool_id") or 0)
        pool = storage.get_proxy_pool(pool_id) if pool_id > 0 else None
        candidates = storage.list_proxy_pool_candidates(pool_id, limit=500) if pool is not None else []
        active_key = active_hop_keys[index] if index < len(active_hop_keys) else ""
        active_proxy = storage.get_proxy_by_key(active_key) if active_key else None
        node_rows = sorted(
            [proxy_status_summary(proxy, active_key=active_key) for proxy in candidates],
            key=lambda item: (not item.get("active"), not item.get("healthy"), item.get("latency_ms") is None, item.get("latency_ms") or 10**9),
        )
        if active_proxy is not None and not any(item.get("key") == active_key for item in node_rows):
            node_rows.insert(0, proxy_status_summary(active_proxy, active_key=active_key))
        healthy_count = sum(1 for item in node_rows if bool(item.get("healthy")))
        hop_status.append({
            "hop_index": index,
            "label": f"第{index + 1}跳",
            "pool": pool,
            "pool_id": pool_id,
            "total_nodes": len(node_rows),
            "healthy_nodes": healthy_count,
            "available": healthy_count > 0,
            "active_node_key": active_key,
            "active_node": proxy_status_summary(active_proxy, active_key=active_key) if active_proxy is not None else None,
            "nodes": node_rows,
        })
    return hop_status


def build_hop_transition_status(
    chain_service: Any,
    endpoint_id: int,
    hop_pools: list[dict],
) -> list[dict]:
    transitions: list[dict] = []
    for index in range(max(0, len(hop_pools) - 1)):
        left = hop_pools[index]
        right = hop_pools[index + 1]
        left_nodes = [item for item in list(left.get("nodes") or []) if item.get("healthy")]
        right_nodes = [item for item in list(right.get("nodes") or []) if item.get("healthy")]
        active_pair = [str(left.get("active_node_key") or ""), str(right.get("active_node_key") or "")]
        pairs: list[dict] = []
        if active_pair[0] and active_pair[1]:
            health = endpoint_route_health(chain_service, endpoint_id, active_pair)
            pairs.append({
                "source": left.get("active_node"),
                "target": right.get("active_node"),
                "hop_node_keys": active_pair,
                "active": True,
                "healthy": bool(not health["failed"] and (left.get("active_node") or {}).get("healthy") and (right.get("active_node") or {}).get("healthy")),
                **health,
            })
        for source in left_nodes:
            for target in right_nodes:
                keys = [str(source.get("key") or ""), str(target.get("key") or "")]
                if not keys[0] or not keys[1] or keys == active_pair:
                    continue
                health = endpoint_route_health(chain_service, endpoint_id, keys)
                pairs.append({
                    "source": source,
                    "target": target,
                    "hop_node_keys": keys,
                    "active": False,
                    "healthy": not health["failed"],
                    **health,
                })
                if len(pairs) >= 80:
                    break
            if len(pairs) >= 80:
                break
        healthy_pairs = sum(1 for item in pairs if bool(item.get("healthy")))
        transitions.append({
            "from_hop_index": index,
            "to_hop_index": index + 1,
            "label": f"第{index + 1}跳 -> 第{index + 2}跳",
            "total_pairs": max(0, len(left_nodes) * len(right_nodes)),
            "shown_pairs": len(pairs),
            "healthy_pairs": healthy_pairs,
            "available": bool(healthy_pairs > 0),
            "pairs": pairs,
        })
    return transitions


def build_endpoint_status_response(
    storage: Any,
    chain_service: Any,
    chain_instance_manager: Any,
    endpoint_id: int,
) -> dict:
    item = storage.get_http_proxy_endpoint(endpoint_id)
    if item is None:
        return {}
    hops = list(item.get("hops") or [])
    entry_pool_id = int(hops[0].get("pool_id") or 0) if hops else 0
    leases = chain_service.get_leases(pool_id=entry_pool_id or None, endpoint_id=endpoint_id or None)
    instances = chain_instance_manager.list_instances(endpoint_id=endpoint_id)
    active_hop_keys = latest_active_hop_keys(endpoint_id, leases, instances)
    hop_pools = build_hop_pool_status(storage, endpoint_id, item, active_hop_keys)
    transitions = build_hop_transition_status(chain_service, endpoint_id, hop_pools)
    hop_pools_available = bool(hop_pools) and all(p.get("available") for p in hop_pools)
    transitions_available = all(t.get("available") for t in transitions)
    return {
        "item": item,
        "leases": leases,
        "instances": instances,
        "active_hop_node_keys": active_hop_keys,
        "hop_pools": hop_pools,
        "transitions": transitions,
        "summary": {
            "endpoint_id": endpoint_id,
            "hop_count": len(hop_pools),
            "available": hop_pools_available and transitions_available,
            "degraded": any(
                p.get("available") and p.get("healthy_nodes", 0) < p.get("total_nodes", 0)
                for p in hop_pools
            ) or any(not t.get("available") for t in transitions),
            "healthy_hop_pools": sum(1 for p in hop_pools if p.get("available")),
            "total_hop_pools": len(hop_pools),
            "healthy_transitions": sum(1 for t in transitions if t.get("available")),
            "total_transitions": len(transitions),
        },
    }
