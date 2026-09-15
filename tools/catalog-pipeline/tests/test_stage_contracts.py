"""Integral, offline coverage for the versioned catalog stage boundaries."""
import copy, hashlib, json, pathlib, re, sys, tempfile, unittest
from types import SimpleNamespace
from unittest import mock
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition import acquisition as acquisition_module
from catalog_acquisition.acquisition import AcquisitionSession, verify_outputs
from catalog_acquisition.acquisition_plan import AcquisitionBlocked
from catalog_acquisition.extraction import extract, validate_inputs, ExtractionInputError
from catalog_acquisition.extraction_adapters import FixtureHtmlExtractionAdapter
from catalog_acquisition.identity import canonical_identity
from catalog_acquisition.matching import resolve
from catalog_acquisition.normalization import build_plan, fingerprint, normalize_to, verify_output
from catalog_acquisition.paths import semantic_path_key, UnsafePathError
from catalog_acquisition.schema_validation import validate
from catalog_acquisition.serialization import canonical_bytes
from jem_nexus_import.normalized_adapter import adapt_normalized_product, NormalizedProjectionError, ADAPTER_VERSION
from jem_nexus_import.reconciliation import build_operations

SCHEMAS=ROOT/'schemas/v1'
def _digest(value): return hashlib.sha256(canonical_bytes(value)).hexdigest()
def _sign(value,field='semantic_fingerprint'):
 semantic=copy.deepcopy(value); semantic.pop(field,None); semantic.pop('generated_at',None); value[field]=_digest(semantic); return value

def _acquisition_contract(candidate_id='asset-a'):
 candidate={'candidate_id':candidate_id,'state':'allowed','reason':'authorized','url':'https://assets.example.test/media/a'}
 auth=json.loads((ROOT/'fixtures/valid/acquisition-authorization.json').read_text(encoding='utf-8'))
 auth.update(authorization_id='auth-1',fixture_only=True)
 return {'transport_allowed':True,'authorization_fingerprint':auth['authorization_fingerprint'],'items':[candidate]},auth

class _Transport:
 def __init__(self,responses): self.responses=list(responses); self.calls=[]
 def request(self,method,url,headers,max_body_bytes):
  self.calls.append((method,url,copy.deepcopy(headers),max_body_bytes)); status,response_headers,chunks=self.responses.pop(0)
  return SimpleNamespace(status=status,headers=response_headers,chunks=iter(chunks))

def _interrupted():
 yield b'abc'
 raise AcquisitionBlocked('stream_interrupted')

def _candidate(key,model):
 digest=hashlib.sha256(key.encode()).hexdigest(); source_key='url-v1:sha256:'+digest
 return {'source':'ep','source_role':'authoritative_existence','source_identity':'ep:'+source_key,'source_key':source_key,
  'source_url':'/'+key,'canonical_url':'https://example.test/'+key,'label_raw':model,'label_hint':model,'model_hint':model,
  'source_categories':['lifts'],'discovery_page':'https://example.test/catalog','evidence_reference':'evidence/'+key,
  'locator':'item-'+key,'rule_version':'synthetic-v1','warnings':[],'review_status':'pending'}

def _matching(root,rows):
 body=b''.join(canonical_bytes(x) for x in rows); (root/'product-candidates.jsonl').write_bytes(body)
 manifest={'schema_version':'discovery-manifest-v1','sources':['ep'],'adapters':{'ep':'synthetic-v1'},'states':{'ep':'complete'},'counts':{'candidates':len(rows)}}
 manifest['content_fingerprint']=_digest(manifest); path=root/'discovery-manifest.json'; path.write_bytes(canonical_bytes(manifest))
 output=root/'matching'; result=resolve(path,output); return result,output/'matching-manifest.json',copy.deepcopy(manifest),copy.deepcopy(rows)

def _snapshot(root,matching,reverse=False):
 snaproot=root/'snapshots'; snaproot.mkdir(); rows=[]
 for index,binding in enumerate(matching['identity_bindings']):
  model='MODEL-B' if binding['canonical_identity_value']==canonical_identity('EP Equipment','MODEL-B').value else 'MODEL-A'
  body=f'<body data-page-type="product"><div data-field="Model" data-model="{model}">{model}</div></body>'.encode()
  relative=f'page-{index}.html'; (snaproot/relative).write_bytes(body)
  rows.append({'source':'ep','source_role':'authoritative_existence','source_identity_value':binding['observed_identity_reference'],
   'requested_url':'https://example.test/'+model.lower(),'canonical_url':'https://example.test/'+model.lower(),'relative_path':relative,
   'sha256':hashlib.sha256(body).hexdigest(),'size':len(body),'content_type':'text/html','encoding':'utf-8','adapter_version':'synthetic-v1'})
 if reverse: rows.reverse()
 manifest={'schema_version':'snapshot-manifest-v1','synthetic':True,'approved_hosts':['example.test'],'snapshots':rows}
 manifest['content_fingerprint']=_digest(manifest); path=root/'snapshot-manifest.json'; path.write_bytes(canonical_bytes(manifest)); return path,snaproot,copy.deepcopy(manifest)

def _policy():
 def number(target,unit,scale=3): return {'kind':'number','rule_id':'number.'+target,'rule_version':'1','decimal_separator':'.','thousands_separator':None,'target_unit':unit,'scale':scale,'rounding':'ROUND_HALF_EVEN','conversions':{},'target_field':target}
 rules={'working_height':number('WorkingHeightM','m'),'rated_load_capacity':number('MaximumLoadCapacityKg','kg'),
  'machine_weight':number('MachineWeightKg','kg'),'year':number('Year',None,0),'hours_meter':number('HoursMeter','h'),
  'power_source':{'kind':'enum','rule_id':'power.v1','rule_version':'1','target_field':'PowerSource'},
  'terrain_type':{'kind':'enum','rule_id':'terrain.v1','rule_version':'1','target_field':'TerrainType'},
  'custom_spec':number('FutureField','mm')}
 value={'schema_version':'1.0.0','policy_version':'normalization-ep-v1','field_rules':rules}; value['fingerprint']=fingerprint(value); return value

def _observation(identity,key,value,unit,evidence):
 return {'canonical_identity':identity,'model':'MODEL','variant':None,'source_field_key':key,'source_label':key.replace('_',' ').title(),
  'raw_value':value,'raw_unit':unit,'source':'ep','source_url':'https://example.test/product','source_document':'fixture.html','source_page':'1',
  'source_section':'specifications','extraction_rule':'table.v1','evidence_references':[evidence],'relation_references':['relation-'+evidence],
  'locale':'en','qualifiers':['verified']}

def _normalized_products(reverse=False):
 a=canonical_identity('EP Equipment','MODEL-A').value; b=canonical_identity('EP Equipment','MODEL-B').value
 observations=[_observation(a,'working_height','10.000','m','e-a-height'),_observation(a,'rated_load_capacity','0.000','kg','e-a-zero'),
  _observation(a,'power_source','diesel',None,'e-a-power'),_observation(a,'year','2024',None,'e-a-year'),_observation(a,'hours_meter','0','h','e-a-hours'),
  _observation(a,'custom_spec','25','mm','e-a-spec'),_observation(b,'working_height','12.345','m','e-b-height'),
  _observation(b,'rated_load_capacity','1500','kg','e-b-load'),_observation(b,'machine_weight','2400','kg','e-b-weight'),
  _observation(b,'terrain_type','outdoor',None,'e-b-terrain')]
 products=[{'canonical_identity':a,'brand_code':'EP','canonical_model':'MODEL-A','variant':None,'source_titles':['A'],'source_category_keys':['lifts']},
           {'canonical_identity':b,'brand_code':'EP','canonical_model':'MODEL-B','variant':None,'source_titles':['B'],'source_category_keys':['lifts']}]
 if reverse: observations.reverse(); products.reverse()
 bundle={'schema_version':'1.0.0','fixture_only':True,'structure_verified':False,'artifact_references':[],'products':products,'observations':observations,
  'policy':_policy(),'category_catalog':{'categories':[{'category_key':'lifts'}]},'category_matrix':{'mappings':[{'mapping_id':'map','source_category_key':'lifts','mapping_status':'approved','target_category_key':'lifts','primary':True}]},
  'asset_decisions':{},'upstream_fingerprints':{'matching':'a'*64,'extraction':'b'*64}}
 return build_plan(bundle)

class CatalogStageContractTests(unittest.TestCase):
 def test_acquisition_semantic_id_paths_checkpoint_and_resume_contract(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory); plan,auth=_acquisition_contract(); first=_Transport([(200,{},[b'User-agent: *\nAllow: /\n']),(200,{'content-length':'6','etag':'"v1"','content-type':'application/octet-stream'},_interrupted())])
   AcquisitionSession(plan=plan,authorization=auth,transport=first,output_root=root,clock=lambda:'2026-01-01T00:00:00Z',pause=lambda host:None).acquire_all()
   checkpoint_path=next((root/'_operations/checkpoints').glob('*.json')); checkpoint=json.loads(checkpoint_path.read_text(encoding='utf-8')); attempt=checkpoint['attempt_id']; key=semantic_path_key(attempt,expected_prefix='attempt')
   validate(checkpoint,SCHEMAS/'acquisition-checkpoint.schema.json')
   self.assertRegex(key,r'^sidv1-[0-9a-f]{64}$'); self.assertEqual(key,checkpoint_path.stem); self.assertEqual(3,checkpoint['bytes_present']); self.assertIn(key,checkpoint['part_relative_path'])
   resumed=_Transport([(200,{},[b'User-agent: *\nAllow: /\n']),(206,{'content-length':'3','content-range':'bytes 3-5/6','etag':'"v1"','content-type':'application/octet-stream'},[b'def'])])
   result=AcquisitionSession(plan=plan,authorization=auth,transport=resumed,output_root=root,clock=lambda:'2026-01-01T00:00:00Z',pause=lambda host:None).resume(checkpoint_path.relative_to(root).as_posix())
   receipt=json.loads((root/'receipts'/f'{key}.json').read_text(encoding='utf-8')); self.assertEqual(attempt,receipt['attempt_id']); self.assertEqual(attempt,checkpoint['attempt_id']); self.assertTrue(verify_outputs(root)['valid']); self.assertEqual('completed',receipt['state']); self.assertEqual(2,len(resumed.calls))
   self.assertIn(attempt,(root/'acquisition-receipts.jsonl').read_text(encoding='utf-8'))
   second_root=root/'second'; second_plan,second_auth=_acquisition_contract('asset-b'); second=_Transport([(200,{},[b'User-agent: *\nAllow: /\n']),(200,{'content-length':'3','content-type':'application/octet-stream'},[b'xyz'])])
   AcquisitionSession(plan=second_plan,authorization=second_auth,transport=second,output_root=second_root,clock=lambda:'2026-01-01T00:00:00Z',pause=lambda host:None).acquire_all()
   second_receipt=json.loads(next((second_root/'receipts').glob('*.json')).read_text()); other=second_receipt['attempt_id']; other_key=semantic_path_key(other,expected_prefix='attempt')
   self.assertNotEqual(key,other_key); self.assertEqual(other_key,next((second_root/'receipts').glob('*.json')).stem); self.assertEqual(2,len(second.calls))
  with tempfile.TemporaryDirectory() as directory,mock.patch.object(acquisition_module,'_id',return_value='attempt:sha256:bad'):
   root=pathlib.Path(directory); plan,auth=_acquisition_contract(); transport=_Transport([])
   with self.assertRaises(UnsafePathError): AcquisitionSession(plan=plan,authorization=auth,transport=transport,output_root=root,clock=lambda:'fixed',pause=lambda host:None).acquire_all()
   self.assertEqual([],transport.calls); self.assertEqual([],list(root.rglob('*')))

 def test_two_product_matching_output_drives_extraction_contract(self):
  candidates=[_candidate('a','MODEL-A'),_candidate('b','MODEL-B')]; original=copy.deepcopy(candidates)
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory); matching,matching_path,manifest_before,rows_before=_matching(root,candidates); self.assertEqual(original,candidates)
   matching_before=json.loads(matching_path.read_text()); snapshot_path,snapshot_root,snapshot_before=_snapshot(root,matching,reverse=True); output=root/'extracted'
   extracted=extract(snapshot_path,snapshot_root,matching_path,output); self.assertEqual(manifest_before,json.loads((root/'discovery-manifest.json').read_text())); self.assertEqual(matching_before,json.loads(matching_path.read_text())); self.assertEqual(snapshot_before,json.loads(snapshot_path.read_text()))
   self.assertEqual('matching-extraction-binding-v1',matching['binding_contract_version']); self.assertEqual(_digest(matching['identity_bindings']),matching['binding_hash']); self.assertEqual(2,len(matching['identity_bindings']))
   raw=[json.loads(line) for line in (output/'raw-products.jsonl').read_text().splitlines()]; self.assertEqual(2,len(raw)); self.assertEqual({x['canonical_identity_value'] for x in matching['identity_bindings']},{x['canonical_identity_value'] for x in raw})
   for item in raw:
    model=next(iter(item['model_scopes'])); self.assertEqual(model,item['canonical_url'].rsplit('/',1)[-1].upper()); self.assertIn('evidence/'+model[-1].lower(),next(x['evidence_references'] for x in matching['identity_bindings'] if x['canonical_identity_value']==item['canonical_identity_value']))
   validate(matching,SCHEMAS/'matching-manifest.schema.json'); validate(extracted,SCHEMAS/'extraction-manifest.schema.json')
   ordered_root=root/'ordered'; ordered_root.mkdir(); matching_reversed,matching_reversed_path,_,_=_matching(ordered_root,list(reversed(candidates))); snapshot_reversed_path,snapshot_reversed_root,_=_snapshot(ordered_root,matching_reversed)
   extracted_reversed=extract(snapshot_reversed_path,snapshot_reversed_root,matching_reversed_path,ordered_root/'extracted')
   self.assertEqual(matching['binding_hash'],matching_reversed['binding_hash']); self.assertEqual(matching['output_hashes'],matching_reversed['output_hashes']); self.assertEqual(extracted['output_hashes'],extracted_reversed['output_hashes'])
   negative_root=root/'negative'; negative_root.mkdir()
   cases=('missing','duplicate','hash','version','namespace','role','unknown')
   for case in cases:
    with self.subTest(case=case):
     bad=copy.deepcopy(matching); snap=copy.deepcopy(snapshot_before)
     if case=='missing': bad['identity_bindings']=[]; bad['binding_hash']=_digest([])
     elif case=='duplicate': bad['identity_bindings'].append(copy.deepcopy(bad['identity_bindings'][0])); bad['binding_hash']=_digest(bad['identity_bindings'])
     elif case=='hash': bad['binding_hash']='0'*64
     elif case=='version': bad['binding_contract_version']='incompatible-v0'
     elif case=='namespace': bad['identity_bindings'][0]['source_namespace']='gam'; bad['binding_hash']=_digest(bad['identity_bindings'])
     elif case=='role': bad['identity_bindings'][0]['source_role']='supplemental'; bad['binding_hash']=_digest(bad['identity_bindings'])
     else: snap['snapshots'][0]['source_identity_value']='unknown-opaque-identity'; _sign(snap,'content_fingerprint')
     _sign(bad); bad_path=negative_root/(case+'-matching.json'); bad_path.write_bytes(canonical_bytes(bad)); snap_path=negative_root/(case+'-snapshot.json'); snap_path.write_bytes(canonical_bytes(snap)); target=negative_root/(case+'-output')
     with mock.patch.object(FixtureHtmlExtractionAdapter,'parse') as parser,self.assertRaises(ExtractionInputError): extract(snap_path,snapshot_root,bad_path,target)
     parser.assert_not_called(); self.assertFalse(target.exists())

 def test_two_product_normalization_adapter_reconciliation_contract(self):
  plan=_normalized_products(); reversed_plan=_normalized_products(reverse=True); documents=plan['products']; originals=copy.deepcopy(documents)
  projections=[adapt_normalized_product(x) for x in documents]; reversed_projections=[adapt_normalized_product(x) for x in reversed_plan['products']]
  self.assertEqual(originals,documents); self.assertEqual({x['canonical_identity_value']:x['fingerprint'] for x in projections},{x['canonical_identity_value']:x['fingerprint'] for x in reversed_projections})
  for product,projection in zip(documents,projections): validate(product,SCHEMAS/'producto.schema.json'); validate(projection,SCHEMAS/'jem-projection.schema.json')
  by_model={x['structured_fields']['model']:x for x in projections}; a=by_model['MODEL-A']['structured_fields']; b=by_model['MODEL-B']['structured_fields']
  self.assertEqual(('10','0','diesel','2024','0'),(a['working_height_m'],a['maximum_load_capacity_kg'],a['power_source'],a['year'],a['hours_meter'])); self.assertNotIn('machine_weight_kg',a)
  self.assertEqual(('12.345','1500','2400','outdoor'),(b['working_height_m'],b['maximum_load_capacity_kg'],b['machine_weight_kg'],b['terrain_type'])); self.assertTrue(all(not isinstance(v,float) for p in projections for v in p['structured_fields'].values()))
  self.assertEqual(1,len(by_model['MODEL-A']['product_specs'])); self.assertTrue(documents[0]['product_specs'][0]['observation_reference'])
  evidence={x['canonical_identity_value']:{e for field in x['field_evidence'] for e in field['provenance']['evidence_references']} for x in projections}; self.assertTrue(all(not (values & other) for identity,values in evidence.items() for other_identity,other in evidence.items() if identity!=other_identity))
  expected={'canonical_identity','model','variant','source_field_key','source_label','raw_value','raw_unit','normalized_value','normalized_unit','source','source_url','source_document','source_page','source_section','extraction_rule','evidence_references','relation_references','locale','qualifiers','rule_id','rule_version','policy_fingerprint','observation_id','conflict_group','review_references'}
  self.assertTrue(all(expected<=set(field['provenance']) and field['adapter_version']==ADAPTER_VERSION for p in projections for field in p['field_evidence']))
  snapshot={'collections':{'categories':[{'id':1,'slug':'maquinaria','parent_id':None,'product_type':'machinery'}],'brands':[],'suppliers':[],'products':[]}}; package={'entries':{f'products/{index}/producto.json':canonical_bytes(product) for index,product in enumerate(reversed(documents))}}
  root_contract={'collection':'categories','identity_field':'slug','identity':'maquinaria','parent_field':'parent_id','product_type':'machinery'}
  operations=build_operations(package,snapshot,{'supplier_optional':True},root_contract); projected_evidence={x['canonical_identity']:x for x in operations['projection_evidence']}
  self.assertEqual({x['canonical_identity_value'] for x in projections},set(projected_evidence)); self.assertEqual({x['fingerprint'] for x in projections},{x['projection_fingerprint'] for x in projected_evidence.values()}); self.assertTrue(all(x['adapter_version']==ADAPTER_VERSION for x in projected_evidence.values()))
  product_payloads=[x['payload_template'] for x in operations['operations'] if x['kind']=='product']; self.assertTrue(all(value is False for payload in product_payloads for value in (payload['price_visible'],payload['is_featured'],payload['is_published']))); self.assertTrue(all(payload['price'] is None for payload in product_payloads)); self.assertTrue(all(not isinstance(value,dict) for payload in product_payloads for key,value in payload.items() if key not in {'category_id','brand_id'}))
  with tempfile.TemporaryDirectory() as directory:
   destination=pathlib.Path(directory)/'normalized'; normalize_to(plan,plan['fingerprint'],destination); self.assertTrue(verify_output(destination)['valid'])
   mapping=json.loads((destination/'physical-identity-mappings.json').read_text()); validate(mapping,SCHEMAS/'semantic-physical-mapping.schema.json')
   for product_path in destination.glob('products/*/producto.json'): validate(json.loads(product_path.read_text()),SCHEMAS/'producto.schema.json')

 def test_adapter_negative_contract_matrix_is_fail_closed(self):
  base=_normalized_products()['products'][0]
  mutations=(lambda x:x.update(document_kind='wrong'),lambda x:x.update(schema_version='0'),lambda x:x['structured_fields']['WorkingHeightM'].pop('value'),
   lambda x:x['structured_fields']['WorkingHeightM'].update(unit='ft'),lambda x:x['structured_fields']['WorkingHeightM'].update(status='conflict'),
   lambda x:x['structured_fields']['WorkingHeightM'].update(observation_reference='missing'),lambda x:x['observations'].append(copy.deepcopy(x['observations'][0])),
   lambda x:x['structured_fields'].update(WorkingHeightFeet=x['structured_fields'].pop('WorkingHeightM')))
  for mutate in mutations:
   value=copy.deepcopy(base); before=copy.deepcopy(value); mutate(value); submitted=copy.deepcopy(value)
   with self.assertRaises(NormalizedProjectionError): adapt_normalized_product(value)
   self.assertEqual(submitted,value); self.assertNotEqual(before,value)
