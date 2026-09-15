# Catalog stage contracts

## Semantic identities and physical keys

`semantic-path-key-v1` accepts only `<versioned-prefix>:sha256:<64 lower-case hex>` identities. It emits `sidv1-<digest>` filesystem segments after validating the expected namespace. The containing receipt, checkpoint, normalized document, and `physical-identity-mappings.json` retain the complete semantic identity; `safe_join` remains strict.

## Matching to extraction

`matching-extraction-binding-v1` is embedded in the matching manifest as `identity_bindings`. Each binding seals the observed discovery reference, opaque stable source identity, namespace, role, canonical resolution, and evidence. `binding_hash` is the canonical SHA-256 of the ordered bindings and participates in both matching and extraction semantic fingerprints. Extraction validates the matching fingerprint and binding hash before reading snapshot HTML, and rejects missing, duplicate, contradictory, unknown, or incompatible bindings.

## Normalized document to JEM

`normalized-to-jem-v1` is a pure adapter in `jem_nexus_import`. It accepts only normalized audit documents version 1.0.0, resolves every projected value to one unambiguous embedded normalized observation, and emits JEM projection schema 2.0.0. Numeric values remain canonical decimal strings (including `"0"`); they are never converted to binary floats. The projection retains per-value provenance and its adapter version in its fingerprint. Reconciliation consumes only this projection and applies the existing safe commercial defaults.
