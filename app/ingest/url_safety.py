from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


def _is_bad_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True

    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_safe_fetch_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"}:
        raise UnsafeUrlError(f"Unsupported URL scheme: {p.scheme}")
    if not p.hostname:
        raise UnsafeUrlError("URL is missing hostname")

    host = p.hostname

    # If host is an IP literal
    try:
        ipaddress.ip_address(host)
        if _is_bad_ip(host):
            raise UnsafeUrlError("IP address is not allowed")
        return
    except ValueError:
        pass

    # Resolve hostname
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeUrlError(f"DNS resolution failed for host {host}: {e}") from e

    for info in infos:
        ip = info[4][0]
        if _is_bad_ip(ip):
            raise UnsafeUrlError(f"Hostname resolves to disallowed IP: {ip}")
