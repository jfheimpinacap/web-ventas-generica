import copy, json, pathlib, sys, tempfile, unittest
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.schema_validation import SchemaValidationError, validate, validate_schema_keywords

class SchemaTests(unittest.TestCase):
 def test_every_schema_has_valid_synthetic_fixture(self):
  schemas=sorted((ROOT/'schemas/v1').glob('*.schema.json'))
  self.assertEqual(22,len(schemas))
  for schema in schemas:
   fixture=ROOT/'fixtures/valid'/schema.name.replace('.schema.json','.json')
   self.assertTrue(fixture.exists(),schema.name)
   validate(json.loads(fixture.read_text()),schema)
   validate_schema_keywords(schema)
 def test_required_unknown_version_and_property_are_rejected(self):
  schema=ROOT/'schemas/v1/run-manifest.schema.json'; value=json.loads((ROOT/'fixtures/valid/run-manifest.json').read_text())
  for mutation in ('missing','version','extra'):
   candidate=copy.deepcopy(value)
   if mutation=='missing': candidate.pop('run_id')
   elif mutation=='version': candidate['schema_version']='2.0.0'
   else: candidate['secret']='must not pass'
   with self.assertRaises(SchemaValidationError): validate(candidate,schema)
 def test_unknown_provenance_and_enum_rejected(self):
  schema=ROOT/'schemas/v1/normalized-value.schema.json'; value=json.loads((ROOT/'fixtures/valid/normalized-value.json').read_text()); value['resolution_status']='confident'
  with self.assertRaises(SchemaValidationError): validate(value,schema)
  audit=ROOT/'schemas/v1/audit-issue.schema.json'; value=json.loads((ROOT/'fixtures/valid/audit-issue.json').read_text()); value['severity']='fatal-ish'
  with self.assertRaises(SchemaValidationError): validate(value,audit)
  raw_schema=ROOT/'schemas/v1/raw-evidence.schema.json'; raw=json.loads((ROOT/'fixtures/valid/raw-evidence.json').read_text()); raw['source_role']='inferred_from_adapter_name'
  with self.assertRaises(SchemaValidationError): validate(raw,raw_schema)
  discovered_schema=ROOT/'schemas/v1/discovered-product-entry.schema.json'; discovered=json.loads((ROOT/'fixtures/valid/discovered-product-entry.json').read_text()); discovered['source_role']='supplemental'
  with self.assertRaises(SchemaValidationError): validate(discovered,discovered_schema)
 def test_wrong_types_constraints_and_structured_errors(self):
  schema=ROOT/'schemas/v1/package-manifest.schema.json'; value=json.loads((ROOT/'fixtures/valid/package-manifest.json').read_text())
  for field,replacement,keyword in [('package_id',7,'type'),('artifacts',[{'unexpected':True}],'required'),('discovered_universe',['x','x'],'uniqueItems')]:
   candidate=copy.deepcopy(value); candidate[field]=replacement
   with self.assertRaises(SchemaValidationError) as cm: validate(candidate,schema)
   self.assertEqual('SCHEMA_INVALID',cm.exception.code); self.assertEqual(keyword,cm.exception.keyword); self.assertTrue(cm.exception.schema); self.assertTrue(cm.exception.instance_path)
 def test_ref_resolution_is_local_and_fail_closed(self):
  schema=ROOT/'schemas/v1/normalized-value.schema.json'; validate(json.loads((ROOT/'fixtures/valid/normalized-value.json').read_text()),schema)
  templates=['missing.schema.json','../outside.schema.json','https://example.invalid/schema.json','file:///tmp/schema.json','#/missing']
  with tempfile.TemporaryDirectory(dir=ROOT/'schemas/v1') as directory:
   folder=pathlib.Path(directory)
   for index,ref in enumerate(templates):
    candidate=folder/f'bad-{index}.schema.json'; candidate.write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:test','type':'object','properties':{'x':{'$ref':ref}}}))
    with self.assertRaises(SchemaValidationError): validate({'x':1},candidate)
   cycle=folder/'cycle.schema.json'; cycle.write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:test','type':'object','properties':{'x':{'$ref':'cycle.schema.json'}}}))
   with self.assertRaises(SchemaValidationError): validate({'x':1},cycle)
 def test_unsupported_keyword_fails_schema_audit(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'schemas/v1') as directory:
   schema=pathlib.Path(directory)/'unsupported.schema.json'; schema.write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:test','type':'string','oneOf':[]}))
   with self.assertRaises(SchemaValidationError) as cm: validate_schema_keywords(schema)
   self.assertEqual('oneOf',cm.exception.keyword)
 def test_conflict_missing_and_manual_states_are_representable(self):
  schema=ROOT/'schemas/v1/normalized-value.schema.json'; base=json.loads((ROOT/'fixtures/valid/normalized-value.json').read_text())
  for state in ['conflict','missing','manual_approval_required','manual_approved']:
   value=copy.deepcopy(base); value['resolution_status']=state
   if state=='conflict': value['conflict']={'values':['a','b'],'reason':'synthetic disagreement'}
   validate(value,schema)
 def test_discovered_product_remains_when_not_importable(self):
  value=json.loads((ROOT/'fixtures/valid/package-manifest.json').read_text())
  discovered_entry=value['discovered_universe'][0]
  self.assertNotIn(discovered_entry,value['importable_universe']); self.assertIn(discovered_entry,value['blocked'])

if __name__=='__main__': unittest.main()
