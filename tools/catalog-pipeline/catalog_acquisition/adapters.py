"""Offline protocol for future source adapters. Implementations receive captured bytes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol, Sequence

@dataclass(frozen=True)
class AdapterDiagnostic:
    code: str; severity: str; message: str; blocking: bool

class SourceAdapter(Protocol):
    adapter_id: str; adapter_version: str; capabilities: frozenset[str]
    def validate_input(self, captured: bytes) -> Sequence[AdapterDiagnostic]: ...
    def discover(self, snapshot: bytes) -> Iterable[Mapping[str, object]]: ...
    def extract(self, evidence: bytes) -> Iterable[Mapping[str, object]]: ...
    def normalize_reference(self, reference: str) -> str: ...
    def fingerprint(self) -> str: ...

class SyntheticAdapter:
    """Tiny injected-data demonstration; it performs no I/O."""
    adapter_id="synthetic.fixture"; adapter_version="1.0.0"; capabilities=frozenset({"discovery", "extraction"})
    def validate_input(self, captured: bytes): return [] if captured else [AdapterDiagnostic("EMPTY_INPUT", "error", "Captured input is empty", True)]
    def discover(self, snapshot: bytes): return ({"stable_source_key": line.decode("utf-8")} for line in snapshot.splitlines() if line)
    def extract(self, evidence: bytes): return ({"raw_value": evidence.decode("utf-8"), "resolution_status": "exact"},)
    def normalize_reference(self, reference: str) -> str: return reference.strip()
    def fingerprint(self) -> str: return "synthetic.fixture@1.0.0"
