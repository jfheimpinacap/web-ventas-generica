"""Closed helpers for versioned JEM Nexus contract metadata."""
from __future__ import annotations

ROOT_CATEGORY_FIELDS = frozenset(("collection", "identity_field", "identity", "parent_field", "product_type"))


def root_category_contract(contract):
    metadata = contract.get("local_readiness") if isinstance(contract, dict) else None
    root = metadata.get("root_category") if isinstance(metadata, dict) else None
    if not isinstance(root, dict) or set(root) != ROOT_CATEGORY_FIELDS:
        raise ValueError("ROOT_CATEGORY_CONTRACT_INVALID")
    if not all(isinstance(root[field], str) and root[field] for field in ROOT_CATEGORY_FIELDS):
        raise ValueError("ROOT_CATEGORY_CONTRACT_INVALID")
    return dict(root)


def select_contract_root(categories, root):
    """Select exactly one root by contractual identity, never by ID or order."""
    if not isinstance(categories, list):
        return {"status": "missing", "matches": [], "root": None}
    matches = [item for item in categories if isinstance(item, dict)
               and item.get(root["identity_field"]) == root["identity"]]
    if not matches:
        return {"status": "missing", "matches": [], "root": None}
    if len(matches) != 1:
        return {"status": "ambiguous", "matches": matches, "root": None}
    item = matches[0]
    identifier = item.get("id")
    valid = (item.get(root["parent_field"]) is None
             and item.get("product_type") == root["product_type"]
             and type(identifier) is int and identifier > 0)
    return {"status": "valid" if valid else "invalid", "matches": matches,
            "root": item if valid else None}
