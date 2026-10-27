"""The slowapi key function: the real client IP behind Render, and nothing a caller can forge.
No network, no Groq. Run from the repo root:  .venv/bin/python -m unittest tests.test_rate_limit_key -v"""
import os
import unittest
from types import SimpleNamespace

from cryptography.fernet import Fernet

# main/jira_oauth fail fast without these; fake values are fine, and setdefault
# leaves any real ones alone.
for _name, _value in {
    "JIRA_CLIENT_ID": "test-id",
    "JIRA_CLIENT_SECRET": "test-secret",
    "JIRA_REDIRECT_URI": "http://localhost:8000/api/jira/callback",
    "FRONTEND_ORIGIN": "http://localhost:8000",
    "SESSION_SECRET": Fernet.generate_key().decode(),
    "APP_ENV": "local",
    "GROQ_API_KEY": "test-groq-key",
}.items():
    os.environ.setdefault(_name, _value)

import main  # noqa: E402

PROXY = "10.0.0.7"  # what request.client.host is behind Render: the proxy, the same for every visitor


def fake_request(headers=None, client_host=PROXY):
    """Just what the key function reads: .headers (case-insensitive get) and .client.host."""
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    return SimpleNamespace(
        headers=SimpleNamespace(get=lambda name, default=None: lowered.get(name.lower(), default)),
        client=SimpleNamespace(host=client_host) if client_host else None,
    )


class ClientIpKey(unittest.TestCase):
    def test_the_limiter_uses_this_key_function(self):
        self.assertIs(main.limiter._key_func, main.client_ip_key)

    def test_cf_connecting_ip_present_gives_that_ip(self):
        self.assertEqual(main.client_ip_key(fake_request({"CF-Connecting-IP": "203.0.113.9"})), "203.0.113.9")

    def test_header_name_is_case_insensitive_and_whitespace_is_trimmed(self):
        self.assertEqual(main.client_ip_key(fake_request({"cf-connecting-ip": "  203.0.113.9 "})), "203.0.113.9")

    def test_ipv6_is_normalised_so_one_visitor_is_one_key(self):
        a = main.client_ip_key(fake_request({"CF-Connecting-IP": "2001:DB8:0:0:0:0:0:1"}))
        b = main.client_ip_key(fake_request({"CF-Connecting-IP": "2001:db8::1"}))
        self.assertEqual(a, b)
        self.assertEqual(a, "2001:db8::1")

    def test_header_absent_gives_client_host(self):
        self.assertEqual(main.client_ip_key(fake_request()), PROXY)
        self.assertEqual(main.client_ip_key(fake_request(client_host="127.0.0.1")), "127.0.0.1")

    def test_no_client_at_all_keeps_slowapis_own_fallback(self):
        self.assertEqual(main.client_ip_key(fake_request(client_host=None)), "127.0.0.1")

    def test_a_forged_x_forwarded_for_is_ignored(self):
        forged = {"X-Forwarded-For": "198.51.100.66, 192.0.2.1"}
        self.assertEqual(main.client_ip_key(fake_request(forged)), PROXY)                         # header absent: client.host
        both = dict(forged, **{"CF-Connecting-IP": "203.0.113.9"})
        self.assertEqual(main.client_ip_key(fake_request(both)), "203.0.113.9")                   # header present: CF wins

    def test_two_visitors_behind_the_same_proxy_get_different_keys(self):
        one = main.client_ip_key(fake_request({"CF-Connecting-IP": "203.0.113.9"}))
        two = main.client_ip_key(fake_request({"CF-Connecting-IP": "203.0.113.10"}))
        self.assertNotEqual(one, two)

    def test_a_value_that_is_not_an_ip_never_becomes_a_key(self):
        for bad in ("not-an-ip", "1.2.3.4, 5.6.7.8", "203.0.113.9; drop table", "", "999.1.1.1"):
            self.assertEqual(main.client_ip_key(fake_request({"CF-Connecting-IP": bad})), PROXY, repr(bad))


if __name__ == "__main__":
    unittest.main()
