"""Fail-closed robots policy parsed exclusively from injected bytes."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import quote,unquote,urlsplit
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

def _longest_match(parser: RobotFileParser, user_agent: str, target_url: str):
    """Apply RFC longest-match precedence to the group selected by RobotFileParser.

    RobotFileParser's public ``can_fetch`` stops at the first matching rule, so a broad
    Allow placed before a narrower Disallow can incorrectly authorize a URL.
    """
    entry=next((item for item in parser.entries if item.applies_to(user_agent)),None)
    if entry is None: entry=parser.default_entry
    if entry is None: return True,None
    path=urlsplit(quote(unquote(target_url))).path
    matches=[rule for rule in entry.rulelines if rule.applies_to(path)]
    if not matches: return True,None
    longest=max(len(rule.path) for rule in matches)
    selected=[rule for rule in matches if len(rule.path)==longest]
    # At equal specificity Allow wins, as required by the robots exclusion protocol.
    rule=next((item for item in selected if item.allowance),selected[0])
    directive="Allow" if rule.allowance else "Disallow"
    return rule.allowance,f"{directive}: {rule.path}"

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
        rules=[line.split(":",1)[1].strip() for line in text.splitlines()
            if ":" in line and line.split(":",1)[0].strip().casefold() in ("allow","disallow")]
        if any("*" in rule or "$" in rule for rule in rules):
            raise ValueError("unsupported robots path pattern")
        parser=RobotFileParser(); parser.set_url(robots_url); parser.parse(text.splitlines())
        allowed,applicable=_longest_match(parser,user_agent,target_url)
        sitemaps=tuple(x for x in (parser.site_maps() or ()) if urlsplit(x).scheme=="https")
        return RobotsDecision(**common,state="allowed" if allowed else "disallowed",applicable_rule=applicable,allowed=allowed,sitemaps=sitemaps)
    except (UnicodeError,ValueError) as exc:
        return RobotsDecision(**common,state="parse_failed",applicable_rule=None,allowed=False,detail=str(exc))
