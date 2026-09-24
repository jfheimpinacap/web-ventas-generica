import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "verify_local_data_package.py"
SPEC = importlib.util.spec_from_file_location("package_verifier", SCRIPT)
verifier = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(verifier)

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build_package(root):
    package = root / "package"; (package / "data").mkdir(parents=True)
    rows = {}
    for table, count in verifier.COUNTS.items():
        values = []
        for number in range(1, count + 1):
            row = {"Id": number}
            if table in verifier.AUDIT_TABLES: row.update(CreatedById=1, UpdatedById=1)
            values.append(row)
        rows[table] = values
    rows["AppUsers"][0]["PasswordHash"] = "SYNTHETIC_SECRET_MUST_NOT_LEAK"
    rows["AppUserPermissions"] = [{"UserId": 1 + (n % 2), "Permission": "p%02d" % n} for n in range(58)]
    rows["Categories"][0]["ParentId"] = None
    for row in rows["Categories"][1:]: row["ParentId"] = 1
    for row in rows["Products"]: row.update(CategoryId=1, BrandId=1, SupplierId=None, TechnicalSheetId=1)
    for table in ("ProductImages", "ProductSpecs"):
        for row in rows[table]: row["ProductId"] = row["Id"]
    for table in ("Promotions", "HomeSectionItems", "QuoteRequests"):
        for row in rows[table]: row["ProductId"] = 1
    for row in rows["CommercialQuotes"]: row.update(CustomerProfileId=1, ResponsibleSellerId=1, IssuedById=1)
    for row in rows["CommercialQuoteItems"]: row.update(CommercialQuoteId=row["Id"], ProductId=row["Id"])
    rows["CommercialQuoteFolioCounters"] = [{"Year": 2026, "LastNumber": 9}]
    rows["CommercialQuoteIssueIdempotencyRecords"] = [{"ResponsibleSellerId": 1, "IdempotencyKey": "k%d" % n, "CommercialQuoteId": n, "CreatedAt": "synthetic"} for n in range(1, 9)]
    hashes = {}
    for table in verifier.TABLES:
        path = package / "data" / (table + ".json")
        path.write_text(json.dumps(rows[table], separators=(",", ":")), encoding="utf-8")
        hashes[table] = digest(path)
    media = []
    for number in range(1, 93):
        rel = "media/images/product-images/%d/f.bin" % number; path = package / rel
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(("i%d" % number).encode())
        media.append({"kind":"product-image", "recordId":number, "parentId":number, "packagePath":rel, "sizeBytes":path.stat().st_size, "sha256":digest(path)})
    for number in range(1, 86):
        rel = "media/technical-sheets/s%d.pdf" % number; path = package / rel
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(("s%d" % number).encode())
        media.append({"kind":"technical-sheet", "recordId":number, "parentId":None, "packagePath":rel, "sizeBytes":path.stat().st_size, "sha256":digest(path)})
    manifest = {"packageVersion":1,"packageType":"JemNexusLocalDataPackage","createdUtc":"synthetic","status":"PREPARED_LOCAL_NOT_AUTHORIZED_FOR_PRODUCTION_APPLY",
        "source":{"instance":"(localdb)\\MSSQLLocalDB","database":"JemNexus_Local","schema":"dbo","inventorySha256":"0"*64},
        "exclusions":{"tables":["AppRefreshTokens","__EFMigrationsHistory"],"refreshTokenRowsIncluded":0,"orphanImageFilesIncluded":0,"observedOrphanImageFiles":2},
        "tables":{"count":17,"rowCounts":verifier.COUNTS,"sha256":hashes},"media":{"count":177,"files":media},"limitations":[]}
    (package / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    return package

class VerifierTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=False)

    def test_plan_only_neither_reads_nor_accepts_package(self):
        result = self.run_cli("--mode", "PlanOnly")
        self.assertEqual(0, result.returncode); self.assertEqual("PLAN_ONLY", json.loads(result.stdout)["status"])
        result = self.run_cli("--mode", "PlanOnly", "--package", "/does/not/exist")
        self.assertEqual(2, result.returncode)

    def test_valid_synthetic_package_and_no_row_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_cli("--mode", "VerifyPackage", "--package", str(build_package(Path(temp)).resolve()))
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual("VERIFIED_OFFLINE_PLAN_ONLY", json.loads(result.stdout)["status"])
        self.assertNotIn("SYNTHETIC_SECRET", result.stdout)

    def test_accepts_empty_array_for_every_zero_count_table(self):
        with tempfile.TemporaryDirectory() as temp:
            package = build_package(Path(temp))
            for table in ("Suppliers", "Promotions", "HomeSectionItems", "QuoteRequests"):
                self.assertEqual("[]", (package / "data" / f"{table}.json").read_text())
            result = self.run_cli("--mode", "VerifyPackage", "--package", str(package.resolve()))
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual(429, json.loads(result.stdout)["counts"]["rows"])

    def test_rejects_empty_or_invalid_json_even_with_matching_manifest_hash(self):
        for contents in ("", "not-json"):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as temp:
                package = build_package(Path(temp)); table = package / "data" / "Suppliers.json"
                table.write_text(contents)
                manifest_path = package / "manifest.json"; manifest = json.loads(manifest_path.read_text())
                manifest["tables"]["sha256"]["Suppliers"] = digest(table)
                manifest_path.write_text(json.dumps(manifest, separators=(",", ":")))
                result = self.run_cli("--mode", "VerifyPackage", "--package", str(package.resolve()))
            self.assertEqual(2, result.returncode)
            self.assertEqual(["JSON_INVALID"], json.loads(result.stdout)["blockers"])

    def test_rejects_hash_mismatch_and_reports_only_code(self):
        with tempfile.TemporaryDirectory() as temp:
            package = build_package(Path(temp)); (package / "data" / "AppUsers.json").write_text("[]")
            result = self.run_cli("--mode", "VerifyPackage", "--package", str(package.resolve()))
        self.assertEqual(2, result.returncode); self.assertEqual(["TABLE_HASH_MISMATCH"], json.loads(result.stdout)["blockers"])

    def test_rejects_unexpected_file(self):
        with tempfile.TemporaryDirectory() as temp:
            package = build_package(Path(temp)); (package / "extra.txt").write_text("x")
            result = self.run_cli("--mode", "VerifyPackage", "--package", str(package.resolve()))
        self.assertEqual(2, result.returncode); self.assertEqual(["PACKAGE_FILE_SET"], json.loads(result.stdout)["blockers"])

    def test_rejects_traversal_before_reading_target(self):
        with tempfile.TemporaryDirectory() as temp:
            package = build_package(Path(temp)); path = package / "manifest.json"
            manifest = json.loads(path.read_text()); manifest["media"]["files"][0]["packagePath"] = "media/images/product-images/1/../f.bin"
            path.write_text(json.dumps(manifest))
            result = self.run_cli("--mode", "VerifyPackage", "--package", str(package.resolve()))
        self.assertEqual(2, result.returncode); self.assertEqual(["PATH_EXTERNAL_OR_TRAVERSAL"], json.loads(result.stdout)["blockers"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_rejects_link(self):
        with tempfile.TemporaryDirectory() as temp:
            package = build_package(Path(temp)); victim = package / "media/technical-sheets/s1.pdf"
            target = package / "media/technical-sheets/s2.pdf"; victim.unlink()
            try: victim.symlink_to(target)
            except OSError: self.skipTest("symlink creation unavailable")
            result = self.run_cli("--mode", "VerifyPackage", "--package", str(package.resolve()))
        self.assertEqual(2, result.returncode); self.assertEqual(["LINK_REJECTED"], json.loads(result.stdout)["blockers"])

if __name__ == "__main__": unittest.main()
