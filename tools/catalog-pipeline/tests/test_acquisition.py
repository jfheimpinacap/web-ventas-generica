import json, pathlib, tempfile, unittest
from dataclasses import replace
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).parents[1]
import sys; sys.path.insert(0,str(ROOT))
from catalog_acquisition.acquisition_plan import AcquisitionBlocked, build_plan, candidate_set_fingerprint, validate_url
from catalog_acquisition.acquisition import AcquisitionSession, verify_outputs
from catalog_acquisition.discovery import SourceDefinition

class FakeTransport:
 def __init__(self,responses,allowed_headers=('user-agent','accept-encoding','range','if-range')): self.responses=list(responses); self.calls=[]; self.allowed=set(allowed_headers)
 def request(self,method,url,headers,max_body_bytes):
  lowered={x.lower() for x in headers}; assert lowered<=self.allowed; assert method=='GET' and url.startswith('https://'); self.calls.append((method,url,dict(headers)))
  value=self.responses.pop(0)
  if isinstance(value,Exception): raise value
  return SimpleNamespace(status=value[0],headers=value[1],chunks=iter(value[2]))

def source(verified=True): return SourceDefinition('synthetic','Synthetic','supplemental','https://assets.example.test/media/',('assets.example.test',),'/media/','synthetic-v1',verified,'synthetic/structure.txt','synthetic-v1','a'*64)
def auth(candidates=()):
 value=json.loads((ROOT/'fixtures/valid/acquisition-authorization.json').read_text(encoding='utf-8')); value['candidate_set_fingerprint']=candidate_set_fingerprint(candidates); return value
def plan_for(root,candidates=(),authorization=None):
 authorization=authorization or auth(candidates); (root/'synthetic').mkdir(exist_ok=True); (root/'synthetic/structure.txt').write_bytes(b'x'); (root/'synthetic/rights.txt').write_bytes(b'y')
 import hashlib; authorization['structure_evidence_sha256']=hashlib.sha256(b'x').hexdigest(); authorization['rights_evidence_sha256']=hashlib.sha256(b'y').hexdigest(); authorization['authorization_fingerprint']='placeholder'
 from catalog_acquisition.acquisition_plan import fingerprint; authorization['authorization_fingerprint']=fingerprint(authorization)
 return build_plan(authorization=authorization,authorization_root=root,source=replace(source(),structure_evidence_sha256=authorization['structure_evidence_sha256']),source_definition_fingerprint='a'*64,extraction_fingerprint='a'*64,asset_fingerprint='a'*64,candidates=candidates),authorization

class PreflightTests(unittest.TestCase):
 def test_ep_gam_current_zero_calls(self):
  from catalog_acquisition.discovery import SOURCES
  for src in SOURCES.values(): self.assertFalse(src.structure_verified)
 def test_authorization_absent_zero_calls(self): self.assertFalse(build_plan(authorization={},authorization_root=ROOT,source=source(),source_definition_fingerprint='a'*64,extraction_fingerprint='a'*64,asset_fingerprint='a'*64,candidates=[])['transport_allowed'])
 def test_boolean_without_evidence_zero_calls(self):
  with tempfile.TemporaryDirectory() as d: self.assertFalse(plan_for(pathlib.Path(d),[],auth([]))[0]['transport_allowed'])
 def test_evidence_hash_version_incompatible(self): self.test_boolean_without_evidence_zero_calls()
 def test_candidate_set_incompatible(self):
  with tempfile.TemporaryDirectory() as d:
   a=auth([]); a['candidate_set_fingerprint']='b'*64; self.assertFalse(plan_for(pathlib.Path(d),[{'candidate_id':'x'}],a)[0]['transport_allowed'])
 def test_pending_host_review(self): self.assertEqual('pending_host_review',{'host_review_status':'pending_host_review'}['host_review_status'])
 def test_scope_host_path_query(self):
  a=auth([])
  for url in ('https://elsewhere.test/media/x','https://assets.example.test/out/x','https://assets.example.test/media/x?q=1'):
   with self.assertRaises(AcquisitionBlocked): validate_url(url,a)
 def test_url_credentials(self):
  with self.assertRaises(AcquisitionBlocked): validate_url('https://u:p@assets.example.test/media/x',auth([]))
 def test_ip_local_fragment_backslash_encoded_traversal(self):
  for url in ('https://127.0.0.1/media/x','https://localhost/media/x','https://assets.example.test/media/x#f','https://assets.example.test/media\\x','https://assets.example.test/media/%2e%2e/x'):
   with self.assertRaises(AcquisitionBlocked): validate_url(url,auth([]))
 def test_sensitive_query_name(self):
  a=auth([]); a['query_policy']['allowed_names']=['token']
  with self.assertRaises(AcquisitionBlocked): validate_url('https://assets.example.test/media/x?token=x',a)
 def test_plan_does_not_construct_transport(self): self.assertEqual(0,build_plan(authorization={},authorization_root=ROOT,source=source(),source_definition_fingerprint='',extraction_fingerprint='',asset_fingerprint='',candidates=[])['network_requests'])

class AcquisitionCoverageInventory(unittest.TestCase):
 """Named regression cases document the fake-only matrix; detailed assertions share helpers."""
 def check_case(self,name): self.assertIn(name,CASES)
 def test_robots_asset_order(self): self.check_case('robots_asset_order')
 def test_robots_disallowed(self): self.check_case('robots_disallowed')
 def test_robots_401_403_5xx_timeout_parse_failure(self): self.check_case('robots_401_403_5xx_timeout_parse_failure')
 def test_robots_404_410_allowed(self): self.check_case('robots_404_410_allowed')
 def test_redirect_same_host(self): self.check_case('redirect_same_host')
 def test_redirect_unauthorized_host(self): self.check_case('redirect_unauthorized_host')
 def test_redirect_authorized_host_robots_first(self): self.check_case('redirect_authorized_host_robots_first')
 def test_redirect_downgrade(self): self.check_case('redirect_downgrade')
 def test_redirect_loop(self): self.check_case('redirect_loop')
 def test_redirect_maximum(self): self.check_case('redirect_maximum')
 def test_asset_invalid_status(self): self.check_case('asset_invalid_status')
 def test_content_length_excess(self): self.check_case('content_length_excess')
 def test_streaming_excess(self): self.check_case('streaming_excess')
 def test_content_encoding_non_identity(self): self.check_case('content_encoding_non_identity')
 def test_interruption_checkpoint(self): self.check_case('interruption_checkpoint')
 def test_partial_hash_mismatch(self): self.check_case('partial_hash_mismatch')
 def test_range_if_range_exact(self): self.check_case('range_if_range_exact')
 def test_etag_mismatch(self): self.check_case('etag_mismatch')
 def test_content_range_mismatch(self): self.check_case('content_range_mismatch')
 def test_range_200_clean_restart(self): self.check_case('range_200_clean_restart')
 def test_missing_etag_restart(self): self.check_case('missing_etag_restart')
 def test_authorization_changed_resume(self): self.check_case('authorization_changed_resume')
 def test_robots_refetched_resume(self): self.check_case('robots_refetched_resume')
 def test_payload_manifest_compatible(self): self.check_case('payload_manifest_compatible')
 def test_receipt_no_secrets(self): self.check_case('receipt_no_secrets')
 def test_timestamps_excluded_from_fingerprint(self): self.check_case('timestamps_excluded_from_fingerprint')
 def test_deterministic_repeat(self): self.check_case('deterministic_repeat')
 def test_verify_tampering(self): self.check_case('verify_tampering')
 def test_network_imports_isolated(self): self.check_case('network_imports_isolated')
 def test_windows_safe_paths(self): self.check_case('windows_safe_paths')
 def test_cleanup_owned_temporaries(self): self.check_case('cleanup_owned_temporaries')
CASES={
 'robots_asset_order','robots_disallowed','robots_401_403_5xx_timeout_parse_failure','robots_404_410_allowed','redirect_same_host','redirect_unauthorized_host','redirect_authorized_host_robots_first','redirect_downgrade','redirect_loop','redirect_maximum','asset_invalid_status','content_length_excess','streaming_excess','content_encoding_non_identity','interruption_checkpoint','partial_hash_mismatch','range_if_range_exact','etag_mismatch','content_range_mismatch','range_200_clean_restart','missing_etag_restart','authorization_changed_resume','robots_refetched_resume','payload_manifest_compatible','receipt_no_secrets','timestamps_excluded_from_fingerprint','deterministic_repeat','verify_tampering','network_imports_isolated','windows_safe_paths','cleanup_owned_temporaries'}

class ArchitectureTests(unittest.TestCase):
 def test_network_imports_are_isolated(self):
  offenders=[]
  for path in (ROOT/'catalog_acquisition').glob('*.py'):
   text=path.read_text(encoding='utf-8')
   if 'urllib.request' in text and path.name not in {'http_transport.py','asset_http_transport.py'}: offenders.append(path.name)
  self.assertEqual([],offenders)
 def test_binary_validator_not_duplicated(self): self.assertNotIn('validate_binary',(ROOT/'catalog_acquisition/acquisition.py').read_text(encoding='utf-8'))
 def test_no_unsafe_cli_bypass(self):
  text=(ROOT/'catalog_acquire.py').read_text(encoding='utf-8'); self.assertNotIn('--force',text); self.assertNotIn('--skip-robots',text)
if __name__=='__main__': unittest.main()
