import socket

import pytest


@pytest.fixture(autouse=True)
def _mock_dns(monkeypatch):
    # Route-level tests exercise reject_private_hosts(), which calls
    # socket.getaddrinfo() for real. Fake it here so the default test suite
    # never needs actual network/DNS access; test_security.py overrides this
    # per-test to exercise the private/public IP branches specifically.
    def _fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
