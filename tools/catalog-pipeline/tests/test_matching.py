"""Offline matching specifications. These tests intentionally use synthetic local data."""
import ast,json,pathlib,sys,tempfile,unittest
from hashlib import sha256
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.identity import canonical_identity,source_identity
from catalog_acquisition.matching import (canonical_component,comparison_key,compare_manifests,
 MatchingBlockedError,MatchingInputError,_load_decisions,_load_rules,resolve,validate_domain,OUTPUTS)
from catalog_acquisition.serialization import canonical_bytes

class CanonizationTests(unittest.TestCase):
 def test_source_identity_ignores_mutable_observation(self):
  self.assertEqual(source_identity('ep','stable',key_strategy='native-v1').value,source_identity('ep','stable',key_strategy='native-v1').value)
  self.assertNotEqual(source_identity('ep','stable',key_strategy='native-v1').value,source_identity('gam','stable',key_strategy='native-v1').value)
 def test_canonical_is_source_independent_and_variants_exact(self):
  self.assertEqual(canonical_identity('EP Equipment','MODEL 10').value,canonical_identity('EP Equipment','MODEL 10').value)
  values={canonical_identity('EP Equipment','MODEL 10',x).value for x in (None,'S','+','Li','24V','II','PRO')}
  self.assertEqual(7,len(values))
 def test_raw_canonical_and_comparison_are_separate(self):
  raw='  Model‐  10  '; self.assertEqual('Model‐  10',canonical_component(raw))
  key=comparison_key(raw); self.assertNotEqual(raw,key['value']); self.assertTrue(key['changed']); self.assertIn('rule_version',key)
 def test_controls_and_empty_are_rejected(self):
  for value in ('  ','bad\x00value'):
   with self.assertRaises(MatchingInputError): canonical_component(value)

class RegistryTests(unittest.TestCase):
 def test_alias_cycle_and_collision_are_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d)/'rules.json'
   base=json.loads((ROOT/'fixtures/matching/rules-valid.json').read_text()); base['rules_version']='x'
   for aliases in ([{'source_namespace':'s','alias':'a','canonical_identity_value':'b'},{'source_namespace':'s','alias':'b','canonical_identity_value':'a'}],
    [{'source_namespace':'s','alias':'A','canonical_identity_value':'x'},{'source_namespace':'s','alias':'a','canonical_identity_value':'y'}]):
    base['aliases']=aliases; path.write_text(json.dumps(base))
    with self.assertRaises(MatchingBlockedError): _load_rules(path)
 def test_manual_decision_requires_auditable_id(self):
  with self.assertRaises(MatchingInputError): _load_decisions(ROOT/'fixtures/matching/decision-invalid-missing-id.json')
  self.assertIn('synthetic-source-1',_load_decisions(ROOT/'fixtures/matching/decision-valid.json'))

class IncrementalTests(unittest.TestCase):
 def manifest(self,mappings,fingerprint='f'):
  return {'schema_version':'1.0.0','engine_version':'catalog-identity-v1','rules_version':'r','semantic_fingerprint':fingerprint,'source_mappings':mappings}
 def test_new_preserved_remap_and_not_observed(self):
  result=compare_manifests(self.manifest({'a':'one','gone':'x'}),self.manifest({'a':'one','new':'two'}))
  classes={x['classification'] for x in result['changes']}
  self.assertEqual({'preserved_resolution','new_source_identity','not_observed_in_latest'},classes)
 def test_silent_remap_blocks(self):
  result=compare_manifests(self.manifest({'a':'one'}),self.manifest({'a':'two'}))
  self.assertEqual('blocked',result['status']); self.assertEqual('remapping_conflict',result['changes'][0]['classification'])
 def test_incompatible_versions_block_comparison(self):
  new=self.manifest({}); new['rules_version']='other'
  self.assertEqual('comparison_blocked',compare_manifests(self.manifest({}),new)['status'])
 def test_supplemental_association_disappearance_or_remap_blocks(self):
  old=self.manifest({'gam':None}); old['supplemental_entry_mappings']={'gam':'entry-a'}
  for replacement in ({'gam':'entry-b'},{}):
   new=self.manifest({'gam':None}); new['supplemental_entry_mappings']=replacement
   self.assertEqual('blocked',compare_manifests(old,new)['status'])

class SupplementalAssociationTests(unittest.TestCase):
 def candidate(self,source,role,key,model,*,warnings=()):
  return {'source':source,'source_role':role,'source_identity':f'{source}:url-v1:sha256:{key}',
   'source_key':f'url-v1:sha256:{key}','source_url':f'/{key}','canonical_url':f'https://example.invalid/{key}',
   'label_raw':model,'label_hint':model,'model_hint':model,'source_categories':[],
   'discovery_page':'https://example.invalid/list','evidence_reference':f'evidence/{key}',
   'locator':f'item-{key}','rule_version':'synthetic-v1','warnings':list(warnings),'review_status':'pending'}
 def run_case(self,rows):
  directory=tempfile.TemporaryDirectory(); root=pathlib.Path(directory.name)
  body=b''.join(canonical_bytes(x) for x in rows); (root/'product-candidates.jsonl').write_bytes(body)
  sources=sorted({x['source'] for x in rows}); manifest={'schema_version':'discovery-manifest-v1',
   'sources':sources,'adapters':{x:'synthetic-v1' for x in sources},'states':{x:'complete' for x in sources},
   'counts':{'candidates':len(rows)}}
  manifest['content_fingerprint']=sha256(canonical_bytes(manifest)).hexdigest()
  path=root/'discovery-manifest.json'; path.write_bytes(canonical_bytes(manifest)); output=root/'out'
  result=resolve(path,output)
  def read(name): return [json.loads(x) for x in (output/name).read_text().splitlines()]
  return directory,result,{name:read(name) for name in OUTPUTS}
 def test_exact_gam_associates_to_unresolved_ep_without_resolving_it(self):
  ep=self.candidate('ep','authoritative_existence','ep-a','SERIES 10',warnings=('series_page',))
  gam=self.candidate('gam','supplemental','gam-a','SERIES 10')
  hold,result,rows=self.run_case([gam,ep]); association=rows['supplemental-associations.jsonl'][0]
  supplemental_link=next(x for x in rows['identity-links.jsonl'] if x['source_namespace']=='gam')
  self.assertEqual('confirmed',association['association_status'])
  self.assertEqual('unresolved',association['canonical_resolution_status']); self.assertIsNone(supplemental_link['canonical_identity_value'])
  self.assertEqual(1,result['universes']['discovered_universe']); self.assertEqual(2,result['universes']['source_identity_universe'])
  self.assertEqual({'evidence/ep-a','evidence/gam-a'},set(association['evidence_ids'])); hold.cleanup()
 def test_normalized_match_is_review_not_orphan(self):
  ep=self.candidate('ep','authoritative_existence','ep-a','MODEL-10',warnings=('manual',))
  gam=self.candidate('gam','supplemental','gam-a','model‐10')
  hold,result,rows=self.run_case([ep,gam]); link=next(x for x in rows['identity-links.jsonl'] if x['source_namespace']=='gam')
  self.assertEqual('normalized_candidate',link['resolution_status']); self.assertIsNone(link['canonical_identity_value'])
  self.assertEqual('proposed_for_review',rows['supplemental-associations.jsonl'][0]['association_status']); hold.cleanup()
 def test_multiple_authoritative_entries_are_ambiguous_and_orphan_is_only_none(self):
  ep1=self.candidate('ep','authoritative_existence','ep-a','MODEL 10'); ep2=self.candidate('ep','authoritative_existence','ep-b','MODEL 10')
  gam=self.candidate('gam','supplemental','gam-a','MODEL 10')
  hold,result,rows=self.run_case([ep1,ep2,gam]); association=rows['supplemental-associations.jsonl'][0]
  self.assertEqual('ambiguous',association['association_status']); self.assertEqual(2,len(association['candidate_discovered_entry_ids'])); self.assertIsNone(association['discovered_entry_id']); hold.cleanup()
  orphan=self.candidate('gam','supplemental','gam-b','UNRELATED')
  hold,result,rows=self.run_case([ep1,orphan]); link=next(x for x in rows['identity-links.jsonl'] if x['source_namespace']=='gam')
  self.assertEqual('supplemental_orphan',link['resolution_status']); self.assertEqual([],rows['supplemental-associations.jsonl'][0]['candidate_discovered_entry_ids']); self.assertEqual(1,result['universes']['discovered_universe']); hold.cleanup()
 def test_repeated_resolution_has_identical_semantic_outputs(self):
  candidates=[self.candidate('ep','authoritative_existence','ep-a','MODEL 10'),self.candidate('gam','supplemental','gam-a','MODEL 10')]
  hold_a,result_a,rows_a=self.run_case(candidates); hold_b,result_b,rows_b=self.run_case(candidates)
  self.assertEqual(result_a['semantic_fingerprint'],result_b['semantic_fingerprint']); self.assertEqual(rows_a,rows_b)
  hold_a.cleanup(); hold_b.cleanup()

class ArchitectureTests(unittest.TestCase):
 def test_matching_and_cli_have_no_network_imports_or_fuzzy_algorithm(self):
  prohibited={'urllib.request','http.client','requests','socket','selenium','playwright','Levenshtein'}
  for path in (ROOT/'catalog_acquisition/matching.py',ROOT/'catalog_identity.py'):
   source=path.read_text(); tree=ast.parse(source)
   imports={x.name for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for x in n.names}
   self.assertFalse(prohibited & imports); self.assertNotIn('confidence',source.casefold())
 def test_supplemental_cannot_enter_discovered_universe_contract(self):
  schema=json.loads((ROOT/'schemas/v1/discovered-product-entry.schema.json').read_text())
  self.assertEqual('authoritative_existence',schema['properties']['source_role']['const'])
 def test_synthetic_fixture_inventory_has_all_required_cases(self):
  scenarios=json.loads((ROOT/'fixtures/matching/scenarios.json').read_text())['scenarios']
  self.assertEqual(18,len(scenarios))

if __name__=='__main__': unittest.main()
