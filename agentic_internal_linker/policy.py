"""Fail-closed URL and anchor policies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .models import CatalogEntry

UNSAFE_URL_CHARS_RE = re.compile(r"[\s\x00-\x1f\x7f\[\]()<>\"'\\]")
UTILITY_SEGMENTS = {
    "account",
    "cart",
    "checkout",
    "login",
    "logout",
    "privacy",
    "register",
    "search",
    "signin",
    "signup",
    "sitemap",
    "subscribe",
    "terms",
}
ANCHOR_BLACKLIST_RE = re.compile(
    r"\b(?:click here|here|learn more|read more|reference guide|supporting details|this)\b",
    re.IGNORECASE,
)


def normalize_host(host: str) -> str:
    return host.strip().rstrip(".").encode("idna").decode("ascii").lower()


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    hostname = normalize_host(parts.hostname or "")
    port = f":{parts.port}" if parts.port else ""
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (parts.scheme.lower(), f"{hostname}{port}", path, parts.query, parts.fragment)
    )


@dataclass(frozen=True, slots=True)
class URLPolicy:
    allowed_hosts: frozenset[str]
    allow_subdomains: bool = False
    allow_http: bool = False
    allow_homepage: bool = False

    @classmethod
    def from_base_url(
        cls,
        base_url: str,
        *,
        allow_subdomains: bool = False,
        allow_http: bool = False,
    ) -> URLPolicy:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("base_url must be an HTTP(S) origin without credentials")
        return cls(
            allowed_hosts=frozenset({normalize_host(parsed.hostname)}),
            allow_subdomains=allow_subdomains,
            allow_http=allow_http,
        )

    @classmethod
    def from_catalog(cls, catalog: list[CatalogEntry]) -> URLPolicy:
        hosts = {normalize_host(urlsplit(entry.url).hostname or "") for entry in catalog}
        hosts.discard("")
        if len(hosts) != 1:
            raise ValueError("base_url is required when catalog entries span multiple hosts")
        return cls(allowed_hosts=frozenset(hosts))

    def host_allowed(self, host: str) -> bool:
        normalized = normalize_host(host)
        if normalized in self.allowed_hosts:
            return True
        return self.allow_subdomains and any(
            normalized.endswith(f".{allowed}") for allowed in self.allowed_hosts
        )

    def validate_url(self, url: str) -> tuple[bool, str]:
        if not url or len(url) > 2_048 or UNSAFE_URL_CHARS_RE.search(url):
            return False, "URL is empty, too long, or contains unsafe characters"
        try:
            parsed = urlsplit(url)
            _ = parsed.port
        except (UnicodeError, ValueError):
            return False, "URL cannot be parsed safely"
        schemes = {"https"} | ({"http"} if self.allow_http else set())
        if parsed.scheme.lower() not in schemes:
            return False, "URL scheme is not allowed"
        if not parsed.hostname or parsed.username or parsed.password:
            return False, "URL hostname is missing or contains credentials"
        if not self.host_allowed(parsed.hostname):
            return False, "URL host is outside the configured site"
        segments = {segment.lower() for segment in parsed.path.split("/") if segment}
        if segments & UTILITY_SEGMENTS:
            return False, "URL targets a utility page"
        if not self.allow_homepage and parsed.path in {"", "/"}:
            return False, "Homepage links are disabled"
        return True, ""


def anchor_is_safe(anchor: str) -> bool:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", anchor)
    return 2 <= len(words) <= 6 and not ANCHOR_BLACKLIST_RE.search(anchor)


def validate_catalog(catalog: list[CatalogEntry], policy: URLPolicy) -> list[CatalogEntry]:
    if not catalog:
        raise ValueError("catalog must contain at least one entry")
    if len(catalog) > 10_000:
        raise ValueError("catalog cannot contain more than 10,000 entries")

    validated: list[CatalogEntry] = []
    seen: set[str] = set()
    for index, entry in enumerate(catalog):
        if not entry.title or len(entry.title) > 512 or len(entry.description) > 2_048:
            raise ValueError("catalog titles are required and field limits must be respected")
        ok, reason = policy.validate_url(entry.url)
        if not ok:
            raise ValueError(f"catalog entry {index} has an unsafe URL: {reason}")
        normalized = normalize_url(entry.url)
        if normalized not in seen:
            seen.add(normalized)
            validated.append(
                CatalogEntry(url=normalized, title=entry.title, description=entry.description)
            )
    return validated
