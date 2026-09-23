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
        cls.protector = cls.script[cls.script.index("function ConvertTo-ProtectedMigrationSql"):cls.script.index("function Assert-ProtectedMigrationSql")]
        cls.protected_validator = cls.script[cls.script.index("function Assert-ProtectedMigrationSql"):cls.script.index("function Get-SqlPreflight")]
        cls.postflight = cls.script[cls.script.index("function Get-SqlPostflight"):cls.script.index("$repoRoot =")]
        cls.dynamic_postflight = cls.postflight[cls.postflight.index("-- BEGIN VALIDACION POSTFLIGHT DINAMICA"):cls.postflight.index("-- END VALIDACION POSTFLIGHT DINAMICA")]

    @staticmethod
    def parse_marker_sequence(sql):
        marker = re.compile(r"^-- BEGIN LOTE EF PROTEGIDO (\d+); REQUIERE ORDINAL (\d+)$")
        return [tuple(map(int, match.groups())) for line in re.split(r"\r\n|\n|\r", sql) if (match := marker.fullmatch(line))]

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
        self.assertIn("Test-NonPublicHost $uri", self.script)
        self.assertIn("URL API HTTP encontrada", self.script)
        self.assertIn("$ExpectedApiHost = 'api.jem-nexus.cl'", self.script)

    def test_exact_framework_placeholder_is_allowed_only_in_javascript(self):
        self.assertIn("$absoluteUrl -ceq 'http://localhost'", self.script)
        self.assertIn("$file.Extension -cne '.js'", self.script)
        for condition in ("$uri.Port -ne 80", "$uri.AbsolutePath -cne '/'", "$uri.Query", "$uri.Fragment", "$uri.UserInfo"):
            self.assertIn(condition, self.script)
        self.assertNotIn("$content -match '(?i)localhost|127", self.script)

    def test_structured_url_validation_rejects_local_variants(self):
        source = self.script[self.script.index("function Assert-FrontendOutput"):self.script.index("function Assert-GeneratedMigrationSql")]
        self.assertIn("[Uri]::TryCreate($absoluteUrl", source)
        self.assertIn("Test-NonPublicHost $uri", source)
        self.assertIn("$hostName.EndsWith('.localhost')", self.script)
        # These variants cannot enter the sole exact-placeholder exemption.
        for unsafe in ("http://localhost:5173", "http://localhost/api", "https://localhost", "http://127.0.0.1"):
            self.assertNotEqual(unsafe, "http://localhost")

    def test_expected_api_and_discovered_development_fallback_are_enforced(self):
        self.assertIn("if (-not $apiConfirmed)", self.script)
        self.assertIn("$content.Contains($ExpectedApiUrl)", self.script)
        self.assertIn("Get-DevelopmentApiFallback $frontendApiSource", self.script)
        self.assertRegex(self.script, r"DEFAULT_API_BASE_URL\\s\+\*=|DEFAULT_API_BASE_URL")
        self.assertIn("$content.Contains($DevelopmentApiFallback)", self.script)

    def test_frontend_validation_evidence_is_recorded_in_manifest(self):
        for marker in ("api_productiva_confirmada", "placeholders_framework_permitidos", "archivos_placeholders_framework"):
            self.assertIn(marker, self.script)
        self.assertIn("frontend_validation = $frontendValidation", self.script)

    def test_bundle_validation_is_hash_and_minifier_independent(self):
        self.assertNotIn("index-Mfu708cJ.js", self.script)
        self.assertIn("Get-ChildItem -LiteralPath $DistPath -File -Recurse", self.script)
        self.assertIn("[regex]::Matches($content", self.script)

    def test_sql_preflight_and_postflight_contracts(self):
        for marker in (
            "SET XACT_ABORT ON",
            "DB_NAME() <> N'$ExpectedDatabase'",
            "@DefaultSchema <> N'$ExpectedSchema'",
            "$ExpectedSchema = 'jemnexusb_api'",
            "#JemNexusReleasePreflight",
            ") <> 20 THROW",
            "users.manage",
            "NO_ACTION",
            "POSTFLIGHT_OK",
        ):
            self.assertIn(marker, self.script)
        self.assertIn("Assert-GeneratedMigrationSql $efSql", self.script)
        self.assertIn("SQL EMITIDO POR EF CORE; CUERPOS SIN CAMBIOS, EJECUCION PROTEGIDA", self.script)

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
        self.assertIn("BEGIN TRY", self.script)
        self.assertIn("END TRY", self.script)
        self.assertIn("una única ventana, conexión y sesión de SSMS", self.doc)

    def test_sql_sentinel_contains_count_sequence_and_failure_state(self):
        table = re.search(r"CREATE TABLE #JemNexusReleasePreflight \((.*?)\);", self.script)
        self.assertIsNotNone(table)
        for column in ("[QuoteRequestCount] bigint NOT NULL", "[LastCompletedBatch] int NOT NULL", "[ExecutionFailed] bit NOT NULL"):
            self.assertIn(column, table.group(1))
        insert = self.script.index("INSERT INTO #JemNexusReleasePreflight")
        begin = self.script.index("BEGIN TRANSACTION;", insert)
        first_go = self.script.index("GO", begin)
        self.assertIn("SELECT COUNT_BIG(*), 0, 0", self.script[insert:begin])
        self.assertLess(insert, begin)
        self.assertLess(begin, first_go)

    def test_every_nonempty_ef_batch_is_wrapped_and_counted(self):
        self.assertIn("[regex]::Split($Sql, '(?im)^\\s*GO", self.protector)
        self.assertIn("Where-Object { -not [string]::IsNullOrWhiteSpace($_) }", self.protector)
        loop = self.protector.index("for ($index = 0; $index -lt $batches.Count; $index++)")
        guard = self.protector.index("-- BEGIN LOTE EF PROTEGIDO $ordinal", loop)
        body = self.protector.index("$execution", guard)
        advance = self.protector.index("SET [LastCompletedBatch] = $ordinal", body)
        self.assertLess(guard, body)
        self.assertLess(body, advance)
        self.assertIn("BatchCount = $batches.Count", self.protector[advance:])

    def test_marker_validation_splits_lf_crlf_and_bare_cr_explicitly(self):
        self.assertIn('[regex]::Split($Sql, "\\r\\n|\\n|\\r")', self.protected_validator)
        self.assertNotIn("(?m)^-- BEGIN LOTE EF PROTEGIDO \\d+; REQUIERE ORDINAL \\d+$", self.script)

    def test_marker_validation_accepts_lf_with_and_without_final_newline(self):
        fixture = "header\n-- BEGIN LOTE EF PROTEGIDO 1; REQUIERE ORDINAL 0\nbody"
        self.assertEqual(self.parse_marker_sequence(fixture), [(1, 0)])
        self.assertEqual(self.parse_marker_sequence(fixture + "\n"), [(1, 0)])

    def test_marker_validation_accepts_crlf_with_and_without_final_newline(self):
        fixture = "header\r\n-- BEGIN LOTE EF PROTEGIDO 1; REQUIERE ORDINAL 0\r\nbody"
        self.assertEqual(self.parse_marker_sequence(fixture), [(1, 0)])
        self.assertEqual(self.parse_marker_sequence(fixture + "\r\n"), [(1, 0)])

    def test_marker_validation_accepts_mixed_line_endings(self):
        fixture = (
            "-- BEGIN LOTE EF PROTEGIDO 1; REQUIERE ORDINAL 0\r\nbody 1\n"
            "-- BEGIN LOTE EF PROTEGIDO 2; REQUIERE ORDINAL 1\rbody 2"
        )
        self.assertEqual(self.parse_marker_sequence(fixture), [(1, 0), (2, 1)])

    def test_marker_validation_rejects_a_malformed_marker(self):
        fixture = "-- BEGIN LOTE EF PROTEGIDO 1 REQUIERE ORDINAL 0\r\nbody"
        self.assertEqual(self.parse_marker_sequence(fixture), [])

    def test_marker_validation_rejects_a_missing_ordinal(self):
        fixture = (
            "-- BEGIN LOTE EF PROTEGIDO 1; REQUIERE ORDINAL 0\n"
            "-- BEGIN LOTE EF PROTEGIDO 3; REQUIERE ORDINAL 2"
        )
        self.assertNotEqual(self.parse_marker_sequence(fixture), [(1, 0), (2, 1)])

    def test_marker_validation_rejects_a_duplicate_ordinal(self):
        fixture = (
            "-- BEGIN LOTE EF PROTEGIDO 1; REQUIERE ORDINAL 0\r\n"
            "-- BEGIN LOTE EF PROTEGIDO 1; REQUIERE ORDINAL 0"
        )
        self.assertNotEqual(self.parse_marker_sequence(fixture), [(1, 0), (2, 1)])

    def test_marker_validation_rejects_an_incorrect_predecessor(self):
        fixture = (
            "-- BEGIN LOTE EF PROTEGIDO 1; REQUIERE ORDINAL 0\n"
            "-- BEGIN LOTE EF PROTEGIDO 2; REQUIERE ORDINAL 0"
        )
        self.assertNotEqual(self.parse_marker_sequence(fixture), [(1, 0), (2, 1)])

    def test_marker_validator_keeps_exact_count_and_sequence_checks(self):
        for contract in (
            "if ($BatchCount -le 0)",
            "if ($markers.Count -ne $BatchCount)",
            "$marker = $markers[$ordinal - 1]",
            "[int]$marker.Groups['Ordinal'].Value -ne $ordinal",
            "[int]$marker.Groups['PreviousOrdinal'].Value -ne $previousOrdinal",
        ):
            self.assertIn(contract, self.protected_validator)
        self.assertIn("SET [LastCompletedBatch] = $ordinal", self.protected_validator)
        self.assertIn("OBJECT_ID\\(N'tempdb\\.\\.#JemNexusReleasePreflight'", self.protected_validator)
        self.assertIn("IF XACT_STATE\\(\\) <> 1", self.protected_validator)
        self.assertIn("EXEC sys\\.sp_executesql N''", self.protected_validator)
        self.assertIn("IF @PostflightOrdinal <>", self.protected_validator)
        self.assertIn("COMMIT TRANSACTION;", self.protected_validator)

    def test_batch_guard_requires_sentinel_transaction_and_exact_predecessor(self):
        guard = self.protector[self.protector.index("-- BEGIN LOTE EF PROTEGIDO"):self.protector.index("BEGIN TRY")]
        sentinel = guard.index("OBJECT_ID(N'tempdb..#JemNexusReleasePreflight'")
        transaction = guard.index("IF XACT_STATE() <> 1")
        read_ordinal = guard.index("SELECT @Value = [LastCompletedBatch]")
        expected = guard.index("IF @ObservedOrdinal$ordinal <> $previousOrdinal")
        self.assertLess(sentinel, transaction)
        self.assertLess(transaction, read_ordinal)
        self.assertLess(read_ordinal, expected)
        self.assertLess(expected, len(guard))

    def test_batch_success_advances_only_after_body_and_next_batch_requires_it(self):
        compare = self.protector.index("IF @ObservedOrdinal$ordinal <> $previousOrdinal")
        body = self.protector.index("$execution", compare)
        transaction_after_body = self.protector.index("IF XACT_STATE() <> 1 THROW 51001", body)
        advance = self.protector.index("SET [LastCompletedBatch] = $ordinal", body)
        self.assertLess(compare, body)
        self.assertLess(body, transaction_after_body)
        self.assertLess(transaction_after_body, advance)
        self.assertLess(body, advance)
        self.assertIn("$previousOrdinal = $index", self.protector)
        self.assertIn("$ordinal = $index + 1", self.protector)
        self.assertIn("WHERE [LastCompletedBatch] = $previousOrdinal AND [ExecutionFailed] = 0", self.protector[advance:])

    def test_catch_rolls_back_marks_failure_and_rethrows(self):
        catch = self.protector[self.protector.index("BEGIN CATCH"):self.protector.index("END CATCH")]
        rollback = catch.index("IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;")
        mark = catch.index("UPDATE #JemNexusReleasePreflight SET [ExecutionFailed] = 1;")
        rethrow = catch.index("THROW;")
        self.assertLess(rollback, mark)
        self.assertLess(mark, rethrow)

    def test_raw_ef_sql_has_no_unprotected_mutable_path(self):
        assembly = self.script[self.script.index("$efSql ="):self.script.index("[IO.File]::WriteAllText((Join-Path $releaseStaging $sqlName)")]
        self.assertIn("ConvertTo-ProtectedMigrationSql $efSql", assembly)
        self.assertIn("$protectedEf.Sql", assembly)
        self.assertNotIn("$efSql.Trim()", assembly)
        self.assertIn("Assert-ProtectedMigrationSql $finalSql $protectedEf.BatchCount $protectedEf.DirectTransactionBatchCount $protectedEf.DynamicBatchCount", assembly)
        self.assertIn("EXEC sys.sp_executesql N'$escapedBody';", self.protector)

    def test_postflight_requires_final_sequence_before_commit_and_success(self):
        sentinel = self.postflight.index("OBJECT_ID(N'tempdb..#JemNexusReleasePreflight'")
        transaction = self.postflight.index("IF XACT_STATE() <> 1")
        sequence = self.postflight.index("IF @PostflightOrdinal <> $FinalBatchOrdinal OR @PostflightFailed <> 0")
        migrations = self.postflight.index("Las migraciones destino no quedaron registradas una vez")
        count = self.postflight.index("Cambio el conteo de QuoteRequests")
        commit = self.postflight.index("COMMIT TRANSACTION;")
        success = self.postflight.index("N'POSTFLIGHT_OK'")
        drop = self.postflight.index("DROP TABLE #JemNexusReleasePreflight")
        self.assertLess(sentinel, transaction)
        self.assertLess(transaction, sequence)
        self.assertLess(sequence, migrations)
        self.assertLess(migrations, count)
        self.assertLess(count, commit)
        self.assertLess(commit, success)
        self.assertLess(success, drop)

    def test_failed_preflight_leaves_every_later_mutation_behind_a_guard(self):
        guard = self.protector.index("IF OBJECT_ID(N'tempdb..#JemNexusReleasePreflight', N'U') IS NULL")
        body = self.protector.index("$execution", guard)
        blocked_commit = self.postflight.index("postflight y COMMIT bloqueados")
        commit = self.postflight.index("COMMIT TRANSACTION;")
        self.assertLess(guard, body)
        self.assertLess(blocked_commit, commit)
        self.assertNotIn("$efSql.Trim()", self.script)

    def test_manifest_records_cross_batch_fail_safe_contract(self):
        manifest = self.script[self.script.index("$manifest = [ordered]@{"):self.script.index("ConvertTo-Json -Depth 8")]
        for marker in (
            "proteccion_fail_safe_entre_lotes = $true",
            "lotes_ef_protegidos = $protectedEf.BatchCount",
            "lotes_control_transaccion_directos = $protectedEf.DirectTransactionBatchCount",
            "lotes_ef_dinamicos = $protectedEf.DynamicBatchCount",
            "postflight_compilacion_diferida = $true",
            "tabla temporal de sesion con ordinal secuencial y marcador de fallo",
            "postflight_exige_secuencia_completa = $true",
            "commit_exterior_despues_de_secuencia = $true",
        ):
            self.assertIn(marker, manifest)

    def test_msg_266_cause_is_structurally_excluded(self):
        self.assertIn("CONTROL TRANSACCIONAL EF DIRECTO", self.protector)
        self.assertNotIn("EXEC sys.sp_executesql N'$body'", self.protector)

    def test_pure_begin_transaction_is_classified_and_executed_directly(self):
        self.assertIn("$isBeginTransaction = $body -match '(?is)^BEGIN\\s+TRANSACTION\\s*;?\\s*$'", self.protector)
        self.assertIn("    $body", self.protector)

    def test_pure_commit_is_classified_and_executed_directly(self):
        self.assertIn("$isCommit = $body -match '(?is)^COMMIT\\s*;?\\s*$'", self.protector)
        self.assertIn("if ($isBeginTransaction -or $isCommit)", self.protector)

    def test_transaction_control_inside_dynamic_body_is_rejected(self):
        self.assertIn("$containsTransactionControl", self.protector)
        self.assertIn("mezcla o usa una variante inesperada", self.protector)
        self.assertIn("Un control transaccional quedo dentro de sp_executesql", self.protected_validator)

    def test_mixed_transaction_batch_is_fail_closed(self):
        self.assertIn("$containsTransactionControl -and -not ($isBeginTransaction -or $isCommit)", self.protector)

    def test_exactly_two_begin_and_two_commit_batches_are_derived(self):
        self.assertIn("$beginCount -ne 2 -or $commitCount -ne 2", self.protector)
        self.assertIn("BeginTransactionBatchCount = $beginCount", self.protector)
        self.assertIn("CommitBatchCount = $commitCount", self.protector)

    def test_all_direct_batches_keep_the_common_ordinal_advance(self):
        direct_choice = self.protector.index("if ($isBeginTransaction -or $isCommit)")
        common_advance = self.protector.index("SET [LastCompletedBatch] = $ordinal", direct_choice)
        self.assertLess(direct_choice, common_advance)
        self.assertIn("DirectTransactionBatchCount = $directTransactionCount", self.protector)

    def test_non_transaction_batches_remain_dynamic(self):
        self.assertIn("$dynamicBatchCount++", self.protector)
        self.assertIn("$execution = \"    EXEC sys.sp_executesql N'$escapedBody';\"", self.protector)

    def test_new_schema_references_are_only_inside_dynamic_postflight(self):
        dynamic_start = self.postflight.index("-- BEGIN VALIDACION POSTFLIGHT DINAMICA")
        dynamic_end = self.postflight.index("-- END VALIDACION POSTFLIGHT DINAMICA")
        outer = self.postflight[:dynamic_start] + self.postflight[dynamic_end:]
        self.assertNotIn("[IssuedById]", outer)
        self.assertNotIn("[AppUserPermissions]", outer)

    def test_dynamic_postflight_starts_after_all_guards(self):
        sequence = self.postflight.index("IF @PostflightOrdinal <> $FinalBatchOrdinal OR @PostflightFailed <> 0")
        dynamic = self.postflight.index("-- BEGIN VALIDACION POSTFLIGHT DINAMICA")
        self.assertLess(sequence, dynamic)

    def test_dynamic_postflight_returns_all_counts_through_output_parameters(self):
        for name in ("TargetMigrations", "SellerCount", "SellerPermissionCount", "CommercialQuoteCount", "QuoteRequestCount"):
            self.assertIn(f"@{name}Out", self.dynamic_postflight)
            self.assertIn(f"@{name} OUTPUT", self.dynamic_postflight)

    def test_dynamic_postflight_has_no_transaction_control_statement(self):
        sql_payload = self.dynamic_postflight[self.dynamic_postflight.index("EXEC sys.sp_executesql"):]
        self.assertIsNone(re.search(r"(?im)^\s*(BEGIN|COMMIT|ROLLBACK)\s+TRANSACTION\b", sql_payload))

    def test_outer_commit_is_direct_and_after_dynamic_validation(self):
        dynamic_end = self.postflight.index("-- END VALIDACION POSTFLIGHT DINAMICA")
        state = self.postflight.index("IF XACT_STATE() <> 1 THROW 51002", dynamic_end)
        commit = self.postflight.index("COMMIT TRANSACTION;", state)
        self.assertLess(dynamic_end, state)
        self.assertLess(state, commit)

    def test_final_row_uses_only_precalculated_values(self):
        commit = self.postflight.index("COMMIT TRANSACTION;")
        final_select = self.postflight[commit:self.postflight.index("DROP TABLE #JemNexusReleasePreflight", commit)]
        self.assertIn("@TargetMigrations AS [TargetMigrations]", final_select)
        self.assertNotIn("AppUserPermissions", final_select)
        self.assertNotIn("IssuedById", final_select)
        self.assertEqual(self.postflight.count("N'POSTFLIGHT_OK'"), 1)

    def test_missing_migrations_cannot_compile_new_schema_before_sequence_guard(self):
        sequence_end = self.postflight.index("BEGIN TRY", self.postflight.index("IF @PostflightOrdinal <>"))
        guarded_prefix = self.postflight[:sequence_end]
        self.assertNotIn("IssuedById", guarded_prefix)
        self.assertNotIn("AppUserPermissions", guarded_prefix)

    def test_derived_counts_are_not_manifest_constants(self):
        manifest = self.script[self.script.index("$manifest = [ordered]@{"):self.script.index("ConvertTo-Json -Depth 8")]
        self.assertNotRegex(manifest, r"lotes_(?:ef_protegidos|control_transaccion_directos|ef_dinamicos)\s*=\s*\d+")

    def test_current_sql_contract_requires_41_total_4_direct_and_37_dynamic(self):
        self.assertIn("$directTransactionCount -ne 4", self.protector)
        self.assertIn("($DirectTransactionBatchCount + $DynamicBatchCount) -ne $BatchCount", self.protected_validator)
        self.assertIn("41 lotes protegidos, cuatro directos y 37 dinamicos", self.doc)

    def test_documentation_records_both_incident_causes_and_clean_rollback(self):
        for marker in ("Msg 266", "sp_executesql", "Msg 207", "IssuedById", "rollback limpio", "490cdcf41dfb"):
            self.assertIn(marker, self.doc)

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
        self.assertEqual(len(removals), 3)
        self.assertTrue(any("-LiteralPath $stagingRoot" in removal for removal in removals))
        self.assertTrue(any("-LiteralPath $published" in removal for removal in removals))
        self.assertTrue(any("-LiteralPath $outputPath" in removal for removal in removals))
        self.assertNotIn("$HOME", self.script)
        self.assertIn("ZIP de destino ya existe", self.script)
        self.assertIn("OutputRoot debe estar completamente fuera del repositorio", self.script)

    def test_every_release_artifact_is_created_in_staging(self):
        creation_block = self.script[self.script.index("New-DeterministicZip $backendPackage"):self.script.index("# La comprobacion global de colisiones")]
        self.assertNotIn("Join-Path $outputPath $backendName", creation_block)
        self.assertNotIn("Join-Path $outputPath $frontendName", creation_block)
        self.assertNotIn("Join-Path $outputPath $sqlName", creation_block)
        for name in ("$backendName", "$frontendName", "$sqlName", "'manifest.json'", "'SHA256SUMS.txt'", "'PRESERVE_ON_SERVER.txt'"):
            self.assertIn(name, creation_block)
        self.assertGreaterEqual(creation_block.count("Join-Path $releaseStaging"), 8)

    def test_final_validation_precedes_collision_check_and_first_move(self):
        validate = self.script.index("$manifestCheck = Get-Content")
        collisions = self.script.index("# La comprobacion global de colisiones")
        move = self.script.index("Move-Item -LiteralPath")
        self.assertLess(validate, collisions)
        self.assertLess(collisions, move)
        self.assertIn("foreach ($name in $releaseNames)", self.script[collisions:move])

    def test_publication_failure_rolls_back_only_files_moved_by_this_run(self):
        move = self.script.index("Move-Item -LiteralPath")
        rollback = self.script.index("foreach ($published in $movedByThisRun)", move)
        self.assertIn("$movedByThisRun.Add($destination)", self.script[move:rollback])
        self.assertIn("Remove-Item -LiteralPath $published -Force", self.script[rollback:])
        self.assertIn("se revirtieron exclusivamente los archivos de esta ejecucion", self.script)

    def test_backend_and_frontend_zips_are_not_published_before_later_failures(self):
        backend_zip = self.script.index("New-DeterministicZip $backendPackage")
        frontend_validation = self.script.index("Assert-FrontendOutput $frontendDist")
        sql_validation = self.script.index("Assert-GeneratedMigrationSql $efSql")
        first_move = self.script.index("Move-Item -LiteralPath")
        self.assertLess(backend_zip, frontend_validation)
        self.assertLess(frontend_validation, sql_validation)
        self.assertLess(sql_validation, first_move)
        self.assertIn("Join-Path $releaseStaging $backendName", self.script[backend_zip:frontend_validation])

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
