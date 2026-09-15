from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from .naming import normalize_model
from .sources import Source, serializable
from .validation import validate_public_url

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.items=[]
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag in {"img", "source"} and values.get("src"): self.items.append((values["src"], "image", " ".join((values.get("alt", ""), values.get("title", "")))))
        if tag == "a" and values.get("href"): self.items.append((values["href"], "auto", " ".join((values.get("title", ""), values.get("aria-label", "")))))

def association_evidence(text: str, model: str, all_models: list[str]) -> tuple[bool, str]:
    normalized = normalize_model(text); wanted = normalize_model(model)
    hits = [item for item in all_models if normalize_model(item) and normalize_model(item) in normalized]
    exact = wanted in normalized
    if len({normalize_model(x) for x in hits}) > 1: return False, "MODEL_AMBIGUOUS"
    return (True, "") if exact else (False, "MODEL_UNKNOWN")

def discover(sources: list[Source], transport, max_bytes: int) -> list[dict]:
    models=[s.model for s in sources if s.model]
    candidates=[]
    for source in sources:
        if not source.enabled: continue
        if source.asset_url:
            candidates.append({**serializable(source), "url":source.asset_url, "approved":bool(source.model), "reason":"" if source.model else "MODEL_UNKNOWN"})
        if not source.page_url: continue
        validate_public_url(source.page_url, transport.resolve)
        response=transport.get(source.page_url, headers={}, timeout=30, max_bytes=max_bytes)
        validate_public_url(response.final_url, transport.resolve)
        if response.status != 200 or len(response.body)>max_bytes: continue
        parser=Links(); parser.feed(response.body.decode("utf-8", "replace"))
        for raw, hint, context in parser.items:
            url=urljoin(response.final_url, raw); suffix=urlsplit(url).path.lower()
            kind="technical_sheet" if suffix.endswith(".pdf") else hint
            if kind == "auto" and not suffix.endswith((".jpg", ".jpeg", ".png", ".webp")): continue
            if any(word in (url+context).lower() for word in ("logo", "icon", "banner", "favicon", "navigation")): continue
            ok, reason=association_evidence(url+" "+context, source.model, models)
            candidates.append({**serializable(source), "url":url, "asset_type":kind, "approved":ok, "reason":reason})
    return sorted(candidates, key=lambda x:(x["priority"],x["target_brand"],x["model"],x["url"]))
