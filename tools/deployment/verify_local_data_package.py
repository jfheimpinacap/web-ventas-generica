#!/usr/bin/env python3
"""Offline verifier for the private JemNexus local-data package.

This program deliberately has no database client and no import/apply mode.  Its
stdout contract is metadata-only: counts, SHA-256 digests, and blocker codes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

TABLES = (
    "AppUsers", "AppUserPermissions", "Brands", "Categories", "Suppliers",
    "TechnicalSheets", "Products", "ProductImages", "ProductSpecs", "Promotions",
    "HomeSectionItems", "QuoteRequests", "CustomerProfiles", "CommercialQuotes",
    "CommercialQuoteItems", "CommercialQuoteFolioCounters",
    "CommercialQuoteIssueIdempotencyRecords",
)
COUNTS = dict(zip(TABLES, (3, 58, 3, 10, 0, 85, 92, 92, 58, 0, 0, 0, 1, 9, 9, 1, 8)))
PK = {name: ("Id",) for name in TABLES}
PK.update(AppUserPermissions=("UserId", "Permission"),
          CommercialQuoteFolioCounters=("Year",),
          CommercialQuoteIssueIdempotencyRecords=("ResponsibleSellerId", "IdempotencyKey"))
FKS = (
    ("AppUserPermissions", "UserId", "AppUsers"),
    ("Categories", "ParentId", "Categories"),
    ("Products", "CategoryId", "Categories"), ("Products", "BrandId", "Brands"),
    ("Products", "SupplierId", "Suppliers"), ("Products", "TechnicalSheetId", "TechnicalSheets"),
    ("ProductImages", "ProductId", "Products"), ("ProductSpecs", "ProductId", "Products"),
    ("Promotions", "ProductId", "Products"), ("HomeSectionItems", "ProductId", "Products"),
    ("QuoteRequests", "ProductId", "Products"),
    ("CommercialQuotes", "CustomerProfileId", "CustomerProfiles"),
    ("CommercialQuotes", "ResponsibleSellerId", "AppUsers"),
    ("CommercialQuotes", "IssuedById", "AppUsers"),
    ("CommercialQuoteItems", "CommercialQuoteId", "CommercialQuotes"),
    ("CommercialQuoteItems", "ProductId", "Products"),
    ("CommercialQuoteIssueIdempotencyRecords", "ResponsibleSellerId", "AppUsers"),
    ("CommercialQuoteIssueIdempotencyRecords", "CommercialQuoteId", "CommercialQuotes"),
)
AUDIT_TABLES = ("Brands", "Categories", "Suppliers", "Products", "ProductImages",
                "ProductSpecs", "Promotions", "HomeSectionItems", "QuoteRequests", "CustomerProfiles")
PLAN = (
    ("AppUsers",), ("AppUserPermissions",),
    ("Brands", "Categories", "Suppliers", "TechnicalSheets"), ("Products",),
    ("ProductImages", "ProductSpecs", "Promotions", "HomeSectionItems"),
    ("CustomerProfiles",), ("QuoteRequests",), ("CommercialQuotes",),
    ("CommercialQuoteItems", "CommercialQuoteFolioCounters", "CommercialQuoteIssueIdempotencyRecords"),
)

class Blocked(Exception):
    def __init__(self, code: str): self.code = code

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()

def strict_json(path: Path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise Blocked("JSON_DUPLICATE_KEY")
            result[key] = value
        return result
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            return json.load(stream, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(Blocked("JSON_NONFINITE_NUMBER")))
    except Blocked: raise
    except (OSError, UnicodeError, json.JSONDecodeError): raise Blocked("JSON_INVALID")

def exact_keys(value, keys, code):
    if not isinstance(value, dict) or set(value) != set(keys): raise Blocked(code)

def is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse)

def safe_member(root: Path, member: str, prefix: str) -> Path:
    if not isinstance(member, str) or "\\" in member:
        raise Blocked("PATH_INVALID")
    pure = PurePosixPath(member)
    if pure.is_absolute() or not pure.parts or any(p in ("", ".", "..") for p in pure.parts) or not member.startswith(prefix):
        raise Blocked("PATH_EXTERNAL_OR_TRAVERSAL")
    candidate = root.joinpath(*pure.parts)
    cursor = root
    if is_link_or_reparse(root): raise Blocked("LINK_REJECTED")
    for part in pure.parts:
        cursor = cursor / part
        if is_link_or_reparse(cursor): raise Blocked("LINK_REJECTED")
    try:
        if os.path.commonpath((str(root.resolve()), str(candidate.resolve(strict=True)))) != str(root.resolve()):
            raise Blocked("PATH_EXTERNAL_OR_TRAVERSAL")
    except (OSError, ValueError): raise Blocked("FILE_MISSING")
    if not candidate.is_file(): raise Blocked("FILE_MISSING")
    return candidate

def verify(package: Path) -> dict:
    if not package.is_absolute(): raise Blocked("PACKAGE_PATH_NOT_ABSOLUTE")
    manifest_path = safe_member(package, "manifest.json", "manifest.json")
    manifest = strict_json(manifest_path)
    exact_keys(manifest, ("packageVersion", "packageType", "createdUtc", "status", "source", "exclusions", "tables", "media", "limitations"), "MANIFEST_STRUCTURE")
    exact_keys(manifest["source"], ("instance", "database", "schema", "inventorySha256"), "SOURCE_STRUCTURE")
    exact_keys(manifest["exclusions"], ("tables", "refreshTokenRowsIncluded", "orphanImageFilesIncluded", "observedOrphanImageFiles"), "EXCLUSIONS_STRUCTURE")
    exact_keys(manifest["tables"], ("count", "rowCounts", "sha256"), "TABLES_STRUCTURE")
    exact_keys(manifest["media"], ("count", "files"), "MEDIA_STRUCTURE")
    if (manifest["packageVersion"] != 1 or manifest["packageType"] != "JemNexusLocalDataPackage" or
        manifest["status"] != "PREPARED_LOCAL_NOT_AUTHORIZED_FOR_PRODUCTION_APPLY"):
        raise Blocked("PACKAGE_IDENTITY")
    source = manifest["source"]
    if source["instance"] != "(localdb)\\MSSQLLocalDB" or source["database"] != "JemNexus_Local" or source["schema"] != "dbo":
        raise Blocked("SOURCE_IDENTITY")
    exclusions = manifest["exclusions"]
    if exclusions["tables"] != ["AppRefreshTokens", "__EFMigrationsHistory"] or exclusions["refreshTokenRowsIncluded"] != 0 or exclusions["orphanImageFilesIncluded"] != 0:
        raise Blocked("EXCLUSIONS_INVALID")
    tables = manifest["tables"]
    if tables["count"] != 17 or tables["rowCounts"] != COUNTS or set(tables["sha256"]) != set(TABLES):
        raise Blocked("TABLE_COUNTS_OR_SET")

    rows = {}; expected_files = {"manifest.json"}; table_hashes = {}
    for name in TABLES:
        rel = "data/" + name + ".json"; path = safe_member(package, rel, "data/")
        expected_files.add(rel)
        actual_hash = sha256(path); expected_hash = tables["sha256"][name]
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or expected_hash.lower() != expected_hash or actual_hash != expected_hash: raise Blocked("TABLE_HASH_MISMATCH")
        value = strict_json(path)
        if (not isinstance(value, list) or len(value) != COUNTS[name] or
            any(not isinstance(row, dict) or any(isinstance(cell, (dict, list)) for cell in row.values()) for row in value)):
            raise Blocked("TABLE_JSON_STRUCTURE_OR_COUNT")
        keys = PK[name]
        if any(any(key not in row for key in keys) for row in value): raise Blocked("PRIMARY_KEY_MISSING")
        identities = [tuple(row[key] for key in keys) for row in value]
        if len(set(identities)) != len(identities): raise Blocked("PRIMARY_KEY_DUPLICATE")
        rows[name] = value; table_hashes[name] = actual_hash

    ids = {name: {row[PK[name][0]] for row in value} for name, value in rows.items() if len(PK[name]) == 1}
    for child, column, parent in FKS:
        for row in rows[child]:
            if column not in row: raise Blocked("FOREIGN_KEY_COLUMN_MISSING")
            if row[column] is not None and row[column] not in ids[parent]: raise Blocked("FOREIGN_KEY_ORPHAN")
    for name in AUDIT_TABLES:
        for row in rows[name]:
            for column in ("CreatedById", "UpdatedById"):
                if column not in row: raise Blocked("AUDIT_COLUMN_MISSING")
                if row[column] is not None and row[column] not in ids["AppUsers"]: raise Blocked("AUDIT_FOREIGN_KEY_ORPHAN")

    category_parent = {row["Id"]: row["ParentId"] for row in rows["Categories"]}
    for category in category_parent:
        visited = set(); cursor = category
        while cursor is not None:
            if cursor in visited: raise Blocked("CATEGORY_DEPENDENCY_CYCLE")
            visited.add(cursor); cursor = category_parent[cursor]
    image_parent = {row["Id"]: row["ProductId"] for row in rows["ProductImages"]}

    media = manifest["media"]
    if media["count"] != 177 or not isinstance(media["files"], list) or len(media["files"]) != 177:
        raise Blocked("MEDIA_COUNT")
    media_hash = hashlib.sha256(); seen_paths = set(); seen_records = set()
    for entry in media["files"]:
        exact_keys(entry, ("kind", "recordId", "parentId", "packagePath", "sizeBytes", "sha256"), "MEDIA_ENTRY_STRUCTURE")
        kind = entry["kind"]; prefix = "media/images/product-images/" if kind == "product-image" else "media/technical-sheets/" if kind == "technical-sheet" else None
        if prefix is None: raise Blocked("MEDIA_KIND")
        record = (kind, entry["recordId"])
        if entry["packagePath"] in seen_paths or record in seen_records: raise Blocked("MEDIA_DUPLICATE")
        path = safe_member(package, entry["packagePath"], prefix)
        parts = PurePosixPath(entry["packagePath"]).parts
        if ((kind == "product-image" and (len(parts) != 5 or parts[3] != str(entry["parentId"]))) or
            (kind == "technical-sheet" and len(parts) != 3)):
            raise Blocked("MEDIA_PATH_RELATION")
        actual_hash = sha256(path)
        if (not isinstance(entry["sizeBytes"], int) or isinstance(entry["sizeBytes"], bool) or entry["sizeBytes"] < 0 or
            not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64 or entry["sha256"].lower() != entry["sha256"] or
            path.stat().st_size != entry["sizeBytes"] or actual_hash != entry["sha256"]): raise Blocked("MEDIA_HASH_OR_SIZE_MISMATCH")
        if kind == "product-image":
            if entry["recordId"] not in ids["ProductImages"] or image_parent[entry["recordId"]] != entry["parentId"]: raise Blocked("MEDIA_RELATION")
        elif entry["recordId"] not in ids["TechnicalSheets"] or entry["parentId"] is not None: raise Blocked("MEDIA_RELATION")
        seen_paths.add(entry["packagePath"]); seen_records.add(record)
        media_hash.update((entry["packagePath"] + "\0" + actual_hash + "\n").encode())
        expected_files.add(entry["packagePath"])
    if sum(1 for k, _ in seen_records if k == "product-image") != 92 or sum(1 for k, _ in seen_records if k == "technical-sheet") != 85:
        raise Blocked("MEDIA_KIND_COUNTS")
    actual_files = set()
    for base, dirs, files in os.walk(package, followlinks=False):
        if any(is_link_or_reparse(Path(base) / d) for d in dirs): raise Blocked("LINK_REJECTED")
        for filename in files:
            path = Path(base) / filename
            if is_link_or_reparse(path): raise Blocked("LINK_REJECTED")
            actual_files.add(path.relative_to(package).as_posix())
    if actual_files != expected_files: raise Blocked("PACKAGE_FILE_SET")
    plan_hash = hashlib.sha256(json.dumps(PLAN, separators=(",", ":")).encode()).hexdigest()
    return {"status": "VERIFIED_OFFLINE_PLAN_ONLY", "counts": {"tables": 17, "rows": sum(COUNTS.values()), "media": 177},
            "hashes": {"manifestSha256": sha256(manifest_path), "tableSetSha256": hashlib.sha256("".join(table_hashes[n] for n in TABLES).encode()).hexdigest(), "mediaSetSha256": media_hash.hexdigest(), "importPlanSha256": plan_hash}, "blockers": ["NO_DATABASE_WRITE_IMPLEMENTED", "WINDOWS_DISPOSABLE_IDENTITY_NOT_DYNAMICALLY_PROVEN", "DESTINATION_SCHEMA_DRIFT_NOT_CHECKED"]}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("PlanOnly", "VerifyPackage"))
    parser.add_argument("--package")
    args = parser.parse_args(argv)
    if args.mode == "PlanOnly":
        if args.package is not None:
            print(json.dumps({"status":"BLOCKED", "counts":{}, "hashes":{}, "blockers":["PLAN_ONLY_REJECTS_PACKAGE_PATH"]}, sort_keys=True)); return 2
        print(json.dumps({"status":"PLAN_ONLY", "counts":{"tables":17,"expectedRows":sum(COUNTS.values()),"media":177}, "hashes":{"importPlanSha256":hashlib.sha256(json.dumps(PLAN,separators=(",", ":")).encode()).hexdigest()}, "blockers":["NO_DATABASE_WRITE_IMPLEMENTED","PACKAGE_NOT_VERIFIED"]}, sort_keys=True)); return 0
    try:
        if not args.package: raise Blocked("PACKAGE_PATH_REQUIRED")
        result = verify(Path(args.package))
        print(json.dumps(result, sort_keys=True)); return 0
    except Blocked as error:
        print(json.dumps({"status":"BLOCKED", "counts":{}, "hashes":{}, "blockers":[error.code]}, sort_keys=True)); return 2
    except Exception:
        # Do not let runtime diagnostics disclose package values or private paths.
        print(json.dumps({"status":"BLOCKED", "counts":{}, "hashes":{}, "blockers":["INTERNAL_VALIDATION_ERROR"]}, sort_keys=True)); return 2

if __name__ == "__main__": sys.exit(main())
