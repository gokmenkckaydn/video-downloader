from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from video_downloader.core.errors import InvalidUrlError


def reject_private_hosts(url: str) -> None:
    """Blocks SSRF: this endpoint makes a server-side request to a
    user-supplied URL, so a host resolving to loopback/private/link-local
    space (e.g. cloud metadata endpoints, internal services) must be refused
    before yt-dlp ever touches it.
    """
    host = urlparse(url).hostname
    if not host:
        raise InvalidUrlError("The URL is missing a host.")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as error:
        raise InvalidUrlError(f"Could not resolve host '{host}'.") from error
    for info in infos:
        raw_addr = info[4][0]
        addr = ipaddress.ip_address(raw_addr.split("%", 1)[0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            raise InvalidUrlError(
                f"URLs resolving to private/internal addresses are not allowed ('{host}' -> '{raw_addr}')."
            )
