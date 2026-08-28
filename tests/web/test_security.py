import socket

import pytest

from video_downloader.core.errors import InvalidUrlError
from video_downloader.web.security import reject_private_hosts


def _fake_getaddrinfo(addr):
    def _impl(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, 0))]

    return _impl


def test_reject_private_hosts_allows_public_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    reject_private_hosts("https://example.com/video")


@pytest.mark.parametrize(
    "addr",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "169.254.169.254",
        "172.16.0.1",
    ],
)
def test_reject_private_hosts_blocks_internal_addresses(monkeypatch, addr):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(addr))
    with pytest.raises(InvalidUrlError):
        reject_private_hosts("https://internal.example/video")


def test_reject_private_hosts_raises_on_dns_failure(monkeypatch):
    def _raise(host, port):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", _raise)
    with pytest.raises(InvalidUrlError):
        reject_private_hosts("https://does-not-resolve.invalid/video")
