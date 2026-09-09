"""Offline-only discovery specifications. Intentionally no network calls."""
import contextlib,io,json,pathlib,sys,tempfile,unittest
from dataclasses import replace
from email.message import Message
from types import SimpleNamespace
from unittest.mock import patch
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.discovery import SOURCES,candidate_record
from catalog_acquisition.discovery_adapters import ADAPTERS,StructureChanged
from catalog_acquisition.http_transport import HttpPolicy,SafeHttpTransport,ResponseTooLarge,ContentTypeBlocked,_retry_after,sanitize_url
from catalog_acquisition.orchestrator import (Frontier,FrontierItem,capture_source,compare,
 config_fingerprint,structure_gate,validate_resume,validate_resume_preflight)
from catalog_acquisition.robots import RobotsDecision,evaluate,permits_catalog
from catalog_acquisition.urls import UnsafeUrlError,canonicalize,validate_redirect

class UrlTests(unittest.TestCase):
 def test_relative_fragment_tracking_and_significant_query(self):
  u=canonicalize('?page=2&utm_source=x#top',base_url=SOURCES['gam'].start_url,source=SOURCES['gam'])
  self.assertEqual('https://online.gamrentals.com/cl/826-ep?page=2',u.canonical)
 def test_unsafe_matrix(self):
  for value in ['http://ep-equipment.com/es/productos/','https://evil.example/es/productos/',
   'https://127.0.0.1/es/productos/','https://localhost/es/productos/',
   'https://u:p@ep-equipment.com/es/productos/','https://ep-equipment.com:444/es/productos/',
   '//ep-equipment.com/es/productos/',r'\\server\share','https://ｅｐ-equipment.com/es/productos/']:
   with self.subTest(value=value),self.assertRaises(UnsafeUrlError): canonicalize(value,base_url=SOURCES['ep'].start_url,source=SOURCES['ep'])
 def test_redirect_allowed_external_and_downgrade(self):
  self.assertEqual('www.ep-equipment.com',validate_redirect('https://www.ep-equipment.com/es/productos/',SOURCES['ep'].start_url,SOURCES['ep']).canonical.split('/')[2])
  for x in ['https://evil.example/x','http://ep-equipment.com/es/productos/']:
   with self.assertRaises(UnsafeUrlError): validate_redirect(x,SOURCES['ep'].start_url,SOURCES['ep'])

class RobotsTests(unittest.TestCase):
 def d(self,status=200,body=b'User-agent: *\nDisallow: /private\nSitemap: https://ep-equipment.com/es/productos/sitemap.xml'):
  # Injected status/body: no robots parser may perform I/O.
  return evaluate(robots_url='https://ep-equipment.com/robots.txt',status=status,body=body,target_url=SOURCES['ep'].start_url,user_agent='agent',fetched_at='2026-01-01T00:00:00Z')
 def test_not_found_allows(self):
  for status in (404,410): self.assertEqual('not_found',self.d(status,b'').state)
 def test_fetch_fail_blocks(self): self.assertFalse(evaluate(robots_url='x',status=None,body=None,target_url='x',user_agent='a',fetched_at='x',fetch_error='timeout').allowed)
 def test_unknown_or_forged_not_found_never_opens_gate(self):
  unknown=self.d(418,b''); forged=RobotsDecision('x','not_found',200,None,'x','a',None,True)
  self.assertFalse(permits_catalog(unknown)); self.assertFalse(permits_catalog(forged))

class ParseTests(unittest.TestCase):
 def test_ep_categories_candidates_pagination_jsonld_entities_unicode_external_unknown(self):
  p=ADAPTERS['ep'].parse((ROOT/'fixtures/discovery-structural/ep.html').read_bytes(),base_url=SOURCES['ep'].start_url,content_type='text/html',encoding='utf-8',snapshot_reference='snap/ep')
  self.assertEqual({'category','product_candidate','pagination','blocked','unknown'},{x.kind for x in p.links}); self.assertEqual('EFL 181',next(x for x in p.links if x.kind=='product_candidate').model_hint); self.assertTrue(p.json_ld); self.assertIn('&',p.categories[0]['name_visible'])
 def test_gam_is_supplemental_and_never_official(self):
  p=ADAPTERS['gam'].parse((ROOT/'fixtures/discovery-structural/gam.html').read_bytes(),base_url=SOURCES['gam'].start_url,content_type='text/html',encoding='utf-8',snapshot_reference='snap/gam',expected_products=True)
  record=candidate_record(SOURCES['gam'],next(x for x in p.links if x.kind=='product_candidate')); self.assertEqual('supplemental',record['source_role']); self.assertEqual('pending',record['review_status'])
 def test_empty_and_changed_fail_closed_when_products_expected(self):
  for name in ('empty.html','changed.html'):
   with self.assertRaises(StructureChanged): ADAPTERS['ep'].parse((ROOT/'fixtures/discovery-structural'/name).read_bytes(),base_url=SOURCES['ep'].start_url,content_type='text/html',encoding='utf-8',snapshot_reference='x',expected_products=True)

class FrontierAndDeterminismTests(unittest.TestCase):
 def test_order_duplicate_cycle_and_hash_duplicate(self):
  f=Frontier(); self.assertTrue(f.add(FrontierItem('https://x/b'))); self.assertTrue(f.add(FrontierItem('https://x/a'))); self.assertFalse(f.add(FrontierItem('https://x/a'))); self.assertEqual('https://x/a',f.next().canonical_url); self.assertIsNone(f.mark_hash('a','h')); self.assertEqual('a',f.mark_hash('b','h'))
 def test_fingerprint_excludes_nothing_not_explicitly_semantic(self):
  a={'schema_version':'x','v':1}; self.assertEqual(config_fingerprint(a),config_fingerprint(dict(a))); self.assertNotEqual(config_fingerprint(a),config_fingerprint(a|{'v':2}))
 def test_resume_mismatch_aborts(self):
  with self.assertRaises(ValueError): validate_resume({'config_fingerprint':'bad'},{'schema_version':'x'})
 def test_comparison_absence_blocked_when_incomplete(self):
  self.assertEqual('comparison_blocked',compare({'states':{'ep':'complete'}},{'states':{'ep':'partial'}},'old','new')['status'])
 def test_comparison_classes_without_deletion(self):
  base={'states':{'ep':'complete'},'adapters':{'ep':'v'},'product_candidates':[]}; result=compare(base,base,'a','b'); self.assertEqual([],result['differences'])

class TransportUnitTests(unittest.TestCase):
 def test_retry_after_bounded_and_log_sanitized(self):
  h=Message(); h['Retry-After']='999'; self.assertEqual(30,_retry_after(h,30)); self.assertNotIn('secret',sanitize_url('https://ep-equipment.com/es/productos/?token=secret'))
 def test_methods_restricted_before_network(self):
  with self.assertRaises(Exception): SafeHttpTransport().fetch(SOURCES['ep'].start_url,SOURCES['ep'],method='POST')
 def test_policy_limits(self):
  p=HttpPolicy(); self.assertEqual((20.0,1.0,2,5,5*1024*1024),(p.timeout,p.min_host_pause,p.retries,p.max_redirects,p.max_body))

class _FakeTransport:
 policy=HttpPolicy(user_agent='offline-test-agent')
 def __init__(self,robots_status=200,robots_body=b'User-agent: *\nAllow: /',error=None,page=None):
  self.calls=[]; self.status=robots_status; self.body=robots_body; self.error=error
  self.page=page or (ROOT/'fixtures/discovery-structural/empty.html').read_bytes()
 def fetch(self,url,source,method='GET'):
  self.calls.append((method,url))
  if len(self.calls)==1:
   if self.error: raise self.error
   return SimpleNamespace(status=self.status,body=self.body,fetched_at='2026-01-01T00:00:00Z',
    final_url=url,content_type='text/plain',encoding='utf-8')
  return SimpleNamespace(status=200,body=self.page,fetched_at='2026-01-01T00:00:01Z',
   final_url=url,content_type='text/html',encoding='utf-8')

class LivePreflightRegressionTests(unittest.TestCase):
 def enabled(self,key='ep'):
  source=SOURCES[key]; return replace(source,structure_verified=True,
   structure_evidence_reference='audit/approved-structure.json',
   structure_evidence_rule_version=ADAPTERS[key].adapter_version,
   structure_evidence_sha256='a'*64)
 def capture(self,source,transport,**kw):
  return capture_source(source,ADAPTERS[source.source],transport,
   config_fingerprint_value='config-fingerprint',max_pages=kw.get('max_pages',1),max_depth=1)
 def test_unverified_structure_blocks_before_transport(self):
  for key in ('ep','gam'):
   with self.subTest(source=key):
    transport=_FakeTransport(); result=self.capture(SOURCES[key],transport)
    self.assertEqual([],transport.calls); self.assertEqual('blocked',result.state)
    self.assertEqual('source_structure_unverified',result.reason); self.assertEqual(0,result.snapshots_persisted)
 def test_boolean_without_compatible_evidence_is_not_authorization(self):
  cases=(replace(SOURCES['ep'],structure_verified=True),
   replace(SOURCES['ep'],structure_verified=True,structure_evidence_reference='audit/x',
    structure_evidence_rule_version='wrong',structure_evidence_sha256='a'*64),
   replace(SOURCES['ep'],structure_verified=True,structure_evidence_reference='audit/x',
    structure_evidence_rule_version=ADAPTERS['ep'].adapter_version,structure_evidence_sha256='unknown'))
  for source in cases:
   with self.subTest(reason=structure_gate(source,ADAPTERS['ep'])):
    transport=_FakeTransport(); result=self.capture(source,transport)
    self.assertEqual([],transport.calls); self.assertEqual('blocked',result.state)
    self.assertIn(result.reason,('source_structure_evidence_missing','source_structure_evidence_version_mismatch',
     'source_structure_evidence_hash_invalid'))
 def test_fetch_proxy_or_timeout_only_attempts_robots(self):
  for error in (OSError('proxy'),TimeoutError('timeout')):
   with self.subTest(error=type(error).__name__):
    transport=_FakeTransport(error=error); result=self.capture(self.enabled(),transport)
    self.assertEqual([('GET','https://ep-equipment.com/robots.txt')],transport.calls)
    self.assertEqual('robots_fetch_failed',result.reason)
 def test_non_authorizing_robots_never_reaches_catalog(self):
  cases=((401,b''),(403,b''),(418,b''),(500,b''),(200,b'\xff'),(200,b'User-agent: *\nDisallow: /'))
  for status,body in cases:
   with self.subTest(status=status,body=body):
    transport=_FakeTransport(status,body); result=self.capture(self.enabled(),transport)
    self.assertEqual(1,len(transport.calls)); self.assertEqual('blocked',result.state)
    self.assertEqual(1,result.urls_blocked)
 def test_404_410_and_explicit_allow_put_robots_first(self):
  for status,body in ((404,b''),(410,b''),(200,b'User-agent: *\nAllow: /')):
   with self.subTest(status=status):
    transport=_FakeTransport(status,body); result=self.capture(self.enabled(),transport)
    self.assertEqual('https://ep-equipment.com/robots.txt',transport.calls[0][1])
    self.assertEqual(SOURCES['ep'].start_url,transport.calls[1][1]); self.assertEqual(2,result.requests_attempted)
 def test_start_url_disallowed_is_never_requested(self):
  transport=_FakeTransport(200,b'User-agent: *\nDisallow: /es/productos/')
  result=self.capture(self.enabled(),transport)
  self.assertEqual(1,len(transport.calls)); self.assertEqual('robots_disallowed',result.reason)
 def test_discovered_url_and_sitemap_do_not_bypass_per_url_gate(self):
  body=b'User-agent: *\nAllow: /es/productos/\nDisallow: /es/productos/private/\nSitemap: https://ep-equipment.com/es/productos/private/map.xml'
  page=b'<a class="category" href="/es/productos/private/">Private</a>'
  transport=_FakeTransport(200,body,page=page); result=self.capture(self.enabled(),transport,max_pages=3)
  self.assertEqual(2,len(transport.calls)); self.assertGreaterEqual(result.urls_blocked,1)
 def test_resume_incompatible_evidence_blocks_before_caller_can_create_transport(self):
  cfg={'schema_version':'discovery-config-v1'}; previous={'config_fingerprint':config_fingerprint(cfg),'robots':{}}
  with self.assertRaises(ValueError): validate_resume_preflight(previous,cfg,{'ep':SOURCES['ep']},{'ep':ADAPTERS['ep']},'offline-test-agent')
 def test_resume_robot_binding_mismatch_blocks_before_network(self):
  cfg={'schema_version':'discovery-config-v1'}; enabled=self.enabled()
  prior={'config_fingerprint':config_fingerprint(cfg),'robots':{'ep':{'source':'gam',
   'user_agent':'offline-test-agent','config_fingerprint':config_fingerprint(cfg),'state':'allowed'}}}
  with self.assertRaises(ValueError): validate_resume_preflight(prior,cfg,{'ep':enabled},{'ep':ADAPTERS['ep']},'offline-test-agent')
 def test_direct_orchestrator_call_and_source_isolation(self):
  blocked_transport=_FakeTransport(); blocked=self.capture(SOURCES['ep'],blocked_transport)
  allowed_transport=_FakeTransport(404,b''); allowed=self.capture(self.enabled('gam'),allowed_transport)
  self.assertEqual([],blocked_transport.calls); self.assertEqual('blocked',blocked.state)
  self.assertEqual(2,len(allowed_transport.calls)); self.assertNotEqual('complete',allowed.state)
 def test_blocked_result_cannot_report_complete(self):
  result=self.capture(SOURCES['ep'],_FakeTransport())
  manifest={'states':{'ep':result.state},'source_results':{'ep':result.__dict__}}
  self.assertNotEqual('complete',manifest['states']['ep']); self.assertEqual(0,manifest['source_results']['ep']['requests_attempted'])
 def test_plan_constructs_no_transport_and_reports_both_blocked(self):
  import catalog_discovery
  with patch.object(catalog_discovery,'SafeHttpTransport',side_effect=AssertionError('network transport constructed')):
   output=io.StringIO()
   with contextlib.redirect_stdout(output): code=catalog_discovery.main(['plan','--source','all'])
  document=json.loads(output.getvalue()); self.assertEqual(0,code); self.assertEqual(0,document['network_requests'])
  self.assertEqual({'blocked'}, {x['state'] for x in document['source_preflight'].values()})

class ArchitectureTests(unittest.TestCase):
 def test_parsers_do_not_import_transport_and_importer_does_not_import_adapters(self):
  parser=(ROOT/'catalog_acquisition/discovery_adapters.py').read_text(); importer='\n'.join(x.read_text() for x in (ROOT/'jem_nexus_import').glob('*.py'))
  self.assertNotIn('http_transport',parser); self.assertNotIn('discovery_adapters',importer)
 def test_no_matching_or_media_fixture(self):
  files=list((ROOT/'fixtures/discovery-structural').iterdir()); self.assertFalse(any(x.suffix.lower() in ('.pdf','.jpg','.png','.webp') for x in files))
if __name__=='__main__': unittest.main()
