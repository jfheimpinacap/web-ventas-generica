from __future__ import annotations

import csv
import json
import re
import time
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .paths import atomic_write, safe_path
from .sources import COLUMNS
from .validation import validate_public_url

EP_START = "https://ep-equipment.com/es/productos/"
GAM_LISTINGS = tuple(
    "https://online.gamrentals.com/cl/826-ep" + (f"?page={page}" if page > 1 else "")
    for page in range(1, 5)
)
FAMILIES = {"SERIE X2", "SERIE X3", "SERIE X5", "SERIE F"}
CHECKPOINT_VERSION = {"format_version": 2, "parser_version": 3, "matcher_version": 2}
MODEL_FIELDS = ("target_brand", "model", "observed_title", "category", "official_model_name", "ep_listing_url", "ep_product_url", "gam_product_url", "ep_image_candidates", "ep_pdf_candidates", "missing_image", "missing_pdf", "gam_fallback_needed", "confidence", "status", "notes")
CANDIDATE_FIELDS = ("target_brand", "model", "category", "asset_type", "asset_role", "source_name", "source_role", "page_url", "asset_url", "expected_mime", "expected_extension", "language", "priority", "model_evidence", "confidence", "disposition", "http_status", "observed_mime", "validation_status", "notes")


class HarvestError(ValueError):
    """Stable, machine-readable harvest failure."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(json.dumps({"error": code, "detail": detail}, ensure_ascii=False, sort_keys=True))


def _key(value: str) -> str:
    value = value.strip().strip(".,;:()[]{}").upper()
    return re.sub(r"[\s\-‐‑‒–—]+", "", value)


def _model_pattern(model: str) -> re.Pattern[str]:
    pieces = [re.escape(piece) for piece in re.split(r"[\s\-‐‑‒–—]+", model.strip()) if piece]
    return re.compile(r"(?<![A-Z0-9])" + r"[\s\-‐‑‒–—]+".join(pieces) + r"(?![A-Z0-9\-‐‑‒–—])", re.IGNORECASE)


def reconcile_title(title: str, seed_rows: list[dict]) -> tuple[str | None, list[str]]:
    """Return one canonical model, or all conflicting candidates for audit."""
    found = []
    for row in sorted(seed_rows, key=lambda item: len(_key(item["canonical_candidate"])), reverse=True):
        model = row["canonical_candidate"]
        match = _model_pattern(model).search(title)
        if match:
            found.append((model, match.span(), _key(model)))
    if not found:
        return None, []
    best = found[0]
    compatible = all(
        candidate[2] in best[2] and candidate[1][0] >= best[1][0] and candidate[1][1] <= best[1][1]
        for candidate in found[1:]
    )
    return (best[0], []) if compatible else (None, [candidate[0] for candidate in found])


class PageParser(HTMLParser):
    """Small conservative parser; it records card-local labels and product assets."""

    def __init__(self):
        super().__init__()
        self.items: list[tuple[str, str, str]] = []
        self.assets: list[tuple[str, str, str]] = []
        self.links: list[tuple[str, str]] = []
        self.anchor_records: list[dict] = []
        self.visible: list[str] = []
        self._anchors: list[dict] = []
        self._stack: list[dict] = []
        self._heading: list[str] | None = None
        self._last_heading = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        marker = " ".join((tag, attrs.get("class", ""), attrs.get("id", ""), attrs.get("role", ""))).lower()
        structural = tag in {"nav", "footer", "aside"} or any(word in marker for word in ("related", "recommend"))
        parent_blocked = any(frame["blocked"] for frame in self._stack)
        blocked = parent_blocked or structural
        # Void elements never enter the stack: a header logo cannot poison the
        # remainder of a document which (correctly) has no </img> end tag.
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self._stack.append({"tag": tag, "blocked": blocked})
        if tag == "a":
            self._anchors.append({"attrs": attrs, "text": [], "blocked": blocked})
        if tag in {"h2", "h3", "h4"} and not blocked:
            self._heading = []
        model = attrs.get("data-model") or attrs.get("data-product-model")
        href = attrs.get("data-product-url") or (attrs.get("href") if model else None)
        if model and href and not blocked:
            self.items.append((model, href, attrs.get("data-category", "")))
        if tag == "img" and not blocked:
            url = attrs.get("data-src") or attrs.get("data-large_image") or attrs.get("src")
            evidence = attrs.get("alt", "")
            image_marker = (marker + " " + evidence + " " + (url or "")).lower()
            excluded = any(word in image_marker for word in ("logo", "icon", "banner", "flag"))
            if url and not excluded and any(word in image_marker for word in ("product", "producto", "gallery", "galeria", "woocommerce")):
                self.assets.append(("image", url, evidence))

    def handle_data(self, data):
        text = " ".join(data.split())
        if text and not any(frame["blocked"] for frame in self._stack):
            self.visible.append(text)
        if self._anchors:
            self._anchors[-1]["text"].append(data)
        if self._heading is not None:
            self._heading.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a" and self._anchors:
            anchor = self._anchors.pop()
            attrs = anchor["attrs"]
            text = " ".join("".join(anchor["text"]).split())
            href = attrs.get("href", "")
            if href and not anchor["blocked"]:
                self.links.append((text, href))
                self.anchor_records.append({"text": text, "href": href, "attrs": dict(attrs)})
                model = attrs.get("data-model") or attrs.get("data-product-model")
                classes = attrs.get("class", "").lower()
                if model or "product-card" in classes or "producto-card" in classes:
                    self.items.append((model or text, href, attrs.get("data-category", "")))
                elif "aprende más" in text.lower() or "aprende mas" in text.lower():
                    if self._last_heading:
                        self.items.append((self._last_heading, href, attrs.get("data-category", "")))
                label = " ".join((text, attrs.get("title", ""), attrs.get("aria-label", ""))).lower()
                if any(term in label for term in ("ficha técnica", "ficha tecnica", "hoja de datos")):
                    self.assets.append(("technical_sheet", href, text))
        if tag in {"h2", "h3", "h4"} and self._heading is not None:
            self._last_heading = " ".join("".join(self._heading).split())
            self._heading = None
        # Recover from omitted/mismatched closing tags by closing through the
        # nearest matching frame instead of maintaining a fragile counter.
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index]["tag"] == tag:
                del self._stack[index:]
                break


def _parse(body: bytes, base: str) -> PageParser:
    parser = PageParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.items = list(dict.fromkeys((n.strip(), urljoin(base, u), c.strip()) for n, u, c in parser.items if n.strip() and u))
    parser.assets = list(dict.fromkeys((t, urljoin(base, u), e.strip()) for t, u, e in parser.assets if u))
    parser.links = list(dict.fromkeys((t, urljoin(base, u)) for t, u in parser.links if u))
    parser.anchor_records = [
        {**record, "href": urljoin(base, record["href"])}
        for record in parser.anchor_records if record["href"]
    ]
    return parser


def _csv_bytes(fields, rows):
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _fetch(transport, url, timeout, max_bytes):
    validate_public_url(url, transport.resolve)
    response = transport.get(url, headers={"Accept": "text/html,application/xhtml+xml"}, timeout=timeout, max_bytes=max_bytes)
    validate_public_url(response.final_url, transport.resolve)
    requested_host = urlsplit(url).hostname
    final_host = urlsplit(response.final_url).hostname
    allowed_redirect_hosts = {requested_host}
    if requested_host in {"ep-equipment.com", "www.ep-equipment.com"}:
        allowed_redirect_hosts = {"ep-equipment.com", "www.ep-equipment.com"}
    if final_host not in allowed_redirect_hosts:
        raise ValueError(f"redirect fuera del origen permitido: {response.final_url}")
    if response.status != 200:
        raise ValueError(f"HTTP {response.status}: {url}")
    mime = (response.headers.get("content-type") or response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
    if mime and mime not in {"text/html", "application/xhtml+xml", "text/plain", "application/octet-stream"}:
        raise ValueError(f"MIME HTML inválido: {mime}")
    return response


def _allowed_product(url: str, source: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        return False
    if source == "EP":
        return parsed.hostname in {"ep-equipment.com", "www.ep-equipment.com"} and bool(re.fullmatch(r"/es/product/[^/]+/?", parsed.path))
    return parsed.hostname == "online.gamrentals.com" and parsed.path.startswith("/cl/ep/")


def _allowed_asset(url: str, source: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        return False
    if source == "EP":
        return parsed.hostname in {"ep-equipment.com", "www.ep-equipment.com", "cdn.ep-portal.net"}
    return parsed.hostname == "online.gamrentals.com"


def _identity_confirmed(parser: PageParser, model: str) -> bool:
    evidence = " ".join(parser.visible + [asset[2] for asset in parser.assets])
    return bool(_model_pattern(model).search(evidence))


def _seed_path():
    return Path(__file__).parents[1] / "fixtures" / "gam-ep-models-2026-09-16.csv"


def _authorize_robots(transport, robots_url, targets, timeout, max_bytes):
    validate_public_url(robots_url, transport.resolve)
    response = transport.get(robots_url, headers={"Accept": "text/plain"}, timeout=timeout, max_bytes=min(max_bytes, 512_000))
    validate_public_url(response.final_url, transport.resolve)
    if response.status in {404, 410}:
        return
    if response.status != 200:
        raise ValueError(f"robots bloqueado HTTP {response.status}: {robots_url}")
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.body.decode("utf-8", errors="replace").splitlines())
    if any(not parser.can_fetch("catalog-assets/1.0", target) for target in targets):
        raise ValueError("robots prohíbe harvest-ep")


def load_seed():
    with _seed_path().open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _new_checkpoint():
    return {**CHECKPOINT_VERSION, "completed_listings": [], "listing_diagnostics": {}, "live_items": [], "completed_ep_catalog": [], "ep_catalog_queue": [EP_START], "ep_catalog": [], "products": {}}


def _load_checkpoint(path: Path, root: Path):
    if not path.exists():
        return _new_checkpoint()
    raw = path.read_bytes()
    try:
        previous = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        previous = {}
    if all(previous.get(key) == value for key, value in CHECKPOINT_VERSION.items()):
        return previous
    archive = safe_path(root, f"_control/research/ep-harvest-checkpoint.incompatible-{int(time.time_ns())}.json")
    atomic_write(archive, raw, root)
    return _new_checkpoint()


def _save_checkpoint(path, checkpoint, root):
    atomic_write(path, (json.dumps(checkpoint, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(), root)


def harvest_ep(root, transport, request_delay=1.0, max_pages=100, max_models=39, max_bytes=5_000_000, timeout=20.0):
    if request_delay < 0 or max_pages < 1 or max_models < 1:
        raise ValueError("límites harvest-ep inválidos")
    research = safe_path(root, "_control/research")
    research.mkdir(parents=True, exist_ok=True)
    checkpoint_path = safe_path(root, "_control/research/ep-harvest-checkpoint.json")
    checkpoint = _load_checkpoint(checkpoint_path, root)
    completed = set(checkpoint["completed_listings"])
    requests = 0
    authorized = set(checkpoint.get("robots_authorized", []))
    for source, robots, targets in (("GAM", "https://online.gamrentals.com/robots.txt", GAM_LISTINGS), ("EP", "https://ep-equipment.com/robots.txt", (EP_START,))):
        if source not in authorized:
            _authorize_robots(transport, robots, targets, timeout, max_bytes)
            requests += 1
            authorized.add(source)
            checkpoint["robots_authorized"] = sorted(authorized)
            _save_checkpoint(checkpoint_path, checkpoint, root)
    seed = load_seed()
    seen_live = {
        (model, item["url"])
        for item in checkpoint["live_items"]
        for model, conflicts in [reconcile_title(item["observed_title"], seed)]
        if model and not conflicts
    }
    for listing in GAM_LISTINGS[:max_pages]:
        if listing in completed:
            continue
        response = _fetch(transport, listing, timeout, max_bytes)
        requests += 1
        parsed = _parse(response.body, response.final_url)
        page = GAM_LISTINGS.index(listing) + 1
        under_ep = []
        reconciled = []
        ambiguous_titles = []
        unmatched = []
        for anchor in parsed.anchor_records:
            split = urlsplit(anchor["href"])
            if split.scheme != "https" or split.hostname != "online.gamrentals.com" or not split.path.startswith("/cl/ep/"):
                continue
            under_ep.append(anchor)
            title = anchor["text"].strip()
            model, conflicts = reconcile_title(title, seed)
            if conflicts:
                ambiguous_titles.append(title)
            elif not model:
                unmatched.append(title)
            else:
                reconciled.append(title)
                identity = (model, anchor["href"])
                if identity not in seen_live:
                    checkpoint["live_items"].append({"observed_title": title, "url": anchor["href"], "category": anchor["attrs"].get("data-category", ""), "listing": listing, "position": len(checkpoint["live_items"]) + 1, "page": page})
                    seen_live.add(identity)
        mime = (response.headers.get("content-type") or response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        checkpoint["listing_diagnostics"][listing] = {
            "requested_url": listing, "http_status": response.status, "mime": mime,
            "bytes": len(response.body), "total_anchors": len(parsed.anchor_records),
            "ep_path_anchors": len(under_ep), "reconciled_titles": reconciled,
            "ambiguous_titles": ambiguous_titles, "unmatched_titles": unmatched,
        }
        checkpoint["completed_listings"].append(listing)
        completed.add(listing)
        _save_checkpoint(checkpoint_path, checkpoint, root)
        if request_delay:
            time.sleep(request_delay)

    if not checkpoint["live_items"]:
        raise HarvestError("HARVEST_NO_LIVE_MODELS", "los listados GAM no produjeron candidatos de producto conciliables")
    seed_models = {row["canonical_candidate"] for row in seed}
    matched: dict[str, dict] = {}
    ambiguous = []
    added = []
    for item in checkpoint["live_items"]:
        model, conflicts = reconcile_title(item["observed_title"], seed)
        if conflicts:
            ambiguous.append({"observed_title": item["observed_title"], "candidates": conflicts})
        elif model and model not in matched:
            matched[model] = item
        elif model:
            ambiguous.append({"observed_title": item["observed_title"], "candidates": [model], "reason": "duplicate"})
        else:
            added.append(item["observed_title"])
    removed = sorted(seed_models - set(matched))
    if not matched:
        raise HarvestError("HARVEST_MODEL_RECONCILIATION_FAILED", "ningún título GAM se concilió con el seed")

    ep_queue = list(checkpoint.get("ep_catalog_queue", [EP_START]))
    ep_done = set(checkpoint["completed_ep_catalog"])
    while ep_queue and len(ep_done) < max_pages:
        listing = ep_queue.pop(0)
        if listing in ep_done:
            continue
        response = _fetch(transport, listing, timeout, max_bytes)
        requests += 1
        parsed = _parse(response.body, response.final_url)
        checkpoint["ep_catalog"].extend([list(item) for item in parsed.items])
        for _, link in parsed.links:
            split = urlsplit(link)
            if split.scheme == "https" and split.hostname in {"ep-equipment.com", "www.ep-equipment.com"} and split.path.startswith("/es/productos/") and link not in ep_done:
                ep_queue.append(link)
        checkpoint["completed_ep_catalog"].append(listing)
        checkpoint["ep_catalog_queue"] = list(dict.fromkeys(ep_queue))
        ep_done.add(listing)
        _save_checkpoint(checkpoint_path, checkpoint, root)
        if request_delay:
            time.sleep(request_delay)

    ep_by_key: dict[str, list] = {}
    for name, url, category in checkpoint["ep_catalog"]:
        ep_by_key.setdefault(_key(name), []).append((name, url, category))
    inventory = []
    candidates = []
    source_rows = []
    concrete = [row for row in seed if row["disposition"] == "OBSERVED" and row["canonical_candidate"] in matched][:max_models]
    if not concrete:
        raise HarvestError("HARVEST_NO_CONCRETE_MODELS", "la conciliación no produjo modelos concretos")
    gam_pages = ep_pages = 0
    for seed_row in seed:
        model = seed_row["canonical_candidate"]
        family = seed_row["disposition"] == "REVIEW"
        live_row = matched.get(model, {})
        matches = ep_by_key.get(_key(model), []) if not family and live_row else []
        ep_url = matches[0][1] if len(matches) == 1 and _allowed_product(matches[0][1], "EP") else ""
        proposed_gam = live_row.get("url", "")
        gam_url = proposed_gam if proposed_gam and _allowed_product(proposed_gam, "GAM") else ""
        ep_assets = []
        gam_assets = []
        if seed_row in concrete:
            product_key = _key(model)
            saved = checkpoint["products"].get(product_key)
            if saved:
                ep_assets, gam_assets = saved.get("ep_assets", []), saved.get("gam_assets", [])
                ep_pages += int(bool(saved.get("ep_observed")))
                gam_pages += int(bool(saved.get("gam_observed")))
            else:
                ep_observed = gam_observed = False
                if ep_url:
                    page = _fetch(transport, ep_url, timeout, max_bytes)
                    requests += 1
                    parsed = _parse(page.body, page.final_url)
                    if _identity_confirmed(parsed, model):
                        ep_observed = True
                        ep_assets = [list(asset) for asset in parsed.assets if _allowed_asset(asset[1], "EP")]
                        ep_pages += 1
                if gam_url:
                    page = _fetch(transport, gam_url, timeout, max_bytes)
                    requests += 1
                    parsed = _parse(page.body, page.final_url)
                    if _identity_confirmed(parsed, model):
                        gam_observed = True
                        gam_assets = [list(asset) for asset in parsed.assets if _allowed_asset(asset[1], "GAM")]
                        gam_pages += 1
                checkpoint["products"][product_key] = {"ep_assets": ep_assets, "gam_assets": gam_assets, "ep_url": ep_url, "gam_url": gam_url, "ep_observed": ep_observed, "gam_observed": gam_observed}
                _save_checkpoint(checkpoint_path, checkpoint, root)
                if request_delay:
                    time.sleep(request_delay)
        ep_types = {asset[0] for asset in ep_assets}
        selected = [("EP", "primary", ep_url, asset) for asset in ep_assets]
        selected += [("GAM", "fallback", gam_url, asset) for asset in gam_assets if asset[0] not in ep_types]
        for source, role, page_url, (kind, url, evidence) in selected:
            candidates.append({"target_brand": "EP", "model": model, "category": seed_row["category"], "asset_type": kind, "asset_role": role, "source_name": source, "source_role": role, "page_url": page_url, "asset_url": url, "expected_mime": "image/*" if kind == "image" else "application/pdf", "expected_extension": "" if kind == "image" else ".pdf", "language": "es", "priority": 0 if source == "EP" else 100, "model_evidence": evidence or model, "confidence": "HIGH", "disposition": "REVIEW", "http_status": "", "observed_mime": "", "validation_status": "VALIDATION_DEFERRED", "notes": "asset discovered on exact model page; binary validation pending"})
            source_rows.append({"target_brand": "EP", "model": model, "source_name": source, "source_role": role, "page_url": page_url, "asset_type": kind, "asset_url": url, "priority": 0 if source == "EP" else 100, "expected_language": "es", "enabled": "false", "notes": "VALIDATION_DEFERRED; exact model page; direct asset discovered"})
        inventory.append({"target_brand": "EP", "model": model, "observed_title": live_row.get("observed_title", ""), "category": seed_row["category"], "official_model_name": matches[0][0] if len(matches) == 1 else "", "ep_listing_url": EP_START, "ep_product_url": ep_url, "gam_product_url": gam_url, "ep_image_candidates": sum(asset[0] == "image" for asset in ep_assets), "ep_pdf_candidates": sum(asset[0] == "technical_sheet" for asset in ep_assets), "missing_image": str("image" not in ep_types).lower(), "missing_pdf": str("technical_sheet" not in ep_types).lower(), "gam_fallback_needed": str(any(asset[0] not in ep_types for asset in gam_assets)).lower(), "confidence": "REVIEW" if family or len(matches) != 1 else "HIGH", "status": "FAMILY_REVIEW" if family else ("MATCHED" if len(matches) == 1 else "OFFICIAL_SOURCE_NOT_FOUND"), "notes": seed_row["notes"]})

    if gam_pages + ep_pages == 0:
        raise HarvestError("HARVEST_NO_PRODUCT_PAGES", "ninguna página confirmó la identidad de un modelo concreto")
    if not source_rows:
        raise HarvestError("HARVEST_NO_ASSET_SOURCES", "las páginas de producto no produjeron candidatos")

    source_rows.sort(key=lambda row: (row["model"].casefold(), int(row["priority"]), row["asset_type"], row["asset_url"]))
    summary = {"seed_models": len(seed), "live_models": len(checkpoint["live_items"]), "matched_seed_models": len(matched), "concrete_models": len(concrete), "review_families": sorted(FAMILIES), "added": sorted(added), "removed": removed, "ambiguous": ambiguous, "gam_product_pages_observed": gam_pages, "ep_product_pages_observed": ep_pages, "image_candidates": sum(row["asset_type"] == "image" for row in source_rows), "technical_sheet_candidates": sum(row["asset_type"] == "technical_sheet" for row in source_rows), "sources": len(source_rows), "requests_this_run": requests, "assets_downloaded": 0, "checkpoint_version": dict(CHECKPOINT_VERSION), "requires_review": bool(ambiguous or added or removed or FAMILIES)}
    audit_summary = {key: value for key, value in summary.items() if key != "requests_this_run"}
    audit = "# Recolección local EP/GAM\n\n" + json.dumps(audit_summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    # Publish the complete set only after coherence checks. Each replacement is atomic.
    outputs = ((research / "ep-model-inventory.csv", _csv_bytes(MODEL_FIELDS, inventory)), (research / "ep-asset-candidates.csv", _csv_bytes(CANDIDATE_FIELDS, candidates)), (safe_path(root, "_control/fuentes.csv"), _csv_bytes(COLUMNS, source_rows)), (research / "ep-source-audit.md", audit.encode("utf-8")))
    for path, data in outputs:
        atomic_write(path, data, root)
    _save_checkpoint(checkpoint_path, checkpoint, root)
    return summary
