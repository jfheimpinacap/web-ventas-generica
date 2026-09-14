import copy, json, pathlib, sys, tempfile, unittest
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.schema_validation import SUPPORTED_KEYWORDS, SchemaValidationError, validate, validate_schema_keywords

class SchemaTests(unittest.TestCase):
 def test_every_schema_has_valid_synthetic_fixture(self):
  schemas=sorted((ROOT/'schemas/v1').glob('*.schema.json'))
  self.assertEqual(82,len(schemas))
  for schema in schemas:
   fixture=ROOT/'fixtures/valid'/schema.name.replace('.schema.json','.json')
   self.assertTrue(fixture.exists(),schema.name)
   validate(json.loads(fixture.read_text(encoding="utf-8")),schema)
   validate_schema_keywords(schema)
  local_names={'local-apply-authorization','local-operation-receipt','local-apply-checkpoint','local-apply-manifest','local-verification-report','local-readiness-report','local-binary-observation-plan','local-binary-observation-report'}
  self.assertEqual(local_names,{path.name.removesuffix('.schema.json') for path in schemas if path.name.startswith('local-')})
  self.assertTrue(all(json.loads((ROOT/'schemas/v1'/(name+'.schema.json')).read_text(encoding='utf-8')).get('additionalProperties') is False for name in local_names))
  plan_schema=ROOT/'schemas/v1/local-binary-observation-plan.schema.json'
  report_schema=ROOT/'schemas/v1/local-binary-observation-report.schema.json'
  v1=json.loads((ROOT/'fixtures/valid/local-binary-observation-plan.json').read_text(encoding='utf-8'))
  v2=json.loads((ROOT/'fixtures/valid/local-binary-observation-plan-v2.json').read_text(encoding='utf-8'))
  report=json.loads((ROOT/'fixtures/valid/local-binary-observation-report.json').read_text(encoding='utf-8'))
  originals=copy.deepcopy((v1,v2,report))
  for value,schema in ((v1,plan_schema),(v2,plan_schema),(report,report_schema)):
   validate(value,schema); validate(value,schema)
  self.assertEqual(originals,(v1,v2,report))
  self.assertEqual({'binding_v1','binding_v2'},set(json.loads(plan_schema.read_text(encoding='utf-8'))['$defs']) & {'binding_v1','binding_v2'})
  self.assertIn('receipt_binding_v2',json.loads(report_schema.read_text(encoding='utf-8'))['$defs'])
  invalid=[]
  candidate=copy.deepcopy(v1); candidate['capture_supported']=True; invalid.append(candidate)
  candidate=copy.deepcopy(v1); candidate['capture_policy']=copy.deepcopy(v2['capture_policy']); invalid.append(candidate)
  candidate=copy.deepcopy(v1); candidate['targets']=copy.deepcopy(v2['targets']); candidate['capture_policy']=copy.deepcopy(v2['capture_policy']); invalid.append(candidate)
  candidate=copy.deepcopy(v2); candidate['capture_supported']=False; invalid.append(candidate)
  candidate=copy.deepcopy(v2); candidate['targets']=copy.deepcopy(v1['targets']); candidate['rules_version']=v1['rules_version']; invalid.append(candidate)
  candidate=copy.deepcopy(v2); candidate['next_permitted_step']='prompt_302_limited_local_get_capture'; invalid.append(candidate)
  candidate=copy.deepcopy(v2); candidate.pop('capture_policy'); invalid.append(candidate)
  candidate=copy.deepcopy(v2); candidate['capture_policy'].pop('allowed_method'); invalid.append(candidate)
  required=json.loads(plan_schema.read_text(encoding='utf-8'))['$defs']['binding_v2']['required']
  for field in required:
   candidate=copy.deepcopy(v2); candidate['targets'][0]['bindings'][0].pop(field); invalid.append(candidate)
  candidate=copy.deepcopy(v2); candidate['targets'][0]['bindings'][0]['unknown']=True; invalid.append(candidate)
  for candidate in invalid:
   with self.subTest(rules_version=candidate['rules_version'],capture=candidate['capture_supported'],step=candidate['next_permitted_step'],policy=candidate.get('capture_policy')):
    with self.assertRaises(SchemaValidationError): validate(candidate,plan_schema)
  for field in required:
   candidate=copy.deepcopy(report); candidate['receipts'][0]['bindings'][0].pop(field)
   with self.subTest(report_binding_missing=field),self.assertRaises(SchemaValidationError): validate(candidate,report_schema)
  candidate=copy.deepcopy(report); candidate['receipts'][0]['bindings'][0]['unknown']=True
  with self.assertRaises(SchemaValidationError): validate(candidate,report_schema)
  nullable=('product_id','declared_extension','declared_content_type','declared_size_bytes')
  self.assertTrue(all(field in binding for receipt in report['receipts'] for binding in receipt['bindings'] for field in nullable))
 def test_required_unknown_version_and_property_are_rejected(self):
  schema=ROOT/'schemas/v1/run-manifest.schema.json'; value=json.loads((ROOT/'fixtures/valid/run-manifest.json').read_text(encoding="utf-8"))
  for mutation in ('missing','version','extra'):
   candidate=copy.deepcopy(value)
   if mutation=='missing': candidate.pop('run_id')
   elif mutation=='version': candidate['schema_version']='2.0.0'
   else: candidate['secret']='must not pass'
   with self.assertRaises(SchemaValidationError): validate(candidate,schema)
 def test_unknown_provenance_and_enum_rejected(self):
  schema=ROOT/'schemas/v1/normalized-value.schema.json'; value=json.loads((ROOT/'fixtures/valid/normalized-value.json').read_text(encoding="utf-8")); value['resolution_status']='confident'
  with self.assertRaises(SchemaValidationError): validate(value,schema)
  audit=ROOT/'schemas/v1/audit-issue.schema.json'; value=json.loads((ROOT/'fixtures/valid/audit-issue.json').read_text(encoding="utf-8")); value['severity']='fatal-ish'
  with self.assertRaises(SchemaValidationError): validate(value,audit)
  raw_schema=ROOT/'schemas/v1/raw-evidence.schema.json'; raw=json.loads((ROOT/'fixtures/valid/raw-evidence.json').read_text(encoding="utf-8")); raw['source_role']='inferred_from_adapter_name'
  with self.assertRaises(SchemaValidationError): validate(raw,raw_schema)
  discovered_schema=ROOT/'schemas/v1/discovered-product-entry.schema.json'; discovered=json.loads((ROOT/'fixtures/valid/discovered-product-entry.json').read_text(encoding="utf-8")); discovered['source_role']='supplemental'
  with self.assertRaises(SchemaValidationError): validate(discovered,discovered_schema)
 def test_wrong_types_constraints_and_structured_errors(self):
  schema=ROOT/'schemas/v1/package-manifest.schema.json'; value=json.loads((ROOT/'fixtures/valid/package-manifest.json').read_text(encoding="utf-8"))
  for field,replacement,keyword in [('package_id',7,'type'),('artifacts',[{'unexpected':True}],'required'),('discovered_universe',['x','x'],'uniqueItems')]:
   candidate=copy.deepcopy(value); candidate[field]=replacement
   with self.assertRaises(SchemaValidationError) as cm: validate(candidate,schema)
   self.assertEqual('SCHEMA_INVALID',cm.exception.code); self.assertEqual(keyword,cm.exception.keyword); self.assertTrue(cm.exception.schema); self.assertTrue(cm.exception.instance_path)
 def test_ref_resolution_is_local_and_fail_closed(self):
  schema=ROOT/'schemas/v1/normalized-value.schema.json'; validate(json.loads((ROOT/'fixtures/valid/normalized-value.json').read_text(encoding="utf-8")),schema)
  templates=['missing.schema.json','../outside.schema.json','https://example.invalid/schema.json','file:///tmp/schema.json','#/missing']
  with tempfile.TemporaryDirectory(dir=ROOT/'schemas/v1') as directory:
   folder=pathlib.Path(directory)
   for index,ref in enumerate(templates):
    candidate=folder/f'bad-{index}.schema.json'; candidate.write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:test','type':'object','properties':{'x':{'$ref':ref}}}), encoding="utf-8", newline="\n")
    with self.assertRaises(SchemaValidationError): validate({'x':1},candidate)
   cycle=folder/'cycle.schema.json'; cycle.write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:test','type':'object','properties':{'x':{'$ref':'cycle.schema.json'}}}), encoding="utf-8", newline="\n")
   with self.assertRaises(SchemaValidationError): validate({'x':1},cycle)
 def test_unsupported_keyword_fails_schema_audit(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'schemas/v1') as directory:
   schema=pathlib.Path(directory)/'structural.schema.json'
   supported={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:test','type':'object','properties':{'image':{'type':'string'},'pdf':{'items':{'const':{'notAKeyword':1}}},'arbitrary-field':{'enum':[{'alsoNotAKeyword':2}] }},'$defs':{'target':{'oneOf':[{'const':'a'},{'const':'b'}]}}}
   schema.write_text(json.dumps(supported),encoding='utf-8',newline='\n'); original_keywords=frozenset(SUPPORTED_KEYWORDS)
   validate_schema_keywords(schema); validate_schema_keywords(schema)
   self.assertEqual(original_keywords,SUPPORTED_KEYWORDS)
   for location,expected_path in [({'definitelyUnsupportedKeyword':True},'$.definitelyUnsupportedKeyword'),({'properties':{'image':{'definitelyUnsupportedKeyword':True}}},'$.properties.image.definitelyUnsupportedKeyword'),({'$defs':{'pdf':{'definitelyUnsupportedKeyword':True}}},'$.$defs.pdf.definitelyUnsupportedKeyword')]:
    candidate=dict(supported); candidate.update(location); schema.write_text(json.dumps(candidate),encoding='utf-8',newline='\n')
    with self.subTest(path=expected_path),self.assertRaises(SchemaValidationError) as cm: validate_schema_keywords(schema)
    self.assertEqual('definitelyUnsupportedKeyword',cm.exception.keyword); self.assertEqual(expected_path,cm.exception.instance_path)
   semantic_cases=[
    ({'const':1},1,True),({'const':1},True,False),({'enum':[1]},True,False),
    ({'if':{'properties':{'kind':{'const':'a'}}},'then':{'properties':{'value':{'const':1}}},'else':{'properties':{'value':{'const':2}}}},{'kind':'a','value':1},True),
    ({'if':{'properties':{'kind':{'const':'a'}}},'then':{'properties':{'value':{'const':1}}},'else':{'properties':{'value':{'const':2}}}},{'kind':'a','value':2},False),
    ({'if':{'properties':{'kind':{'const':'a'}}},'then':{'properties':{'value':{'const':1}}},'else':{'properties':{'value':{'const':2}}}},{'kind':'b','value':2},True),
    ({'allOf':[{'type':'integer'},{'minimum':1}]},1,True),({'allOf':[{'type':'integer'},{'minimum':1}]},0,False),
    ({'anyOf':[{'const':'x'},{'const':'y'}]},'y',True),({'anyOf':[{'const':'x'},{'const':'y'}]},'z',False),
    ({'oneOf':[{'type':'integer'},{'const':'x'}]},1,True),({'oneOf':[{'const':'x'},{'const':'y'}]},'z',False),
    ({'oneOf':[{'type':'integer'},{'const':1}]},1,False),({'oneOf':[{'const':1},{'type':'integer'}]},1,False),
    ({'not':{'const':'blocked'}},'allowed',True),({'not':{'const':'blocked'}},'blocked',False)]
   for index,(document,value,valid) in enumerate(semantic_cases):
    schema.write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':f'urn:test:{index}',**document}),encoding='utf-8',newline='\n')
    with self.subTest(semantic=index):
     if valid: validate(value,schema); validate(value,schema)
     else:
      with self.assertRaises(SchemaValidationError): validate(value,schema)
 def test_conflict_missing_and_manual_states_are_representable(self):
  schema=ROOT/'schemas/v1/normalized-value.schema.json'; base=json.loads((ROOT/'fixtures/valid/normalized-value.json').read_text(encoding="utf-8"))
  for state in ['conflict','missing','manual_approval_required','manual_approved']:
   value=copy.deepcopy(base); value['resolution_status']=state
   if state=='conflict': value['conflict']={'values':['a','b'],'reason':'synthetic disagreement'}
   validate(value,schema)
 def test_discovered_product_remains_when_not_importable(self):
  value=json.loads((ROOT/'fixtures/valid/package-manifest.json').read_text(encoding="utf-8"))
  discovered_entry=value['discovered_universe'][0]
  self.assertNotIn(discovered_entry,value['importable_universe']); self.assertIn(discovered_entry,value['blocked'])
 def test_asset_contracts_reject_unknown_fields_and_enums(self):
  cases=[('payload-manifest.schema.json','payload-manifest.json','provenance_type','invented_source'),('asset-record.schema.json','asset-record.json','validation_status','decoded_ok'),('asset-relation.schema.json','asset-relation.json','eligibility_status','selected')]
  for schema_name,fixture_name,field,bad in cases:
   value=json.loads((ROOT/'fixtures/valid'/fixture_name).read_text(encoding='utf-8'))
   target=value['bindings'][0] if 'bindings' in value else value; target[field]=bad
   with self.assertRaises(SchemaValidationError): validate(value,ROOT/'schemas/v1'/schema_name)
  value=json.loads((ROOT/'fixtures/valid/asset-review.json').read_text(encoding='utf-8')); value['unexpected']=True
  with self.assertRaises(SchemaValidationError): validate(value,ROOT/'schemas/v1/asset-review.schema.json')

if __name__=='__main__': unittest.main()
