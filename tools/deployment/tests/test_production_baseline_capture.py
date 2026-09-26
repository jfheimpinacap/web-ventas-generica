import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location("baseline_policy",ROOT/"production_baseline_policy.py")
policy=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(policy)
SQL=(ROOT/"Capture-JemNexusProductionSchemaBaseline.sql").read_text(encoding="utf-8")
PS=(ROOT/"Capture-JemNexusProductionSchemaBaseline.ps1").read_text(encoding="utf-8")
PS_CREDENTIAL_TEST=(ROOT/"tests"/"Test-ProductionBaselineSqlCredential.WindowsPowerShell.ps1").read_text(encoding="utf-8")
MIGRATIONS=[f"migration-{n:02d}" for n in range(22)]


def observation():
    return {"complete":True,"database":"jemnexusb_prod","serverIdentityOk":True,
            "transactionCount":0,"migrationIds":MIGRATIONS.copy(),
            "schemaFingerprints":{kind:(kind[0]*64) for kind in policy.KINDS}}


class ProductionBaselineCaptureTests(unittest.TestCase):
    def test_stable_capture_and_exact_canonical_hash(self):
        one=observation();self.assertEqual(one["migrationIds"],policy.compare_observations(one,copy.deepcopy(one),MIGRATIONS)["migrationIds"])
        self.assertEqual(policy.canonical_hash([{"a":"x\r\ny","b":None}],("a","b")),
                         __import__('hashlib').sha256(b"x y|<NULL>").hexdigest())

    def test_change_between_passes_is_no_go(self):
        one=observation();two=copy.deepcopy(one);two["schemaFingerprints"]["indexes"]="f"*64
        with self.assertRaisesRegex(ValueError,"OBSERVATIONS_DIFFER_NO_GO"):policy.compare_observations(one,two,MIGRATIONS)

    def test_missing_or_additional_migration_is_rejected(self):
        for ids in (MIGRATIONS[:-1],MIGRATIONS+["extra"]):
            with self.subTest(count=len(ids)):
                one=observation();one["migrationIds"]=ids
                with self.assertRaisesRegex(ValueError,"MIGRATIONS_MISMATCH"):policy.compare_observations(one,observation(),MIGRATIONS)

    def test_wrong_identity_and_intermediate_error_are_rejected(self):
        for field,value,error in (("serverIdentityOk",False,"PRODUCTION_IDENTITY_MISMATCH"),("complete",False,"INCOMPLETE_OBSERVATION")):
            one=observation();one[field]=value
            with self.assertRaisesRegex(ValueError,error):policy.compare_observations(one,observation(),MIGRATIONS)

    def test_open_transaction_and_fingerprint_discord_are_rejected(self):
        one=observation();one["transactionCount"]=1
        with self.assertRaisesRegex(ValueError,"TRANSACTION_NOT_CLOSED"):policy.compare_observations(one,observation(),MIGRATIONS)
        one=observation();del one["schemaFingerprints"]["checks"]
        with self.assertRaisesRegex(ValueError,"FINGERPRINT_SET_INVALID"):policy.compare_observations(one,observation(),MIGRATIONS)

    def test_sql_is_read_only_off_compatible_and_client_is_atomic(self):
        self.assertIn("snapshot_isolation_state_desc=N'OFF'",SQL);self.assertIn("is_read_committed_snapshot_on=0",SQL)
        self.assertNotIn("BEGIN TRANSACTION",SQL.upper());self.assertNotIn("SERIALIZABLE",SQL.upper())
        for verb in ("ALTER DATABASE","CREATE TABLE","INSERT INTO","UPDATE ","DELETE ","MERGE "):
            self.assertNotIn(verb,SQL.upper())
        self.assertIn("$one=Observe;$two=Observe",PS)
        self.assertLess(PS.index("if($a-cne $b)"),PS.index("WriteAllText"))
        self.assertIn("OUTPUT_ALREADY_EXISTS",PS)
        self.assertIn("Move-Item -LiteralPath $temp",PS);self.assertIn("BASELINE_CAPTURE_VERIFIED_AND_SAVED",PS)
        self.assertIn("CommandTimeout=30",PS);self.assertIn("finally{$c.Dispose()}",PS)

    def test_sql_credential_is_prompted_and_never_enters_connection_string(self):
        self.assertIn("ValidateSet('SqlCredential','Integrated')",PS)
        self.assertIn("Get-Credential -Message",PS)
        self.assertIn("Data.SqlClient.SqlCredential",PS)
        self.assertIn("if(-not $Secret.IsReadOnly()){$Secret.MakeReadOnly()}",PS)
        self.assertIn("$c.Credential=$SqlCredential",PS)
        builder=PS[PS.index("$b=New-Object"):PS.index("$c=New-Object")]
        self.assertNotIn("$b.UserID=",builder);self.assertNotIn("$b.Password=",builder)
        self.assertNotIn("ConvertTo-SecureString",PS)
        self.assertNotIn("NetworkCredential",PS)

    def test_windows_powershell_constructor_fixture_never_opens_connection(self):
        self.assertIn("#requires -Version 5.1",PS_CREDENTIAL_TEST)
        self.assertIn("$secret.MakeReadOnly()",PS_CREDENTIAL_TEST)
        self.assertIn("Data.SqlClient.SqlCredential",PS_CREDENTIAL_TEST)
        self.assertIn("$builder.IntegratedSecurity=$false",PS_CREDENTIAL_TEST)
        self.assertIn("$connection.Credential=$credential",PS_CREDENTIAL_TEST)
        self.assertNotIn(".Open(",PS_CREDENTIAL_TEST)
        self.assertNotIn("Password=",PS_CREDENTIAL_TEST)
        self.assertIn("$connection.Dispose()",PS_CREDENTIAL_TEST)
        self.assertIn("$secret.Dispose()",PS_CREDENTIAL_TEST)

    def test_integrated_auth_is_explicit_and_has_no_fallback(self):
        self.assertIn("IntegratedSecurity=($Authentication-ceq 'Integrated')",PS)
        self.assertEqual(1,PS.count("Get-Credential"))
        self.assertNotIn("Authentication='Integrated'",PS)
        self.assertNotIn("Authentication = 'Integrated'",PS)

    def test_auth_tls_failures_are_sanitized_and_resources_are_closed(self):
        self.assertIn("TrustServerCertificate=$false",PS);self.assertIn("Encrypt=$true",PS)
        self.assertIn("AUTHENTICATION_OR_TLS_CONNECTION_FAILED",PS)
        self.assertNotIn("$_.Exception.ToString",PS)
        self.assertIn("'BASELINE_CAPTURE_FAILED'",PS)
        self.assertIn("Write-Error ('NO-GO: '+$diagnostic)",PS)
        self.assertIn("finally{$c.Dispose()}",PS)
        self.assertIn("finally {if($null-ne $Secret){$Secret.Dispose()",PS)
        self.assertEqual(1,PS.count("Write-Error"))

    def test_effective_database_principal_is_guarded_before_metadata(self):
        principal=SQL.index("USER_NAME()")
        metadata=SQL.index("EXEC sys.sp_executesql")
        self.assertLess(principal,metadata)
        self.assertIn("PRODUCTION_DATABASE_PRINCIPAL_MISMATCH",SQL)


if __name__=="__main__":unittest.main()
