import unittest

from proxypool.api.security import is_api_key_required, is_request_authorized


class TestApiSecurity(unittest.TestCase):
    def test_health_and_read_routes_do_not_require_key(self) -> None:
        self.assertFalse(is_api_key_required("GET", "/api/health"))
        self.assertFalse(is_api_key_required("GET", "/api/stats"))
        self.assertFalse(is_api_key_required("GET", "/api/proxies"))
        self.assertFalse(is_api_key_required("GET", "/api/subscription"))
        self.assertFalse(is_api_key_required("GET", "/api/backend/status"))
        self.assertFalse(is_api_key_required("GET", "/api/backend/routes"))
        self.assertFalse(is_api_key_required("GET", "/api/backend/default-port-range"))
        self.assertFalse(is_api_key_required("GET", "/api/backend/latency"))
        self.assertFalse(is_api_key_required("GET", "/api/backend/process-events"))
        self.assertFalse(is_api_key_required("GET", "/api/subscriptions"))
        self.assertFalse(is_api_key_required("GET", "/api/subscription-update-proxy"))
        self.assertFalse(is_api_key_required("GET", "/api/tasks"))
        self.assertFalse(is_api_key_required("GET", "/api/tasks/abc123"))

    def test_mutation_routes_require_key(self) -> None:
        self.assertTrue(is_api_key_required("POST", "/api/collector/import-output"))
        self.assertTrue(is_api_key_required("POST", "/api/tester/run"))
        self.assertTrue(is_api_key_required("POST", "/api/backend/start"))

    def test_authorization_logic(self) -> None:
        self.assertTrue(is_request_authorized("GET", "/api/health", "", None))
        self.assertTrue(is_request_authorized("POST", "/api/tester/run", "", ""))
        self.assertFalse(is_request_authorized("POST", "/api/tester/run", "", "secret"))
        self.assertTrue(is_request_authorized("POST", "/api/tester/run", "secret", "secret"))


if __name__ == "__main__":
    unittest.main()
