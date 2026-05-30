"""Additional tests for proxypool.collector.parser to improve coverage."""
import base64
import json
import unittest

from proxypool.collector.parser import (
    ParseError,
    _first,
    _looks_like_base64,
    _looks_like_clash_yaml,
    _pad_b64,
    _safe_b64_decode_to_text,
    _split_host_port,
    _to_port,
    parse_proxy_link,
    parse_source_content,
)


class TestFormatDetection(unittest.TestCase):
    def test_clash_yaml_by_extension_yaml(self) -> None:
        self.assertTrue(_looks_like_clash_yaml("anything", "foo.yaml"))

    def test_clash_yaml_by_extension_yml(self) -> None:
        self.assertTrue(_looks_like_clash_yaml("anything", "foo.yml"))

    def test_clash_yaml_by_content(self) -> None:
        content = "proxies:\n  - type: ss\n    server: 1.2.3.4"
        self.assertTrue(_looks_like_clash_yaml(content, ""))

    def test_not_clash_yaml(self) -> None:
        self.assertFalse(_looks_like_clash_yaml("random text", "foo.txt"))

    def test_base64_detect_valid(self) -> None:
        # 12+ chars, all valid base64 chars
        payload = "dGVzdHBhZGRpbmcxMjM="
        self.assertTrue(_looks_like_base64(payload))

    def test_base64_too_short(self) -> None:
        self.assertFalse(_looks_like_base64("short"))

    def test_base64_invalid_chars(self) -> None:
        self.assertFalse(_looks_like_base64("not@valid#base64!here"))


class TestHelpers(unittest.TestCase):
    def test_to_port_valid(self) -> None:
        self.assertEqual(_to_port(443), 443)
        self.assertEqual(_to_port("8080"), 8080)

    def test_to_port_none_and_empty(self) -> None:
        self.assertIsNone(_to_port(None))
        self.assertIsNone(_to_port(""))

    def test_to_port_zero(self) -> None:
        self.assertIsNone(_to_port(0))

    def test_to_port_negative(self) -> None:
        self.assertIsNone(_to_port(-1))

    def test_to_port_over_max(self) -> None:
        self.assertIsNone(_to_port(99999))

    def test_to_port_non_numeric(self) -> None:
        self.assertIsNone(_to_port("abc"))

    def test_to_port_float(self) -> None:
        # int(3.14) truncates to 3 without raising, so _to_port returns 3
        self.assertEqual(_to_port(3.14), 3)

    def test_first_none(self) -> None:
        self.assertEqual(_first(None), "")

    def test_first_empty(self) -> None:
        self.assertEqual(_first([]), "")

    def test_first_with_value(self) -> None:
        self.assertEqual(_first(["a", "b"]), "a")

    def test_pad_b64(self) -> None:
        self.assertEqual(_pad_b64("dGVzdA"), "dGVzdA==")

    def test_pad_b64_already_padded(self) -> None:
        self.assertEqual(_pad_b64("dGVzdA=="), "dGVzdA==")

    def test_safe_b64_decode_valid(self) -> None:
        result = _safe_b64_decode_to_text(base64.b64encode(b"hello").decode())
        self.assertEqual(result, "hello")

    def test_safe_b64_decode_invalid(self) -> None:
        result = _safe_b64_decode_to_text("not-valid-base64!!!")
        self.assertEqual(result, "")

    def test_safe_b64_decode_with_url_safe_chars(self) -> None:
        encoded = base64.urlsafe_b64encode(b"test-data").decode()
        result = _safe_b64_decode_to_text(encoded)
        self.assertEqual(result, "test-data")

    def test_split_host_port_valid(self) -> None:
        host, port = _split_host_port("example.com:8080")
        self.assertEqual(host, "example.com")
        self.assertEqual(port, 8080)

    def test_split_host_port_missing(self) -> None:
        with self.assertRaises(ParseError):
            _split_host_port("noport")


class TestParseProxyLinkErrors(unittest.TestCase):
    def test_missing_scheme(self) -> None:
        with self.assertRaises(ParseError):
            parse_proxy_link("no-scheme-here")

    def test_unsupported_scheme(self) -> None:
        with self.assertRaises(ParseError):
            parse_proxy_link("wireguard://host:51820")

    def test_parse_error_reraised(self) -> None:
        # unsupported scheme -> ParseError
        with self.assertRaises(ParseError):
            parse_proxy_link("ftp://example.com")


class TestParseVmessErrors(unittest.TestCase):
    def test_vmess_invalid_base64(self) -> None:
        with self.assertRaises(ParseError):
            parse_proxy_link("vmess://!!!invalid!!!")

    def test_vmess_invalid_json(self) -> None:
        # valid base64 but not valid JSON
        payload = base64.b64encode(b"not json").decode()
        with self.assertRaises(ParseError):
            parse_proxy_link(f"vmess://{payload}")

    def test_vmess_missing_host(self) -> None:
        data = {"port": "443"}
        payload = base64.b64encode(json.dumps(data).encode()).decode()
        with self.assertRaises(ParseError):
            parse_proxy_link(f"vmess://{payload}")

    def test_vmess_missing_port(self) -> None:
        data = {"add": "example.com"}
        payload = base64.b64encode(json.dumps(data).encode()).decode()
        with self.assertRaises(ParseError):
            parse_proxy_link(f"vmess://{payload}")

    def test_vmess_invalid_port(self) -> None:
        data = {"add": "example.com", "port": "notaport"}
        payload = base64.b64encode(json.dumps(data).encode()).decode()
        with self.assertRaises(ParseError):
            parse_proxy_link(f"vmess://{payload}")

    def test_vmess_json_direct(self) -> None:
        """vmess link with inline JSON (no base64)."""
        data = {"add": "direct.com", "port": "443", "ps": "direct", "id": "aaa", "net": "tcp"}
        link = "vmess://" + json.dumps(data)
        node = parse_proxy_link(link)
        self.assertEqual(node.host, "direct.com")

    def test_vmess_uses_host_fallback(self) -> None:
        """vmess falls back to 'host' key when 'add' is absent."""
        data = {"host": "fallback.com", "port": "443", "id": "bbb"}
        payload = base64.b64encode(json.dumps(data).encode()).decode()
        node = parse_proxy_link(f"vmess://{payload}")
        self.assertEqual(node.host, "fallback.com")


class TestParseSS(unittest.TestCase):
    def test_ss_with_query_string(self) -> None:
        cred = base64.urlsafe_b64encode(b"aes-128-gcm:pass").decode().rstrip("=")
        link = f"ss://{cred}@1.2.3.4:8388?plugin=some-plugin#ss-q"
        node = parse_proxy_link(link)
        self.assertEqual(node.protocol, "ss")
        self.assertIn("plugin", node.extra)

    def test_ss_without_at_base64_payload(self) -> None:
        """ss link encoded as full base64 payload (no @ in the encoded part)."""
        inner = "aes-128-gcm:password@1.2.3.4:8388"
        payload = base64.b64encode(inner.encode()).decode()
        link = f"ss://{payload}"
        node = parse_proxy_link(link)
        self.assertEqual(node.host, "1.2.3.4")
        self.assertEqual(node.port, 8388)

    def test_ss_invalid_b64_payload_no_at(self) -> None:
        """Full base64 payload that doesn't contain @ after decode."""
        inner = "aes-128-gcm:password"
        payload = base64.b64encode(inner.encode()).decode()
        with self.assertRaises(ParseError):
            parse_proxy_link(f"ss://{payload}")

    def test_ss_userinfo_base64_with_at(self) -> None:
        """Userinfo is base64-encoded but host:port follows @."""
        encoded_userinfo = base64.b64encode(b"method:pwd").decode()
        link = f"ss://{encoded_userinfo}@host.example.com:1080"
        node = parse_proxy_link(link)
        self.assertEqual(node.host, "host.example.com")
        self.assertEqual(node.port, 1080)

    def test_ss_userinfo_b64_invalid_no_colon(self) -> None:
        """Base64 userinfo decodes but has no colon -> invalid."""
        encoded_userinfo = base64.b64encode(b"nocolon").decode()
        with self.assertRaises(ParseError):
            parse_proxy_link(f"ss://{encoded_userinfo}@host.com:1080")

    def test_ss_plain_text_userinfo_no_colon(self) -> None:
        """Plain text userinfo without colon separator."""
        with self.assertRaises(ParseError):
            parse_proxy_link("ss://nocolon@host.com:1080")


class TestParseSSR(unittest.TestCase):
    def test_ssr_invalid_payload(self) -> None:
        with self.assertRaises(ParseError):
            parse_proxy_link("ssr://!!!bad!!!")

    def test_ssr_too_few_fields(self) -> None:
        """ssr with fewer than 6 colon-separated fields."""
        raw = "server:port:proto"
        encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        with self.assertRaises(ParseError):
            parse_proxy_link(f"ssr://{encoded}")

    def test_ssr_invalid_port(self) -> None:
        password_b64 = base64.urlsafe_b64encode(b"pwd").decode().rstrip("=")
        raw = f"server:notaport:origin:aes-256-cfb:plain:{password_b64}"
        encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        with self.assertRaises(ParseError):
            parse_proxy_link(f"ssr://{encoded}")

    def test_ssr_without_query(self) -> None:
        """ssr with no /?remarks= query string."""
        password_b64 = base64.urlsafe_b64encode(b"pwd").decode().rstrip("=")
        raw = f"1.2.3.4:5678:origin:aes-128-ctr:plain:{password_b64}"
        encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        node = parse_proxy_link(f"ssr://{encoded}")
        self.assertEqual(node.protocol, "ssr")
        self.assertEqual(node.port, 5678)
        self.assertEqual(node.name, "")


class TestParseUrlLike(unittest.TestCase):
    def test_trojan_default_port(self) -> None:
        node = parse_proxy_link("trojan://pwd@example.com#t1")
        self.assertEqual(node.port, 443)

    def test_vless_default_port(self) -> None:
        node = parse_proxy_link("vless://uuid@v.example.com#v1")
        self.assertEqual(node.port, 443)

    def test_hysteria_default_port(self) -> None:
        node = parse_proxy_link("hysteria://pwd@h.example.com#h1")
        self.assertEqual(node.port, 443)

    def test_hysteria2_default_port(self) -> None:
        node = parse_proxy_link("hysteria2://pwd@h2.example.com#h2")
        self.assertEqual(node.port, 443)

    def test_hy2_default_port(self) -> None:
        node = parse_proxy_link("hy2://pwd@hy2.example.com#hy2")
        self.assertEqual(node.port, 443)

    def test_http_default_port(self) -> None:
        node = parse_proxy_link("http://user@http.example.com#http1")
        self.assertEqual(node.port, 80)

    def test_socks_default_port(self) -> None:
        node = parse_proxy_link("socks://user@socks.example.com#s1")
        self.assertEqual(node.port, 1080)

    def test_socks5_default_port(self) -> None:
        node = parse_proxy_link("socks5://user@s5.example.com#s5")
        self.assertEqual(node.port, 1080)

    def test_snell_default_port(self) -> None:
        node = parse_proxy_link("snell://pwd@sn.example.com#sn1")
        self.assertEqual(node.port, 443)

    def test_missing_host(self) -> None:
        with self.assertRaises(ParseError):
            parse_proxy_link("http://:8080")

    def test_socks_with_password(self) -> None:
        node = parse_proxy_link("socks://user:pass@host.com:1080")
        self.assertEqual(node.extra.get("password"), "pass")

    def test_https_protocol_normalized(self) -> None:
        node = parse_proxy_link("https://user@secure.com:443")
        self.assertEqual(node.protocol, "http")


class TestParseSourceContent(unittest.TestCase):
    def test_bom_handling(self) -> None:
        """Content with BOM should still parse correctly."""
        vmess = {
            "add": "bom.com", "port": "443", "id": "aaa", "net": "tcp"
        }
        encoded = base64.b64encode(json.dumps(vmess).encode()).decode()
        content = "﻿vmess://" + encoded
        nodes, invalid = parse_source_content(content)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].host, "bom.com")

    def test_comment_lines_skipped(self) -> None:
        content = "# this is a comment\nhttp://u@h.com:80#n"
        nodes, invalid = parse_source_content(content)
        self.assertEqual(len(nodes), 1)

    def test_empty_lines_skipped(self) -> None:
        content = "\n\n\n"
        nodes, invalid = parse_source_content(content)
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 0)

    def test_base64_encoded_list(self) -> None:
        """Content that is base64-encoded containing proxy links."""
        inner = "trojan://pwd@test.com:443#b64-node"
        encoded = base64.b64encode(inner.encode()).decode()
        nodes, invalid = parse_source_content(encoded)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].host, "test.com")

    def test_base64_without_protocol(self) -> None:
        """Base64 content that decodes but has no ://."""
        encoded = base64.b64encode(b"just some text without protocol").decode()
        nodes, invalid = parse_source_content(encoded)
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 1)

    def test_invalid_proxy_link_in_inline(self) -> None:
        """Inline link that fails parsing goes to invalid list."""
        content = "wireguard://bad:1234"
        nodes, invalid = parse_source_content(content)
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 1)


class TestClashYAML(unittest.TestCase):
    def test_empty_proxies_list(self) -> None:
        yaml_text = "proxies: []"
        nodes, invalid = parse_source_content(yaml_text, source_name="empty.yaml")
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 0)

    def test_no_proxies_key(self) -> None:
        yaml_text = "other_key: []"
        nodes, invalid = parse_source_content(yaml_text, source_name="no.yaml")
        self.assertEqual(len(nodes), 0)

    def test_non_dict_item_in_proxies(self) -> None:
        yaml_text = "proxies:\n  - 42\n  - name: ok\n    type: trojan\n    server: s.com\n    port: 443\n    password: p"
        nodes, invalid = parse_source_content(yaml_text, source_name="mixed.yaml")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(len(invalid), 1)

    def test_invalid_protocol_in_proxies(self) -> None:
        """Proxy item with unknown type -> invalid."""
        yaml_text = 'proxies:\n  - name: x\n    type: wireguard\n    server: s.com\n    port: 443'
        nodes, invalid = parse_source_content(yaml_text, source_name="bad.yaml")
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 1)

    def test_missing_host_in_proxies(self) -> None:
        yaml_text = 'proxies:\n  - name: x\n    type: ss\n    server: ""\n    port: 443'
        nodes, invalid = parse_source_content(yaml_text, source_name="missing.yaml")
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 1)

    def test_missing_port_in_proxies(self) -> None:
        yaml_text = 'proxies:\n  - name: x\n    type: ss\n    server: s.com\n    port: null'
        nodes, invalid = parse_source_content(yaml_text, source_name="nport.yaml")
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 1)

    def test_clash_type_hy2_normalized(self) -> None:
        yaml_text = 'proxies:\n  - name: h\n    type: hy2\n    server: h.com\n    port: 443'
        nodes, _ = parse_source_content(yaml_text, source_name="h.yaml")
        self.assertEqual(nodes[0].protocol, "hysteria2")

    def test_clash_type_socks_normalized(self) -> None:
        yaml_text = 'proxies:\n  - name: s\n    type: socks5\n    server: s.com\n    port: 1080'
        nodes, _ = parse_source_content(yaml_text, source_name="s.yaml")
        self.assertEqual(nodes[0].protocol, "socks")

    def test_clash_proxies_not_list(self) -> None:
        """When 'proxies' key exists but is not a list."""
        yaml_text = "proxies: not-a-list"
        nodes, invalid = parse_source_content(yaml_text, source_name="badlist.yaml")
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(invalid), 0)


if __name__ == "__main__":
    unittest.main()
