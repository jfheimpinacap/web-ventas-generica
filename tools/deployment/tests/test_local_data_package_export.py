import hashlib
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools/deployment/Export-JemNexusLocalDataPackage.ps1"
TEXT = SCRIPT.read_text(encoding="utf-8")
PS51_MANIFEST_TEST = ROOT / "tools/deployment/tests/Test-LocalDataPackageManifest.WindowsPowerShell.ps1"

TRANSFER_TABLES = [
    "AppUsers", "AppUserPermissions", "Brands", "Categories", "Suppliers",
    "TechnicalSheets", "Products", "ProductImages", "ProductSpecs", "Promotions",
    "HomeSectionItems", "QuoteRequests", "CustomerProfiles", "CommercialQuotes",
    "CommercialQuoteItems", "CommercialQuoteFolioCounters",
    "CommercialQuoteIssueIdempotencyRecords",
]


def safe_file(root, relative):
    """Portable behavioral model of Resolve-SafeFile for synthetic fixtures."""
    root = pathlib.Path(root).resolve(strict=True)
    raw = pathlib.Path(relative)
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("unsafe")
    candidate = root / raw
    if any(part.is_symlink() for part in [candidate, *candidate.parents] if part != root.parent):
        raise ValueError("reparse")
    resolved = candidate.resolve(strict=True)
    if root not in resolved.parents:
        raise ValueError("outside")
    return resolved


def prepare_synthetic_package(source, output, *, fail_before_publish=False):
    """Models copy, hash, validation, cleanup and atomic publication semantics."""
    staging = output / ".staging-test"
    final = output / "jemnexus-local-data-package-test"
    staging.mkdir()
    try:
        rows = {
            "AppUsers": [{"Id": 7}],
            "CommercialQuotes": [{"Id": 31, "ResponsibleSellerId": 7, "IssuedById": 7}],
            "CommercialQuoteItems": [{"Id": 41, "CommercialQuoteId": 31, "ProductId": 11}],
            "AppUserPermissions": [{"UserId": 7, "Permission": "quotes.read"}],
        }
        assert rows["CommercialQuotes"][0]["ResponsibleSellerId"] == rows["AppUsers"][0]["Id"]
        assert rows["CommercialQuoteItems"][0]["CommercialQuoteId"] == rows["CommercialQuotes"][0]["Id"]
        data = staging / "data"
        data.mkdir()
        hashes = {}
        for table, records in rows.items():
            path = data / f"{table}.json"
            path.write_text(json.dumps(records, separators=(",", ":")), encoding="utf-8")
            hashes[table] = hashlib.sha256(path.read_bytes()).hexdigest()
        media = staging / "media/images/product-images/11"
        media.mkdir(parents=True)
        referenced = safe_file(source, "product-images/11/referenced.jpg")
        copied = media / referenced.name
        copied.write_bytes(referenced.read_bytes())
        manifest = {
            "status": "PREPARED_LOCAL_NOT_AUTHORIZED_FOR_PRODUCTION_APPLY",
            "exclusions": {"refreshTokenRowsIncluded": 0, "orphanImageFilesIncluded": 0},
            "tables": {"sha256": hashes},
            "media": [{"path": str(copied.relative_to(staging)), "sha256": hashlib.sha256(copied.read_bytes()).hexdigest()}],
        }
        (staging / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        if fail_before_publish:
            raise ValueError("synthetic validation failure")
        staging.rename(final)
        return final
    except Exception:
        if staging.exists():
            for child in sorted(staging.rglob("*"), reverse=True):
                child.unlink() if child.is_file() else child.rmdir()
            staging.rmdir()
        raise


class ExportContractTests(unittest.TestCase):
    def test_modes_and_connection_are_local_only_and_no_apply_exists(self):
        self.assertIn("[ValidateSet('PlanOnly', 'ExportLocal')]", TEXT)
        self.assertIn("Data Source=$ExpectedInstance", TEXT)
        self.assertIn("ApplicationIntent=ReadOnly", TEXT)
        self.assertNotIn("ProductionConnection", TEXT)
        self.assertNotIn("Invoke-Sqlcmd", TEXT)
        self.assertNotIn("DELETE FROM", TEXT.upper())

    def test_exactly_17_business_tables_and_sessions_are_excluded(self):
        table_block = TEXT.split("$Tables = @(", 1)[1].split(")", 1)[0]
        for table in TRANSFER_TABLES:
            self.assertIn(f"'{table}'", table_block)
        self.assertEqual(table_block.count("'"), 34)
        self.assertNotIn("'AppRefreshTokens'", table_block)
        self.assertIn("tables=@('AppRefreshTokens','__EFMigrationsHistory')", TEXT)
        self.assertIn("refreshTokenRowsIncluded=0", TEXT)

    def test_plan_only_exits_before_inventory_media_staging_and_connection(self):
        plan = TEXT.index("if ($Mode -eq 'PlanOnly')")
        plan_exit = TEXT.index("exit 0", plan)
        for marker in ("Get-Content -LiteralPath $inventoryFile", "CreateDirectory($staging)", "$connection.Open()"):
            self.assertGreater(TEXT.index(marker), plan_exit)

    def test_real_off_on_database_state_uses_serializable_not_snapshot(self):
        """Offline contract check, not a dynamic SQL Server validation."""
        self.assertIn("BeginTransaction([Data.IsolationLevel]::Serializable)", TEXT)
        self.assertNotIn("BeginTransaction([Data.IsolationLevel]::Snapshot)", TEXT)
        self.assertNotIn("ALTER DATABASE", TEXT.upper())

    def test_every_capture_query_receives_the_one_connection_and_transaction(self):
        """Audit the script call sites; this does not execute SqlClient."""
        call_lines = [
            line.strip() for line in TEXT.splitlines()
            if "Invoke-Select $connection" in line
        ]
        self.assertEqual(len(call_lines), 4)
        self.assertTrue(all("Invoke-Select $connection $transaction" in line for line in call_lines))
        self.assertEqual(TEXT.count("BeginTransaction("), 1)
        self.assertIn("$command.Transaction = $Transaction", TEXT)
        self.assertIn("SqlDataAdapter $command", TEXT)

    def test_serializable_is_released_before_any_media_filesystem_work(self):
        commit = TEXT.index("$transaction.Commit()")
        media_inventory = TEXT.index("$inventoryMedia=@{}")
        first_media_resolution = TEXT.index("Resolve-SafeFile $imageRoot")
        self.assertLess(commit, media_inventory)
        self.assertLess(commit, first_media_resolution)
        self.assertLess(commit, TEXT.index("Write-Json $file $exportedRows[$name]"))
        self.assertIn("$transaction.Dispose(); $transaction=$null", TEXT[commit:media_inventory])
        self.assertIn("$connection.Close(); $connection.Dispose(); $connection=$null", TEXT[commit:media_inventory])

    def test_ids_and_relationship_fields_are_serialized_without_projection(self):
        self.assertIn("foreach ($column in $Table.Columns)", TEXT)
        self.assertIn("$record[$column.ColumnName]", TEXT)
        self.assertIn("CASE WHEN pk.column_id IS NULL", TEXT)
        self.assertIn("ORDER BY {2}", TEXT)
        self.assertIn("fk.is_disabled=1 OR fk.is_not_trusted=1", TEXT)

    def test_referenced_file_is_packaged_and_orphan_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source = root / "source"
            referenced = source / "product-images/11/referenced.jpg"
            orphan = source / "product-images/99/orphan.jpg"
            referenced.parent.mkdir(parents=True)
            orphan.parent.mkdir(parents=True)
            referenced.write_bytes(b"referenced")
            orphan.write_bytes(b"orphan")
            output = root / "private"
            output.mkdir()
            package = prepare_synthetic_package(source, output)
            self.assertTrue((package / "media/images/product-images/11/referenced.jpg").is_file())
            self.assertFalse(any(path.name == "orphan.jpg" for path in package.rglob("*")))
            manifest = json.loads((package / "manifest.json").read_text())
            self.assertEqual(manifest["exclusions"]["refreshTokenRowsIncluded"], 0)
            self.assertEqual(manifest["exclusions"]["orphanImageFilesIncluded"], 0)

    def test_unsafe_missing_and_symlink_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            media = root / "media"
            media.mkdir()
            (media / "ok.bin").write_bytes(b"ok")
            self.assertEqual(safe_file(media, "ok.bin"), media / "ok.bin")
            for unsafe in ("../outside.bin", str((root / "absolute.bin").resolve()), "missing.bin"):
                with self.assertRaises((ValueError, FileNotFoundError)):
                    safe_file(media, unsafe)
            target = media / "ok.bin"
            link = media / "link.bin"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValueError):
                safe_file(media, "link.bin")

    def test_failure_removes_staging_and_never_publishes_final_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source = root / "source"
            file = source / "product-images/11/referenced.jpg"
            file.parent.mkdir(parents=True)
            file.write_bytes(b"referenced")
            output = root / "private"
            output.mkdir()
            with self.assertRaises(ValueError):
                prepare_synthetic_package(source, output, fail_before_publish=True)
            self.assertEqual(list(output.iterdir()), [])

    def test_sql_failure_path_cannot_publish_and_only_deletes_current_staging(self):
        publish = TEXT.index("[IO.Directory]::Move($staging,$finalPath)")
        catch = TEXT.index("} catch {")
        self.assertLess(publish, catch)
        cleanup = TEXT[catch:]
        self.assertIn("$transaction.Rollback()", cleanup)
        self.assertIn("[IO.Directory]::Delete($staging,$true)", cleanup)
        self.assertNotIn("Get-ChildItem", cleanup)
        self.assertNotIn("$finalPath", cleanup)

    def test_source_contains_private_staging_hash_and_atomic_publish_controls(self):
        self.assertIn("SetAccessRuleProtection($true, $false)", TEXT)
        self.assertIn("Get-FileHash -LiteralPath $Path -Algorithm SHA256", TEXT)
        self.assertIn("Imagen cambiada respecto del inventario", TEXT)
        self.assertIn("Ficha cambiada respecto del inventario", TEXT)
        self.assertIn("[IO.Directory]::Move($staging,$finalPath)", TEXT)
        self.assertIn("[IO.Directory]::Delete($staging,$true)", TEXT)
        self.assertLess(TEXT.index("Get-Hash $inventoryFile"), TEXT.index("[IO.Directory]::Move($staging,$finalPath)"))

    def test_generic_media_list_is_materialized_without_array_subexpression(self):
        self.assertIn("$media=New-Object Collections.Generic.List[object]", TEXT)
        self.assertIn("$mediaFiles=[object[]]$media.ToArray()", TEXT)
        self.assertIn("files=$mediaFiles", TEXT)
        self.assertNotIn("files=@($media)", TEXT)
        self.assertIn("$roundTripMediaFiles.Count -ne 177", TEXT)

    def test_windows_powershell_manifest_harness_covers_required_cardinalities(self):
        harness = PS51_MANIFEST_TEST.read_text(encoding="utf-8")
        self.assertIn("#requires -Version 5.1", harness)
        self.assertIn("New-Object Collections.Generic.List[object]", harness)
        self.assertIn("[object[]]$media.ToArray()", harness)
        self.assertIn("foreach ($count in 0, 1, 177)", harness)
        self.assertIn("$files = @($roundTrip.media.files)", harness)
        self.assertIn("$files[$index].sha256", harness)


if __name__ == "__main__":
    unittest.main()
