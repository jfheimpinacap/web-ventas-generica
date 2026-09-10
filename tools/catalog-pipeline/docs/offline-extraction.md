# Detailed offline extraction (v1)

## Contracts, inputs, and gates

The foundation already defined immutable evidence, source identities, discovery candidates, matching links, supplemental associations, canonical JSON, SHA-256 binding, confined paths, and atomic/write-once storage. It lacked contracts for classified raw pages, per-value provenance, raw table grids, URL-only media/document candidates, extraction review/manifests, and extraction comparison. The eight new closed `schemas/v1` contracts fill only those gaps; they do not alter JEM.

Only local versioned snapshot/matching manifests, immutable bytes, and versioned rules are accepted. Before parsing, extraction checks versions/fingerprints, matching universes, unique IDs/references, namespace/role/adapter, canonical URL metadata, confined paths, existence, size, SHA-256, MIME, and strict declared encoding. Any failure blocks before output exists. Discovery and transport are not imported or constructed.

## Raw layers and provenance

Layers remain separate: snapshot → classified page → raw observation → raw table → media/document URL candidate → review. Snapshot bytes remain primary evidence. Deterministic observation IDs bind source identity, snapshot hash, locator, field, value and occurrence—not clock, machine, absolute/temp path, or incidental order. Records retain namespace/role, nullable entry/association/canonical identity, both URLs, snapshot reference/hash, MIME/encoding, raw field/value/unit, locator, page/scope, adapter/rule, resolution/blockers, and a separate operational timestamp.

Standard-library HTML parsing is passive and bounded by deterministic byte/node/JSON-depth limits. Declared encodings decode strictly; entities use declared `HTMLParser(convert_charrefs=True)` handling. Accents, `ñ`, Unicode punctuation/superscripts, spacing, comma decimals, mistakes, and malformed translations remain unchanged. Text I/O explicitly uses UTF-8 and deterministic output uses LF. There is no correction, translation, range inference, or conversion.

## Classification, tables, and series

The closed page enum is `product`, `series`, `family`, `listing`, `document_landing`, `unknown`, `structure_changed`, and `parse_failed`. Unknown pages get no aggressive fallback. Changed/failed pages enter review; a listing received as product and an empty expected product block. Series/family pages never become products.

Tables retain captions, row/cell coordinates, kind, locators, raw value/unit, rowspan/colspan, explicit model scope and irregularity. Duplicate/contradictory values remain distinct, missing cells are never invented, and ambiguous merged/irregular grids enter review. Explicit model columns stay separate without adoption; unscoped values are not copied, and family values remain `series_shared`.

Fields are raw evidence, not JEM mappings. EP lift height is never `WorkingHeightM` (the fixture hint is only `ProductSpec`). Voltage, Ah, chemistry, unknown enums, year/hours and power source remain raw. EP authoritative and GAM supplemental observations remain separate; GAM creates no official entry and canonical identity may be null. GAM price/stock/availability are retained as excluded commercial evidence, never projected. Conflicts remain for humans.

## URL candidates

Image candidates retain original/resolved candidate URL, referrer, provenance, locator/attribute, alt/title, relationship, scope, host, apparent extension, rule and review state. Nothing selects a primary. Logos/banners/icons remain rejected/audited; external hosts remain pending and never expand allowlists. Document candidates similarly retain link text, apparent filename, provisional kind, explicit language/revision hints, scope and evidence. Extensions confirm neither MIME nor technical-sheet status. No bytes are downloaded.

## Synthetic gate, outputs, CLI, and comparison

EP/GAM live extraction remains blocked: no approved live structural evidence or selectors exist. Bundled rules are `fixture_only`, `structure_verified=false`, fixtures are not live evidence, and no bypass exists. Synthetic output is neither live nor importable.

Sorted outputs are `raw-products.jsonl`, `raw-field-observations.jsonl`, `raw-tables.jsonl`, `media-candidates.jsonl`, `document-candidates.jsonl`, `extraction-review.jsonl`, `extraction-manifest.json`, and `extraction-report.txt`. The manifest binds hashes, schemas, engine/adapters/rules, sources/roles, counts, status/blockers and artifacts. Its semantic fingerprint excludes operational time. Canonical serialization and sorting make identical inputs reproducible. A sibling staging directory is atomically renamed and explicitly removed on failure.

```text
python catalog_extract.py plan --snapshot-manifest SNAPSHOTS.json --matching-manifest MATCHING.json
python catalog_extract.py extract --snapshot-manifest SNAPSHOTS.json --snapshot-root ROOT --matching-manifest MATCHING.json --output-dir OUTPUT
python catalog_extract.py compare --old-manifest OLD.json --new-manifest NEW.json --output COMPARISON.json
```

`plan` writes nothing; `extract` prevalidates; `compare` preserves inputs. Empty/root/traversal/checkout/existing outputs and unsafe paths are rejected. Exit codes: 0 complete, 1 invalid/I/O, 2 blocked, 3 incompatible. No download/apply/publish commands exist. Comparison reports unchanged/new observation/media/document evidence and reserves value/field/structure classes; absence means `field_not_observed`, never deletion. Schema, adapter/rule, identity strategy, or matching fingerprint changes block comparison. Old evidence is never overwritten.

## Explicit limits and pending decisions

No network was used; no live/media/PDF resource was downloaded; no unit was converted; no JEM field/category/enum was mapped; no alias/conflict was resolved; no final description/payload was generated; no product was created/imported/published; and LGMG was not modified. Fixture locators are provisional. Approved live evidence/selectors, mappings, normalization, conflict policy, hosts, downloads, and primary selection remain separate future decisions.
