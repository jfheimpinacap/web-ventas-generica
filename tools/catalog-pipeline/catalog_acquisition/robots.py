"""Fail-closed robots policy parsed exclusively from injected bytes."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

@dataclass(frozen=True)
class RobotsDecision:
    url: str; state: str; http_status: int | None; sha256: str | None
    fetched_at: str; user_agent: str; applicable_rule: str | None
    allowed: bool; sitemaps: tuple[str,...] = (); detail: str = ""

def permits_catalog(decision: RobotsDecision) -> bool:
    """Only an explicit allow or a genuine 404/410 absence opens the gate."""
    return (decision.state == "allowed" and decision.allowed) or (
        decision.state == "not_found" and decision.http_status in (404, 410) and decision.allowed)

def evaluate(*, robots_url: str, status: int | None, body: bytes | None, target_url: str,
             user_agent: str, fetched_at: str, fetch_error: str | None = None) -> RobotsDecision:
    digest=sha256(body).hexdigest() if body is not None else None
    common=dict(url=robots_url,http_status=status,sha256=digest,fetched_at=fetched_at,user_agent=user_agent)
    if fetch_error: return RobotsDecision(**common,state="fetch_failed",applicable_rule=None,allowed=False,detail=fetch_error)
    if status in (404,410): return RobotsDecision(**common,state="not_found",applicable_rule=None,allowed=True)
    if status in (401,403) or status is None or status >= 500:
        return RobotsDecision(**common,state="unknown",applicable_rule=None,allowed=False,detail="robots response is not authoritative")
    if status != 200 or body is None:
        return RobotsDecision(**common,state="unknown",applicable_rule=None,allowed=False,detail="unexpected robots response")
    try:
        text=body.decode("utf-8-sig",errors="strict")
        if "\x00" in text: raise ValueError("NUL in robots")
        parser=RobotFileParser(); parser.set_url(robots_url); parser.parse(text.splitlines())
        allowed=parser.can_fetch(user_agent,target_url)
        sitemaps=tuple(x for x in (parser.site_maps() or ()) if urlsplit(x).scheme=="https")
        path=urlsplit(target_url).path
        applicable=next((line.strip() for line in text.splitlines() if line.strip().lower().startswith(("allow:","disallow:")) and line.split(":",1)[1].strip() and path.startswith(line.split(":",1)[1].strip())),None)
        return RobotsDecision(**common,state="allowed" if allowed else "disallowed",applicable_rule=applicable,allowed=allowed,sitemaps=sitemaps)
    except (UnicodeError,ValueError) as exc:
        return RobotsDecision(**common,state="parse_failed",applicable_rule=None,allowed=False,detail=str(exc))
