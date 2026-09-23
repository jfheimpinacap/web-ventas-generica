import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools/deployment/New-JemNexusProductionRelease.ps1"
DOC = ROOT / "docs/deployment/PRODUCTION_RELEASE_346.md"


class ProductionReleaseToolContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.doc = DOC.read_text(encoding="utf-8")

    def test_plan_only_precedes_all_build_and_output_mutation(self):
        plan = self.script.index("if ($PlanOnly)")
        first_output_create = self.script.index("New-Item -ItemType Directory -Path $outputPath")
        first_build = self.script.index("Invoke-CheckedCommand dotnet $publishArgs")
        self.assertLess(plan, first_output_create)
        self.assertLess(plan, first_build)
        plan_block = self.script[plan:first_output_create]
        self.assertIn("no se ejecutaran dotnet, npm, Node, EF ni compresion", plan_block)

    def test_main_is_default_and_work_requires_explicit_override(self):
        self.assertIn("[string]$ExpectedBranch = 'main'", self.script)
        self.assertNotIn("$ExpectedBranch = 'work'", self.script)
        self.assertIn("-ExpectedBranch work", self.doc)
        self.assertIn('-ExpectedBranch "main"', self.doc)

    def test_branch_validation_rejects_detached_head_and_mismatch(self):
        self.assertIn("[string]::IsNullOrWhiteSpace($branch)", self.script)
        self.assertIn("$branchOutput = @(& git -C $repoRoot branch --show-current)", self.script)
        self.assertIn("HEAD esta detached", self.script)
        self.assertIn("if ($branch -ne $ExpectedBranch)", self.script)
        self.assertIn("Rama inesperada: '$branch'; se esperaba '$ExpectedBranch'", self.script)

    def test_expected_commit_is_full_exact_head_and_required_for_release(self):
        self.assertIn("$ExpectedCommit -cnotmatch '^[0-9a-fA-F]{40}$'", self.script)
        self.assertIn("if ($commit -cne $expectedCommitCanonical)", self.script)
        self.assertIn("ExpectedCommit es obligatorio para generar un release real", self.script)
        self.assertLess(self.script.index("if ($commit -cne $expectedCommitCanonical)"), self.script.index("$shortSha = $commit.Substring(0, 12)"))
        self.assertIn("commit = [ordered]@{ full = $commit; short = $shortSha }", self.script)
        full_sha = re.compile(r"^[0-9a-fA-F]{40}$")
        head = "a" * 40
        self.assertIsNone(full_sha.fullmatch(head[:12]))
        self.assertIsNotNone(full_sha.fullmatch("b" * 40))
        self.assertNotEqual(head, "b" * 40)

    def test_deterministic_artifact_names_and_exact_migration_limits(self):
        for value in (
            '"jem-nexus-backend-$shortSha.zip"',
            '"jem-nexus-frontend-$shortSha.zip"',
            "'jem-nexus-migrations-20260830000000-to-20260922000000.sql'",
            "'20260830000000_PreserveQuotesWhenDeletingProducts'",
            "'20260922000000_AddCommercialQuoteIssuedBy'",
        ):
            self.assertIn(value, self.script)

    def test_configuration_and_frontend_exclusions_are_explicit(self):
        for name in (
            "appsettings.json",
            "appsettings.Development.json",
            "appsettings.Production.json",
            "web.config",
            "App_Data/",
            ".user.ini",
            "*.map",
        ):
            self.assertIn(name, self.script)

    def test_insecure_frontend_targets_are_rejected(self):
        self.assertIn("$uri.Scheme -ne 'https'", self.script)
        for marker in ("localhost", "127", "192", "169", "0xFC", "0xFE"):
            self.assertIn(marker, self.script)
        self.assertRegex(self.script, r"localhost\|127\\\.0\\\.0\\\.1")

    def test_sql_preflight_and_postflight_contracts(self):
        for marker in (
            "SET XACT_ABORT ON",
            "DB_NAME() <> N'$ExpectedDatabase'",
            "SCHEMA_NAME() <> N'$ExpectedSchema'",
            "$ExpectedSchema = 'jemnexusb_api'",
            "#JemNexusReleasePreflight",
            ") <> 20 THROW",
            "users.manage",
            "NO_ACTION",
            "POSTFLIGHT_OK",
        ):
            self.assertIn(marker, self.script)
        self.assertIn("Assert-GeneratedMigrationSql $efSql", self.script)
        self.assertIn("SQL EMITIDO POR EF CORE; NO MODIFICADO", self.script)

    def test_sql_state_survives_go_and_outer_commit_follows_postflight(self):
        create = self.script.index("CREATE TABLE #JemNexusReleasePreflight")
        store = self.script.index("INSERT INTO #JemNexusReleasePreflight")
        begin = self.script.index("BEGIN TRANSACTION;")
        first_go = self.script.index("GO", begin)
        read = self.script.index("SELECT [QuoteRequestCount] FROM #JemNexusReleasePreflight")
        commit = self.script.index("COMMIT TRANSACTION;", read)
        drop = self.script.index("DROP TABLE #JemNexusReleasePreflight", commit)
        self.assertLess(create, store)
        self.assertLess(store, begin)
        self.assertLess(begin, first_go)
        self.assertLess(first_go, read)
        self.assertLess(read, commit)
        self.assertLess(commit, drop)
        self.assertNotIn("BEGIN TRY", self.script)
        self.assertNotIn("END TRY", self.script)
        self.assertIn("una única ventana, conexión y sesión de SSMS", self.doc)

    def test_manifest_hashes_and_preserve_contract(self):
        for marker in ("manifest.json", "SHA256SUMS.txt", "Get-FileHash", "size_bytes", "sha256"):
            self.assertIn(marker, self.script)
        preserve = re.search(r"\$preserve = @\((.*?)\)\n", self.script, re.DOTALL)
        self.assertIsNotNone(preserve)
        self.assertEqual(
            re.findall(r"'([^']*)'", preserve.group(1)),
            ["Backend:", "appsettings.json", "web.config", "logs", "", "Frontend:", "App_Data", ".user.ini", "web.config"],
        )

    def test_deletion_is_limited_to_exact_staging(self):
        removals = re.findall(r"Remove-Item[^\n]+", self.script)
        self.assertEqual(len(removals), 1)
        self.assertIn("-LiteralPath $stagingRoot", removals[0])
        self.assertNotIn("$HOME", self.script)
        self.assertIn("ZIP de destino ya existe", self.script)
        self.assertIn("OutputRoot debe estar completamente fuera del repositorio", self.script)

    def test_no_embedded_secret_assignment_or_connection_string(self):
        self.assertNotRegex(self.script, r"(?i)(password|token|connectionstring)\s*=\s*['\"][^'\"]+['\"]")
        self.assertNotIn("Server=", self.script)
        self.assertNotIn("User Id=", self.script)

    def test_documentation_names_only_real_vite_variables(self):
        for name in ("VITE_API_BASE_URL", "VITE_WHATSAPP_NUMBER", "VITE_CONTACT_EMAIL", "VITE_GTM_ID"):
            self.assertIn(name, self.doc)
        self.assertIn("VITE_PUBLIC_SITE_URL", self.doc)
        self.assertIn("no se consume", self.doc)

    def test_documentation_uses_dynamic_merged_main_identity(self):
        self.assertGreaterEqual(self.doc.count('$ReleaseCommit = (git rev-parse HEAD).Trim()'), 2)
        self.assertGreaterEqual(self.doc.count('-ExpectedCommit $ReleaseCommit'), 2)
        retired_shas = (
            "b9a4eac98d151d8c9a61" + "91e036fe3dffc498dd57",
            "3f8a3cb6842a2683029d" + "a78dc76bcfcbf2ae3fe0",
        )
        for retired_sha in retired_shas:
            self.assertNotIn(retired_sha, self.doc)
        self.assertIn("git rev-parse HEAD` coincide exactamente con `origin/main", self.doc)


if __name__ == "__main__":
    unittest.main()
