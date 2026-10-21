"""Schemeful same-site checks using the vendored Mozilla PSL, including private suffixes."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit


@lru_cache
def rules():
    exact, wildcard, exceptions = set(), set(), set()
    for line in (
        (Path(__file__).parent / "data/public_suffix_list.dat")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("!"):
            exceptions.add(line[1:].encode("idna").decode())
        elif line.startswith("*."):
            wildcard.add(line[2:].encode("idna").decode())
        else:
            exact.add(line.encode("idna").decode())
    return exact, wildcard, exceptions


def registrable(host):
    if not host or not host.isascii() or host.endswith("."):
        return None
    labels = host.lower().split(".")
    exact, wildcard, exceptions = rules()
    if len(labels) < 2 or labels[-1] not in exact:
        return None
    public = 1
    for index in range(len(labels)):
        suffix = ".".join(labels[index:])
        count = len(labels) - index
        if suffix in exceptions:
            public = count - 1
            break
        if suffix in exact or ".".join(labels[index + 1 :]) in wildcard:
            public = max(public, count)
    return ".".join(labels[-public - 1 :]) if len(labels) > public else None


def same_site_siblings(web, api, site):
    origins = [urlsplit(value) for value in (web, api)]
    return bool(site) and all(
        origin.scheme == "https"
        and origin.hostname
        and origin.username is None
        and not origin.path
        and not origin.query
        and not origin.fragment
        and origin.hostname.endswith("." + site)
        and registrable(origin.hostname) == site
        for origin in origins
    )
