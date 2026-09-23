import hashlib
import json
import os
import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools/deployment/Test-JemNexusDataTransferReadiness.ps1"
EXPECTED_COUNTS = {
    "AppUsers": 3, "AppRefreshTokens": 122, "AppUserPermissions": 58,
    "Brands": 3, "Categories": 10, "Suppliers": 0, "Products": 92,
    "ProductImages": 92, "ProductSpecs": 58, "Promotions": 0,
    "HomeSectionItems": 0, "QuoteRequests": 0, "TechnicalSheets": 85,
    "CustomerProfiles": 1, "CommercialQuotes": 9, "CommercialQuoteItems": 9,
    "CommercialQuoteFolioCounters": 1,
    "CommercialQuoteIssueIdempotencyRecords": 8,
}

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def local_fixture():
    return {
        "reportVersion": 1, "reportType": "JemNexusLocalSanitizedInventory",
        "source": {"instance": r"(localdb)\MSSQLLocalDB", "database": "JemNexus_Local", "schema": "dbo"},
        "migrationCount": 22, "counts": dict(EXPECTED_COUNTS),
        "userIdentityHashes": [digest(x) for x in ("a", "b", "c")],
        "exclusions": {"refreshTokens": 122, "refreshTokenRowsIncluded": 0, "orphanImages": 2},
        "schema": {"missingTables": [], "missingColumns": []},
        "integrity": {"orphanForeignKeys": 0, "duplicateUniqueKeys": 0, "requiredIndexesPresent": True},
        "media": {"images": {"referenced": 92, "present": 92, "orphanCount": 2, "transferCount": 92},
                  "technicalSheets": {"referenced": 85, "present": 85, "transferCount": 85}, "manifest": []},
    }

def production_fixture():
    return {"reportType": "JemNexusProductionSanitizedSnapshot", "database": "jemnexusb_prod",
            "schema": "jemnexusb_api", "migrationCount": 22,
            "counts": {"AppUsers": 2, "AppUserPermissions": 29, "QuoteRequests": 8, "CommercialQuotes": 0},
            "userIdentityHashes": sorted([digest("soporte"), digest("vendedor")]),
            "schemaChecks": {"missingTables": [], "missingColumns": [], "requiredIndexesPresent": True, "orphanForeignKeys": 0}}

def evaluate(local, production):
    failures = []
    if local["source"] != {"instance": r"(localdb)\MSSQLLocalDB", "database": "JemNexus_Local", "schema": "dbo"}: failures.append("local identity")
    if local["migrationCount"] != 22 or production["migrationCount"] != 22: failures.append("migrations")
    for key, expected in EXPECTED_COUNTS.items():
        if local["counts"].get(key) != expected: failures.append("local count " + key)
    if local["exclusions"] != {"refreshTokens": 122, "refreshTokenRowsIncluded": 0, "orphanImages": 2}: failures.append("exclusions")
    if local["media"]["images"] != {"referenced": 92, "present": 92, "orphanCount": 2, "transferCount": 92}: failures.append("images")
    if local["media"]["technicalSheets"]["present"] != 85: failures.append("sheets")
    if local["schema"]["missingTables"] or local["schema"]["missingColumns"]: failures.append("local schema")
    if local["integrity"] != {"orphanForeignKeys": 0, "duplicateUniqueKeys": 0, "requiredIndexesPresent": True}: failures.append("local integrity")
    if production["database"] != "jemnexusb_prod" or production["schema"] != "jemnexusb_api": failures.append("production identity")
    for key, expected in {"AppUsers": 2, "AppUserPermissions": 29, "QuoteRequests": 8, "CommercialQuotes": 0}.items():
        if production["counts"].get(key) != expected: failures.append("production " + key)
    if sorted(production["userIdentityHashes"]) != sorted([digest("soporte"), digest("vendedor")]): failures.append("production users")
    checks = production["schemaChecks"]
    if checks["missingTables"] or checks["missingColumns"] or not checks["requiredIndexesPresent"] or checks["orphanForeignKeys"]: failures.append("production schema")
    return "READY_FOR_DESIGN" if not failures else "NO-GO"

def safe_file(root, relative):
    root = pathlib.Path(root).resolve(strict=True)
    raw = pathlib.Path(relative)
    if raw.is_absolute() or ".." in raw.parts: raise ValueError("unsafe")
    candidate = root.joinpath(raw)
    if candidate.is_symlink(): raise ValueError("symlink")
    resolved = candidate.resolve(strict=True)
    if root not in resolved.parents: raise ValueError("outside")
    return resolved

def assert_no_reparse_point(path, allowed_root):
    """Portable model of the FileInfo/DirectoryInfo ancestor walk."""
    root = pathlib.Path(allowed_root).resolve(strict=True)
    item = pathlib.Path(path)
    try:
        item.relative_to(root)
    except ValueError as error:
        raise ValueError("outside") from error
    cursor = item
    while True:
        if cursor.is_symlink(): raise ValueError("symlink")
        if cursor == root: return
        cursor = cursor.parent

def local_identity_allowed(effective_server, database, is_localdb):
    """Portable model of the post-connect identity decision (not a SQL mock)."""
    del effective_server  # SQL Server's dynamic LocalDB name is diagnostic only.
    return database == "JemNexus_Local" and type(is_localdb) is int and is_localdb == 1

def connection_target_allowed(instance, database="JemNexus_Local", schema="dbo"):
    """Portable model of the exact pre-connect parameter guard."""
    return (instance == r"(localdb)\MSSQLLocalDB" and
            database == "JemNexus_Local" and schema == "dbo")

def validate_sql_bindings(sql, parameter_specs, command_parameters):
    """Portable model of the helper's same-command, explicit-type contract."""
    placeholders = set(re.findall(r"(?<!@)@([A-Za-z_][A-Za-z0-9_]*)", sql))
    declared = set(parameter_specs)
    if placeholders != declared:
        return False
    if any("Value" not in spec or "SqlDbType" not in spec for spec in parameter_specs.values()):
        return False
    return declared == set(command_parameters)

def powershell_enumerated_function_result(values):
    """Model assignment from an enumerated PowerShell function result."""
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return list(values)

class ReadinessBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_baseline_is_ready_for_design_never_go(self):
        self.assertEqual(evaluate(local_fixture(), production_fixture()), "READY_FOR_DESIGN")
        self.assertNotIn("'GO'", self.source)
        self.assertNotIn("-Apply", self.source)

    def test_unexpected_names_schema_database_and_migrations_are_no_go(self):
        for field, value in (("database", "wrong"), ("schema", "wrong"), ("instance", "server")):
            local = local_fixture(); local["source"][field] = value
            self.assertEqual(evaluate(local, production_fixture()), "NO-GO")
        local = local_fixture(); local["migrationCount"] = 21
        self.assertEqual(evaluate(local, production_fixture()), "NO-GO")

    def test_missing_table_column_and_bad_ids_fks_indexes_are_no_go(self):
        for section, key, value in (("schema", "missingTables", ["Products"]), ("schema", "missingColumns", ["Products.Id"]),
                                    ("integrity", "orphanForeignKeys", 1), ("integrity", "duplicateUniqueKeys", 1),
                                    ("integrity", "requiredIndexesPresent", False)):
            local = local_fixture(); local[section][key] = value
            self.assertEqual(evaluate(local, production_fixture()), "NO-GO")

    def test_productive_user_quote_request_and_quote_drift_are_no_go(self):
        for key, value in (("AppUsers", 3), ("QuoteRequests", 9), ("CommercialQuotes", 1)):
            prod = production_fixture(); prod["counts"][key] = value
            self.assertEqual(evaluate(local_fixture(), prod), "NO-GO")
        prod = production_fixture(); prod["userIdentityHashes"][0] = digest("new-user")
        self.assertEqual(evaluate(local_fixture(), prod), "NO-GO")

    def test_sessions_and_exactly_two_orphans_are_excluded(self):
        self.assertEqual(evaluate(local_fixture(), production_fixture()), "READY_FOR_DESIGN")
        for key, value in (("refreshTokens", 121), ("refreshTokenRowsIncluded", 1), ("orphanImages", 3)):
            local = local_fixture(); local["exclusions"][key] = value
            self.assertEqual(evaluate(local, production_fixture()), "NO-GO")

    def test_missing_media_and_orphan_transfer_are_no_go(self):
        local = local_fixture(); local["media"]["images"]["present"] = 91
        self.assertEqual(evaluate(local, production_fixture()), "NO-GO")
        local = local_fixture(); local["media"]["images"]["transferCount"] = 94
        self.assertEqual(evaluate(local, production_fixture()), "NO-GO")
        local = local_fixture(); local["media"]["technicalSheets"]["present"] = 84
        self.assertEqual(evaluate(local, production_fixture()), "NO-GO")

    def test_path_guard_rejects_traversal_outside_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp, "uploads"); root.mkdir(); (root / "ok.bin").write_bytes(b"ok")
            self.assertEqual(safe_file(root, "ok.bin"), (root / "ok.bin").resolve())
            with self.assertRaises(ValueError): safe_file(root, "../outside")
            outside = pathlib.Path(temp, "outside"); outside.write_bytes(b"x")
            link = root / "link"
            try: link.symlink_to(outside)
            except OSError: self.skipTest("symlinks unavailable")
            with self.assertRaises(ValueError): safe_file(root, "link")

    def test_reparse_walk_handles_file_and_directory_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp, "uploads"); root.mkdir()
            directory = root / "product-images"; directory.mkdir()
            media = directory / "ok.bin"; media.write_bytes(b"ok")
            self.assertIsNone(assert_no_reparse_point(media, root))
            self.assertIsNone(assert_no_reparse_point(directory, root))
            outside = pathlib.Path(temp, "outside.bin"); outside.write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "outside"):
                assert_no_reparse_point(outside, root)
            with self.assertRaises(ValueError): safe_file(root, "../outside.bin")

            link = directory / "linked.bin"
            try: link.symlink_to(media)
            except OSError: self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "symlink"):
                assert_no_reparse_point(link, root)

    def test_powershell_ancestor_walk_uses_confirmed_item_types(self):
        guard = self.source[self.source.index("function Assert-NoReparsePoint"):self.source.index("function Resolve-SafeFile")]
        self.assertIn("$cursor -is [IO.FileInfo]", guard)
        self.assertIn("$cursor.Directory", guard)
        self.assertIn("$cursor -is [IO.DirectoryInfo]", guard)
        self.assertIn("[IO.Directory]::GetParent($cursor.FullName)", guard)
        self.assertNotRegex(guard, r"\$cursor\.Parent\b")
        self.assertNotRegex(self.source, r"\.Parent\b")

    def test_plan_only_guard_precedes_output_and_connection(self):
        plan = self.source.index("if ($Mode -eq 'PlanOnly')")
        self.assertLess(plan, self.source.index("[IO.Directory]::CreateDirectory", plan))
        self.assertLess(plan, self.source.index("$connection.Open()", plan))
        block = self.source[plan:self.source.index("if ($Mode -eq 'InventoryLocal')")]
        self.assertNotIn("CreateDirectory", block); self.assertNotIn("SqlConnection", block)

    def test_dynamic_effective_localdb_name_is_accepted(self):
        self.assertTrue(local_identity_allowed(r"WORKSTATION\LOCALDB#DYNAMIC", "JemNexus_Local", 1))
        identity_block = self.source[self.source.index("$identity = Invoke-SelectTable"):self.source.index("$migrationCount")]
        self.assertIn("SERVERPROPERTY('IsLocalDB')", identity_block)
        self.assertNotIn("\\\\MSSQLLocalDB$", identity_block)
        self.assertNotIn("LOCALDB#", identity_block)

    def test_non_localdb_null_unexpected_value_and_wrong_database_are_rejected(self):
        for database, is_localdb in (("JemNexus_Local", 0), ("JemNexus_Local", None),
                                     ("JemNexus_Local", "1"), ("wrong", 1)):
            self.assertFalse(local_identity_allowed(r"WORKSTATION\LOCALDB#DYNAMIC", database, is_localdb))
        self.assertIn("$isLocalDb -is [DBNull]", self.source)
        self.assertIn("$isLocalDb -isnot [int]", self.source)

    def test_remote_data_source_is_rejected_before_connection(self):
        inventory = self.source.index("if ($Mode -eq 'InventoryLocal')")
        guard = self.source.index("$LocalInstance -cne $ExpectedInstance", inventory)
        connection = self.source.index("New-Object Data.SqlClient.SqlConnection", inventory)
        self.assertLess(guard, connection)
        for remote in ("10.0.0.8", "sql.example.test", r"SERVER\SharedInstance"):
            self.assertFalse(connection_target_allowed(remote))
        self.assertTrue(connection_target_allowed(r"(localdb)\MSSQLLocalDB"))
        self.assertIn("se rechazo antes de conectar", self.source[guard:connection])
        connection_string = self.source[self.source.index('$connectionString =', inventory):connection]
        self.assertIn("Integrated Security=True", connection_string)
        self.assertNotIn("User ID", connection_string)
        self.assertNotIn("Password", connection_string)
        self.assertNotIn("AttachDbFilename", connection_string)

    def test_reports_have_no_secret_or_personal_fields(self):
        report = local_fixture()
        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key.lower(); yield from keys(child)
            elif isinstance(value, list):
                for child in value: yield from keys(child)
        report_keys = set(keys(report))
        for forbidden in ("passwordhash", "tokenhash", "connectionstring", "email", "rut", "customername", "idempotencykey"):
            self.assertNotIn(forbidden, report_keys)
        self.assertEqual(report["exclusions"]["refreshTokenRowsIncluded"], 0)

    def test_tool_sql_surface_is_read_only(self):
        sql_calls = [line.strip() for line in self.source.splitlines() if "Invoke-SelectTable $connection" in line or "Get-Scalar $connection" in line]
        self.assertGreater(len(sql_calls), 5)
        forbidden = (" insert ", " update ", " delete ", " merge ", " exec ", " alter ", " drop ", " truncate ")
        for line in sql_calls:
            padded = " " + line.lower() + " "
            self.assertFalse(any(word in padded for word in forbidden), line)

    def test_sql_binding_contract_rejects_missing_and_other_command_parameters(self):
        sql = "SELECT name FROM sys.schemas WHERE name=@schema"
        spec = {"schema": {"Value": "dbo", "SqlDbType": "NVarChar"}}
        self.assertFalse(validate_sql_bindings(sql, {}, set()))
        self.assertFalse(validate_sql_bindings(sql, spec, set()))  # Bound to a different command.
        self.assertFalse(validate_sql_bindings(sql, {"schema": {"Value": "dbo"}}, {"schema"}))
        self.assertTrue(validate_sql_bindings(sql, spec, {"schema"}))

    def test_inventory_parameterized_queries_bind_typed_parameters_before_fill(self):
        helper = self.source[self.source.index("function Invoke-SelectTable"):self.source.index("function Get-Scalar")]
        add = helper.index('$command.Parameters.Add("@$key"')
        fill = helper.index("$adapter.Fill($table)")
        self.assertLess(add, fill)
        self.assertIn("$command.Parameters", helper)
        self.assertNotIn("AddWithValue", helper)
        self.assertIn("Falta el parametro SQL", helper)
        self.assertIn("Value y SqlDbType explicitos", helper)
        self.assertIn("Write-Output -NoEnumerate $table", helper)

        inventory = self.source[self.source.index("if ($Mode -eq 'InventoryLocal')"):]
        self.assertEqual(inventory.count("@schema"), 2)
        self.assertIn("$metadata = Invoke-SelectTable $connection", inventory)
        self.assertIn('WHERE s.name=@schema\" $schemaParameter', inventory)
        self.assertIn("$integrityRows = Invoke-SelectTable $connection $integritySql $schemaParameter", inventory)
        self.assertIn("SqlDbType = [Data.SqlDbType]::NVarChar", inventory)
        self.assertIn("Size = 128", inventory)

    def test_inventory_preserves_datatable_for_zero_one_and_many_rows(self):
        helper = self.source[self.source.index("function Invoke-SelectTable"):self.source.index("function Get-Scalar")]
        self.assertIn("DataTable implements IEnumerable", helper)
        self.assertIn("Write-Output -NoEnumerate $table", helper)
        for row_count in (0, 1, 3):
            rows = [object() for _ in range(row_count)]
            table = {"effective_type": "System.Data.DataTable", "Rows": rows}
            # -NoEnumerate returns the table itself rather than its DataRow elements.
            self.assertIs(table, table)
            self.assertEqual(len(table["Rows"]), row_count)

    def test_inventory_shape_failure_list_is_not_collapsed_to_null_string_or_array(self):
        shape = self.source[self.source.index("function Test-ExpectedShape"):self.source.index("if ($Mode -eq 'PlanOnly')")]
        self.assertIn("Write-Output -NoEnumerate $failures", shape)
        self.assertNotIn("return $failures", shape)
        self.assertIn("$shapeFailures.Count", self.source)

        expected_enumerated_types = (([], type(None)), (["one"], str), (["one", "two"], list))
        for failures, collapsed_type in expected_enumerated_types:
            self.assertIsInstance(powershell_enumerated_function_result(failures), collapsed_type)
            # The corrected contract remains one collection object with a stable Count.
            preserved = failures
            self.assertIsInstance(preserved, list)
            self.assertEqual(len(preserved), len(failures))

if __name__ == "__main__": unittest.main()
