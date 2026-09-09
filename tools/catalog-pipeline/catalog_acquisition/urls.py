"""Versioned technical URL canonicalisation and scope enforcement."""
from __future__ import annotations
import ipaddress
import re
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from .discovery import URL_RULE_VERSION, SourceDefinition
from .errors import PipelineError

TRACKING = frozenset({"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"})
class UnsafeUrlError(PipelineError): code = "UNSAFE_DISCOVERY_URL"

@dataclass(frozen=True)
class CanonicalUrl:
    original: str; materialized: str; canonical: str; stable_key: str; rule_version: str = URL_RULE_VERSION

def canonicalize(reference: str, *, base_url: str, source: SourceDefinition, require_scope: bool = True) -> CanonicalUrl:
    if reference.startswith(("//", "\\")):
        raise UnsafeUrlError("scheme-relative and UNC references are forbidden")
    materialized=urljoin(base_url, reference); parsed=urlsplit(materialized)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise UnsafeUrlError("HTTPS and a host are required", url=reference)
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("embedded credentials are forbidden")
    try: port=parsed.port
    except ValueError as exc: raise UnsafeUrlError("invalid port") from exc
    if port not in (None,443): raise UnsafeUrlError("only the default HTTPS port is allowed")
    host=parsed.hostname.lower().rstrip(".")
    try: ipaddress.ip_address(host)
    except ValueError: pass
    else: raise UnsafeUrlError("IP literals are forbidden")
    if host == "localhost" or host.endswith(".localhost") or host not in source.hosts:
        raise UnsafeUrlError("host is not allowlisted", host=host)
    if require_scope and not _allowed_path(source, parsed.path):
        raise UnsafeUrlError("path is outside the source catalog", path=parsed.path)
    query=urlencode([(k,v) for k,v in parse_qsl(parsed.query, keep_blank_values=True) if k.casefold() not in TRACKING], doseq=True)
    path=parsed.path or "/"; netloc=host
    canonical=urlunsplit(("https",netloc,path,query,""))
    return CanonicalUrl(reference,materialized,canonical,sha256((URL_RULE_VERSION+"\0"+canonical).encode()).hexdigest())

def _allowed_path(source: SourceDefinition, path: str) -> bool:
    if path == "/robots.txt": return True
    # Do not let an origin/proxy decode delimiters or dot segments after this gate.
    if re.search(r"%(?:2e|2f|5c|25)",path,re.IGNORECASE): return False
    prefix=source.path_prefix.rstrip("/")
    return path == prefix or path.startswith(prefix+"/")

def validate_redirect(location: str, current: str, source: SourceDefinition) -> CanonicalUrl:
    return canonicalize(location,base_url=current,source=source,require_scope=False)
