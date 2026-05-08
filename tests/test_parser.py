import base64
import json
import unittest

from proxypool.collector.parser import ParseError, parse_proxy_link, parse_source_content


class TestProxyParser(unittest.TestCase):
    def test_parse_vmess_base64(self) -> None:
        payload = {
            "v": "2",
            "ps": "vmess-node",
            "add": "example.com",
            "port": "443",
            "id": "11111111-1111-1111-1111-111111111111",
            "aid": "0",
            "net": "ws",
            "path": "/ws",
            "tls": "tls",
        }
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        node = parse_proxy_link(f"vmess://{encoded}")
        self.assertEqual(node.protocol, "vmess")
        self.assertEqual(node.host, "example.com")
        self.assertEqual(node.port, 443)
        self.assertEqual(node.name, "vmess-node")
        self.assertEqual(node.extra.get("uuid"), "11111111-1111-1111-1111-111111111111")

    def test_parse_ss_with_base64_userinfo(self) -> None:
        cred = base64.urlsafe_b64encode(b"aes-128-gcm:password").decode().rstrip("=")
        node = parse_proxy_link(f"ss://{cred}@127.0.0.1:8388#ss-node")
        self.assertEqual(node.protocol, "ss")
        self.assertEqual(node.host, "127.0.0.1")
        self.assertEqual(node.port, 8388)
        self.assertEqual(node.name, "ss-node")
        self.assertEqual(node.extra.get("cipher"), "aes-128-gcm")

    def test_parse_trojan(self) -> None:
        node = parse_proxy_link(
            "trojan://secret@example.org:443?security=tls&sni=example.org#trojan-node"
        )
        self.assertEqual(node.protocol, "trojan")
        self.assertEqual(node.host, "example.org")
        self.assertEqual(node.port, 443)
        self.assertEqual(node.name, "trojan-node")
        self.assertEqual(node.extra.get("password"), "secret")

    def test_parse_vless(self) -> None:
        node = parse_proxy_link(
            "vless://11111111-1111-1111-1111-111111111111@example.net:8443?encryption=none&security=tls&type=ws&path=%2Fvless#vless-node"
        )
        self.assertEqual(node.protocol, "vless")
        self.assertEqual(node.host, "example.net")
        self.assertEqual(node.port, 8443)
        self.assertEqual(node.extra.get("uuid"), "11111111-1111-1111-1111-111111111111")
        self.assertEqual(node.extra.get("security"), "tls")

    def test_parse_hysteria2(self) -> None:
        node = parse_proxy_link(
            "hysteria2://password@example.com:443?sni=example.com#hy2"
        )
        self.assertEqual(node.protocol, "hysteria2")
        self.assertEqual(node.host, "example.com")
        self.assertEqual(node.port, 443)
        self.assertEqual(node.name, "hy2")

    def test_parse_hysteria_and_snell(self) -> None:
        hy_node = parse_proxy_link("hysteria://pwd@example.com:8443?obfs=test#hy1")
        snell_node = parse_proxy_link("snell://secret@example.org:443#snell-node")
        self.assertEqual(hy_node.protocol, "hysteria")
        self.assertEqual(hy_node.port, 8443)
        self.assertEqual(snell_node.protocol, "snell")
        self.assertEqual(snell_node.host, "example.org")

    def test_parse_http_and_socks(self) -> None:
        http_node = parse_proxy_link("http://user:pass@10.0.0.1:8080#http-node")
        socks_node = parse_proxy_link("socks5://10.0.0.2:1080#socks-node")
        self.assertEqual(http_node.protocol, "http")
        self.assertEqual(socks_node.protocol, "socks")
        self.assertEqual(socks_node.port, 1080)

    def test_parse_ssr(self) -> None:
        # server:port:protocol:method:obfs:password_base64/?remarks=base64(name)
        password_b64 = base64.urlsafe_b64encode(b"pwd").decode().rstrip("=")
        remarks_b64 = base64.urlsafe_b64encode(b"ssr-node").decode().rstrip("=")
        raw = f"1.2.3.4:1234:origin:aes-256-cfb:plain:{password_b64}/?remarks={remarks_b64}"
        encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        node = parse_proxy_link(f"ssr://{encoded}")
        self.assertEqual(node.protocol, "ssr")
        self.assertEqual(node.host, "1.2.3.4")
        self.assertEqual(node.port, 1234)
        self.assertEqual(node.name, "ssr-node")

    def test_invalid_link_raises(self) -> None:
        with self.assertRaises(ParseError):
            parse_proxy_link("not-a-proxy-link")

    def test_parse_source_content_mixed(self) -> None:
        vmess_payload = {
            "v": "2",
            "ps": "node-x",
            "add": "a.com",
            "port": "443",
            "id": "22222222-2222-2222-2222-222222222222",
            "aid": "0",
            "net": "tcp",
        }
        vmess = "vmess://" + base64.b64encode(json.dumps(vmess_payload).encode()).decode()
        content = "\n".join([
            "invalid-line",
            vmess,
            "trojan://pwd@b.com:443#ok",
        ])
        nodes, invalid = parse_source_content(content)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(invalid), 1)

    def test_parse_clash_yaml(self) -> None:
        yaml_text = """
proxies:
  - name: ss-x
    type: ss
    server: 1.1.1.1
    port: 443
    cipher: aes-128-gcm
    password: pass
  - name: trojan-x
    type: trojan
    server: t.example.com
    port: 443
    password: abc
"""
        nodes, invalid = parse_source_content(yaml_text, source_name="x.yaml")
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(invalid), 0)
        self.assertEqual(nodes[0].protocol, "ss")
        self.assertEqual(nodes[1].protocol, "trojan")

    def test_parse_source_content_skips_invalid_ipv6_like_url(self) -> None:
        content = "\n".join(
            [
                "trojan://8r<[9'l6hAO#8ZQi@172.66.44.230:8443?allowInsecure=0&sni=Koma-YT.PAGeS.Dev&ws=1&wspath=%2Ftro8sFW1S91B6sZrM1%3Fed%3D2560#bad",
                "trojan://pwd@ok.example.com:443#ok",
            ]
        )
        nodes, invalid = parse_source_content(content)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].host, "ok.example.com")
        self.assertEqual(len(invalid), 1)


if __name__ == "__main__":
    unittest.main()
