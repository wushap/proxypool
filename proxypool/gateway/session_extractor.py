from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class SessionExtractor:
    def extract(
        self,
        headers: Mapping[str, Any],
        query_params: Mapping[str, Any],
        target_host: str,
        target_path: str,
        header_names: list[str] | None = None,
        query_names: list[str] | None = None,
        rules: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str, bool]:
        normalized_headers = {str(key).lower(): self._first_value(value) for key, value in dict(headers).items()}
        normalized_query = {str(key): self._first_value(value) for key, value in dict(query_params).items()}

        for name in header_names or []:
            value = normalized_headers.get(str(name).lower(), "").strip()
            if value:
                return value, f"header:{name}", False

        for name in query_names or []:
            value = str(normalized_query.get(str(name), "")).strip()
            if value:
                return value, f"query:{name}", False

        match_target = self._normalize_target(target_host, target_path)
        matched_rule = self._select_rule(match_target, rules or [])
        if matched_rule is not None:
            prefix = str(matched_rule.get("url_prefix") or "")
            for name in matched_rule.get("headers") or []:
                value = normalized_headers.get(str(name).lower(), "").strip()
                if value:
                    return value, f"rule:{prefix}:{name}", False

        return "", "missing", True

    def _normalize_target(self, target_host: str, target_path: str) -> str:
        host = str(target_host or "").strip().strip("/")
        path = str(target_path or "").strip()
        if not path:
            return host
        return f"{host}/{path.lstrip('/')}".rstrip("/")

    def _select_rule(self, match_target: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
        best_rule: dict[str, Any] | None = None
        best_length = -1
        for rule in rules:
            prefix = str(rule.get("url_prefix") or "").strip().strip("/")
            if not prefix:
                continue
            if not self._matches_prefix(match_target, prefix):
                continue
            if len(prefix) > best_length:
                best_rule = rule
                best_length = len(prefix)
        return best_rule

    def _matches_prefix(self, match_target: str, prefix: str) -> bool:
        return match_target == prefix or match_target.startswith(prefix + "/")

    def _first_value(self, value: Any) -> str:
        if isinstance(value, (list, tuple)):
            for item in value:
                text = str(item or "").strip()
                if text:
                    return text
            return ""
        return str(value or "")
