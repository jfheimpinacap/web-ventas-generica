"""Fail-closed robots policy evaluated exclusively from injected bytes."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit

@dataclass(frozen=True)
class RobotsDecision:
    url: str; state: str; http_status: int | None; sha256: str | None
    fetched_at: str; user_agent: str; applicable_rule: str | None
    allowed: bool; sitemaps: tuple[str,...] = (); detail: str = ""
    applicable_group: tuple[str,...] = ()

def permits_catalog(decision: RobotsDecision) -> bool:
    """Only an explicit allow or a genuine 404/410 absence opens the gate."""
    return (decision.state == "allowed" and decision.allowed) or (
        decision.state == "not_found" and decision.http_status in (404, 410) and decision.allowed)

def _parse(text: str) -> tuple[list[tuple[tuple[str,...],tuple[tuple[bool,str],...]]],tuple[str,...]]:
    """Parse the deliberately small, auditable robots subset or reject it."""
    groups=[]; agents=[]; rules=[]; sitemaps=[]
    def finish():
        nonlocal agents,rules
        if agents: groups.append((tuple(agents),tuple(rules)))
        agents=[]; rules=[]
    for raw in text.splitlines():
        line=raw.split("#",1)[0].strip()
        if not line: continue
        if ":" not in line: raise ValueError("robots directive is missing ':'")
        name,value=(part.strip() for part in line.split(":",1)); directive=name.casefold()
        if not name: raise ValueError("empty robots directive")
        if directive == "user-agent":
            if not value: raise ValueError("empty user-agent")
            if rules: finish()
            agents.append(value.casefold())
        elif directive in ("allow","disallow"):
            if not agents: raise ValueError("robots rule without user-agent")
            if not value:
                if directive == "disallow": continue
                raise ValueError("empty allow rule")
            if not value.startswith("/"): raise ValueError("robots path must be absolute")
            if "*" in value or "$" in value: raise ValueError("unsupported robots path pattern")
            rules.append((directive == "allow",value))
        elif directive == "sitemap":
            if not value: raise ValueError("empty sitemap")
            if urlsplit(value).scheme == "https": sitemaps.append(value)
        else:
            # Extension directives cannot silently acquire authorization semantics.
            raise ValueError(f"unsupported robots directive: {name}")
    finish()
    if not groups: raise ValueError("robots contains no user-agent group")
    return groups,tuple(sitemaps)

def _select(groups, user_agent: str, target_url: str):
    ua=user_agent.casefold()
    candidates=[]
    for agents,rules in groups:
        matches=[token for token in agents if token == "*" or token in ua]
        if matches: candidates.append((max(0 if token == "*" else len(token) for token in matches),agents,rules))
    if not candidates: return True,None,()
    specificity=max(item[0] for item in candidates)
    selected=[item for item in candidates if item[0] == specificity]
    applicable_group=tuple(token for _,agents,_ in selected for token in agents)
    path=urlsplit(target_url).path or "/"
    matches=[rule for _,_,rules in selected for rule in rules if path.startswith(rule[1])]
    if not matches: return True,None,applicable_group
    longest=max(len(rule[1]) for rule in matches)
    tied=[rule for rule in matches if len(rule[1]) == longest]
    winner=next((rule for rule in tied if rule[0]),tied[0])
    directive="Allow" if winner[0] else "Disallow"
    return winner[0],f"{directive}: {winner[1]}",applicable_group

def evaluate(*, robots_url: str, status: int | None, body: bytes | None, target_url: str,
             user_agent: str, fetched_at: str, fetch_error: str | None = None) -> RobotsDecision:
    """Return one deterministic decision for the supplied response and exact target."""
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
        groups,sitemaps=_parse(text)
        allowed,applicable,applicable_group=_select(groups,user_agent,target_url)
        return RobotsDecision(**common,state="allowed" if allowed else "disallowed",
            applicable_rule=applicable,allowed=allowed,sitemaps=sitemaps,
            applicable_group=applicable_group)
    except (UnicodeError,ValueError) as exc:
        return RobotsDecision(**common,state="parse_failed",applicable_rule=None,allowed=False,detail=str(exc))
