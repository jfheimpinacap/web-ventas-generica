import ast, importlib.util, json, pathlib, sys, tempfile, unittest, unicodedata
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.errors import IdentityCollisionError, ImmutableEvidenceError, PathCollisionError, UnsafePathError, HashMismatchError
from catalog_acquisition.identity import (AmbiguousIdentityLinkError, CanonicalIdentityRegistry,
 IdentityLink, SourceIdentityRegistry, canonical_identity, source_identity)
from catalog_acquisition.discovered import SupplementalDiscoveryError, discovered_product_entry
from catalog_acquisition.paths import category_slug, create_layout, document_filename, image_filename, model_key, safe_join, technical_sheet_filename, LayoutRegistry, windows_collision_key
from catalog_acquisition.serialization import canonical_bytes, content_fingerprint
from catalog_acquisition.storage import atomic_write, sha256_bytes, write_once
from catalog_acquisition.adapters import SyntheticAdapter
from jem_nexus_import.bindings import BindingResolver, MissingBindingError
from jem_nexus_import.projection import project_candidate

class IdentityTests(unittest.TestCase):
 def test_source_identity_excludes_mutable_observations(self):
  first=source_identity('source-a','record-7'); second=source_identity('source-a','record-7')
  self.assertEqual(first.value,second.value) # display/model/URL/adapter version are not constructor inputs
 def test_canonical_identity_is_source_independent_and_variants_separate(self):
  first=canonical_identity('BRAND','EFL 181')
  self.assertEqual(first.value,canonical_identity('BRAND','EFL 181').value)
  self.assertNotEqual(first.value,canonical_identity('BRAND','EFL 181','long-range').value)
  self.assertNotIn('source',first.value)
 def test_candidate_creation_does_not_approve_link(self):
  candidate=canonical_identity('BRAND','EFL 181')
  link=IdentityLink(source_identity('series','page').value,None,(candidate.value,'candidate-b'),'series-candidates','1.0.0','manual_approval_required',None,True)
  with self.assertRaises(AmbiguousIdentityLinkError): link.assert_importable(type_mapping_approved=True,category_mapping_approved=True)
 def test_collision_registries_are_distinct(self):
  r=SourceIdentityRegistry(); r.register('id','origin-a')
  with self.assertRaises(IdentityCollisionError): r.register('id','origin-b')
  c=CanonicalIdentityRegistry(); c.register('canonical','brand','model-a')
  with self.assertRaises(IdentityCollisionError): c.register('canonical','brand','model-b')
 def test_series_can_emit_unapproved_candidates(self):
  link=IdentityLink(source_identity('series','page').value,None,('candidate-a','candidate-b'),'series','1.0.0','manual_approval_required',None,True)
  self.assertEqual(2,len(link.candidate_canonical_identity_values)); self.assertIsNone(link.canonical_identity_value)
 def test_ambiguous_alias_requires_review(self):
  link=IdentityLink(source_identity('source','alias-record').value,None,('candidate-a',),'ambiguous-alias','1.0.0','manual_approval_required',None,True)
  with self.assertRaises(AmbiguousIdentityLinkError): link.assert_importable(type_mapping_approved=True,category_mapping_approved=True)
 def test_rule_and_manual_approval_require_auditable_references(self):
  source=source_identity('source','record').value; candidate=canonical_identity('BRAND','MODEL').value
  missing_rule=IdentityLink(source,candidate,(),'','', 'derived_by_approved_rule',None,False)
  missing_decision=IdentityLink(source,candidate,(),'manual','1.0.0','manual_approved',None,False)
  for link in (missing_rule,missing_decision):
   with self.assertRaises(AmbiguousIdentityLinkError): link.assert_importable(type_mapping_approved=True,category_mapping_approved=True)
  automatic=IdentityLink(source,candidate,(),'exact-components','1.0.0','derived_by_approved_rule',None,False)
  manual=IdentityLink(source,candidate,(),'manual-review','1.0.0','manual_approved','decision-1',False)
  automatic.assert_importable(type_mapping_approved=True,category_mapping_approved=True)
  manual.assert_importable(type_mapping_approved=True,category_mapping_approved=True)
  with self.assertRaises(AmbiguousIdentityLinkError): automatic.assert_importable(type_mapping_approved=False,category_mapping_approved=True)

class DiscoveryTests(unittest.TestCase):
 def test_unresolved_authoritative_entry_survives_without_canonical_identity(self):
  source=source_identity('authority','record-a')
  entry=discovered_product_entry(source,source_role='authoritative_existence',raw_observation_ids=('obs-a',),canonical_candidate_identity_values=('candidate-a','candidate-b'),blocking_issue_codes=('AMBIGUOUS_CANONICAL_MATCH',),evidence_ids=('ev-a',),review_status='blocked')
  self.assertIsNone(entry.canonical_identity_value); self.assertEqual(2,len(entry.canonical_candidate_identity_values))
 def test_supplemental_source_cannot_create_discovered_entry(self):
  with self.assertRaises(SupplementalDiscoveryError): discovered_product_entry(source_identity('supplement','record'),source_role='supplemental',raw_observation_ids=('obs',))
 def test_cases_a_through_f_preserve_layer_boundaries(self):
  cases=json.loads((ROOT/'fixtures/discovery-lifecycle-cases.json').read_text(encoding="utf-8"))
  self.assertEqual(set('abcdef'),{name[5] for name in cases})
  self.assertIn('discovered-a',cases['case_a_official_ambiguous']['discovered_universe'])
  self.assertEqual([],cases['case_c_supplemental']['discovered_universe_additions'])
  self.assertEqual(1,len(cases['case_d_two_sources_one_product']['importable_universe']))
  self.assertEqual([],cases['case_e_series_page']['resolved_canonical_universe'])
  self.assertFalse(cases['case_f_approval']['isolated_approval_boolean_allowed'])

class PathTests(unittest.TestCase):
 def test_windows_cases_stable(self):
  cases=['EFL 181','EFL+181','EFL:181','CON','con.txt','AUX','LPT1','Modelo.','Modelo ','Tijera Ⅱ','Máquina ágil']
  self.assertEqual([model_key(x) for x in cases],[model_key(x) for x in cases])
  self.assertEqual('_CON',model_key('CON')); self.assertEqual('_con.txt',model_key('con.txt'))
  self.assertEqual('EFL_181',model_key('EFL:181'))
 def test_unicode_collision_and_case_insensitive_collision(self):
  a='Café'; b=unicodedata.normalize('NFD',a); self.assertEqual(windows_collision_key(model_key(a)),windows_collision_key(model_key(b)))
  r=LayoutRegistry(); r.add('model','Model','Model')
  with self.assertRaises(PathCollisionError): r.add('model','model','model')
 def test_category_transliteration_collision(self):
  self.assertEqual(category_slug('Camión'),category_slug('Camion'))
  r=LayoutRegistry(); r.add('category','Camión',category_slug('Camión'))
  with self.assertRaises(PathCollisionError): r.add('category','Camion',category_slug('Camion'))
 def test_reject_unsafe(self):
  for value in ['', '.', '..', '/abs', r'C:\\temp', r'\\server\\share', 'C:/drive',
                '../escape', 'safe/../escape', r'safe\..\escape', '//host/path',
                r'\\?\C:\escape', 'nul\0name', 'control\x1fname']:
   with self.subTest(label=repr(value)):
    with self.assertRaises(UnsafePathError): model_key(value)
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   unsafe=['', '.', '..', '../escape', 'safe/../escape', 'safe/../../escape',
    '/absolute', '//server/share', r'\rooted', r'\\server\share', r'C:\absolute',
    'C:relative', r'\\?\C:\escape', r'\\.\NUL', r'safe\child',
    r'safe\..\escape', 'file:stream', 'safe//child', 'safe/./child', 'segment.',
    'segment ', 'nul\0name', 'control\x1fname', 'CON', 'con.txt', 'AUX.json',
    'COM1', 'LPT9.log', 'D:/different-drive', 'C:/drive']
   for relative in unsafe:
    with self.subTest(relative=repr(relative)):
     with self.assertRaises(UnsafePathError): safe_join(root,relative)

 def test_accept_canonical_portable_paths(self):
  valid=['catalogo', 'catalogo/electricas', 'catalogo/electricas/EFL-181/producto.json',
   '_pipeline/manifests/run.json', 'modelo+plus/imagenes/archivo.webp',
   'modelo con espacio/documentos/ficha.pdf', 'catálogo/máquinas/ficha-técnica.pdf']
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve()
   for relative in valid:
    with self.subTest(relative=repr(relative)):
     self.assertEqual(root.joinpath(*relative.split('/')),safe_join(root,relative))
 def test_semantic_labels_are_distinct_from_relative_paths(self):
  for label in ('M:1','r:1','serie:alpha','EFL+181','modelo con espacio','Máquina ágil','safe-key'):
   with self.subTest(label=label):
    key=model_key(label); self.assertNotIn(':',key); self.assertNotIn('/',key); self.assertNotIn('\\',key)
  self.assertEqual('M_1',model_key('M:1'))
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d); filename=document_filename('ZZ','M:1','manual','es','r:1')
   self.assertEqual('ZZ-M_1-manual-es-r_1.pdf',filename)
   self.assertEqual(root/filename,safe_join(root,filename))
   for path in ('M:1','C:foo','file:stream'):
    with self.assertRaises(UnsafePathError): safe_join(root,path)
 def test_transformed_semantic_label_collision_preserves_both_originals(self):
  registry=LayoutRegistry(); registry.add('model','M:1',model_key('M:1'))
  with self.assertRaises(PathCollisionError) as collision:
   registry.add('model','M?1',model_key('M?1'))
  self.assertEqual('M:1',collision.exception.context['first'])
  self.assertEqual('M?1',collision.exception.context['second'])
 def test_manifest_round_trip(self):
  r=LayoutRegistry(); entry=r.add('model','EFL:181',model_key('EFL:181')); self.assertEqual('EFL:181',entry['original_name'])
  decomposed=unicodedata.normalize('NFD','Tijéra'); traced=r.add('model-unicode',decomposed,model_key(decomposed))
  self.assertEqual(decomposed,traced['original_name']); self.assertNotEqual(unicodedata.normalize('NFC',decomposed),traced['original_name'])
 def test_layout_and_future_names(self):
  with tempfile.TemporaryDirectory() as d:
   registry=LayoutRegistry(); canonical=canonical_identity('SYNTHETIC','EFL 181')
   manifest=create_layout(pathlib.Path(d),'SYNTHETIC','Máquinas','EFL 181',resolved_canonical_identity_value=canonical.value,registry=registry)
   self.assertEqual('SYNTHETIC/catalogo/maquinas/EFL 181',manifest['product_path'])
  self.assertEqual('SYNTHETIC-EFL 181-1-principal.jpg',image_filename('SYNTHETIC','EFL 181',1,'JPG',True))
  self.assertEqual('SYNTHETIC-EFL 181-ficha-tecnica-es-r1.pdf',technical_sheet_filename('SYNTHETIC','EFL 181','es','r1'))
 def test_two_sources_one_canonical_product_make_one_folder(self):
  a=source_identity('source-a','a'); b=source_identity('source-b','b'); canonical=canonical_identity('SYNTHETIC','EFL 181')
  self.assertNotEqual(a.value,b.value)
  with tempfile.TemporaryDirectory() as d:
   registry=LayoutRegistry()
   one=create_layout(pathlib.Path(d),'SYNTHETIC','Machines','EFL 181',resolved_canonical_identity_value=canonical.value,registry=registry)
   two=create_layout(pathlib.Path(d),'SYNTHETIC','Machines','EFL 181',resolved_canonical_identity_value=canonical.value,registry=registry)
   self.assertEqual(one['product_path'],two['product_path'])
  fixture=json.loads((ROOT/'fixtures/multi-source-one-product.json').read_text(encoding="utf-8"))
  self.assertEqual(2,len(fixture['source_identity_values'])); self.assertEqual(1,len(fixture['discovered_universe']))
  self.assertEqual(1,len(fixture['resolved_canonical_universe'])); self.assertEqual(1,len(fixture['importable_universe']))

class SerializationTests(unittest.TestCase):
 def test_determinism_and_semantics(self):
  a={'schema_version':'1','rules_version':'1','aliases':['b','a'],'name':'Cafe\u0301','created_at':'one','relative_path':'a\\b'}
  b={'relative_path':'a/b','name':'Café','aliases':['a','b'],'rules_version':'1','schema_version':'1','created_at':'two'}
  self.assertEqual(content_fingerprint(a),content_fingerprint(b)); self.assertEqual(canonical_bytes(a),canonical_bytes(a))
  self.assertNotEqual(content_fingerprint(a),content_fingerprint(a|{'name':'Other'}))
  unicode_value={'schema_version':'1','rules_version':'1','text':'guion ‐, tildes áéíóú, ñ y 漢字'}
  first=canonical_bytes(unicode_value); second=canonical_bytes(dict(unicode_value))
  self.assertEqual(first,second); self.assertTrue(first.endswith(b"\n")); self.assertNotIn(b"\r\n",first)
  with tempfile.TemporaryDirectory() as directory:
   path=pathlib.Path(directory)/'unicode.jsonl'; path.write_bytes(first)
   self.assertEqual(unicode_value,json.loads(path.read_text(encoding="utf-8")))
 def test_requires_versions(self):
  with self.assertRaises(ValueError): content_fingerprint({'name':'x'})

class StorageTests(unittest.TestCase):
 def test_atomic_and_write_once(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'raw/evidence'; data=b'valid'; digest=sha256_bytes(data)
   atomic_write(p,data,digest); self.assertEqual(data,p.read_bytes()); self.assertFalse(list(p.parent.glob('*.tmp')))
   self.assertFalse(write_once(p,data,digest))
   with self.assertRaises(ImmutableEvidenceError): write_once(p,b'changed')
   with self.assertRaises(HashMismatchError): write_once(pathlib.Path(d)/'other',data,'0'*64)
   self.assertEqual(data,p.read_bytes())

class ProjectionTests(unittest.TestCase):
 def test_lift_height_is_spec_never_working_height(self):
  result=project_candidate({'name':'Lift','maximum_lift_height_mm':4800,'battery_voltage_v':48})
  self.assertNotIn('working_height_m',result['structured_fields']); self.assertEqual(2,len(result['product_specs']))
 def test_enum_unknown_blocks(self):
  result=project_candidate({'condition':'invented'}); self.assertFalse(result['ready']); self.assertEqual('UNKNOWN_ENUM',result['issues'][0]['code'])
 def test_structured_only_allowed(self): self.assertEqual({'name':'x'},project_candidate({'name':'x'})['structured_fields'])

class BindingTests(unittest.TestCase):
 def test_explicit_external_root_and_produced(self):
  resolver=BindingResolver([{'namespace':'root','key':'maquinarias','binding_type':'entity_id','value':7}], [{'namespace':'category','key':'forklifts','binding_type':'entity_id','value':8}])
  self.assertEqual(7,resolver.resolve({'scope':'external','namespace':'root','key':'maquinarias','binding_type':'entity_id'}))
  self.assertEqual(8,resolver.resolve({'scope':'produced','namespace':'category','key':'forklifts','binding_type':'entity_id'}))
 def test_missing_is_structured_not_keyerror(self):
  with self.assertRaises(MissingBindingError) as cm: BindingResolver().resolve({'scope':'external','namespace':'root','key':'maquinarias','binding_type':'entity_id'})
  self.assertEqual('MISSING_BINDING',cm.exception.as_dict()['code']); self.assertNotIsInstance(cm.exception,KeyError)

class ArchitectureTests(unittest.TestCase):
 def test_no_cross_imports_or_network_modules(self):
  acquisition='\n'.join(p.read_text(encoding="utf-8") for p in (ROOT/'catalog_acquisition').glob('*.py'))
  parsers='\n'.join((ROOT/'catalog_acquisition'/name).read_text(encoding="utf-8") for name in ('adapters.py','discovery_adapters.py'))
  importer='\n'.join(p.read_text(encoding="utf-8") for p in (ROOT/'jem_nexus_import').glob('*.py'))
  self.assertNotIn('jem_nexus_import',acquisition); self.assertNotIn('catalog_acquisition',importer)
  for forbidden in ['requests','http.client','socket','selenium','playwright']:
   self.assertNotIn(f'import {forbidden}',parsers+importer)
  self.assertNotIn('urllib.request',parsers+importer)
  for path in ROOT.rglob('*.py'):
   source=path.read_text(encoding="utf-8"); tree=ast.parse(source)
   for call in (node for node in ast.walk(tree) if isinstance(node,ast.Call)):
    error_values={keyword.value.value for keyword in call.keywords if keyword.arg=='errors' and isinstance(keyword.value,ast.Constant)}
    self.assertFalse({'ignore','replace'} & error_values,f'{path}:{call.lineno}')
    if isinstance(call.func,ast.Attribute) and call.func.attr in {'read_text','write_text'}:
     self.assertIn('encoding',{keyword.arg for keyword in call.keywords},f'{path}:{call.lineno}')
    if isinstance(call.func,ast.Name) and call.func.id=='open':
     mode=call.args[1].value if len(call.args)>1 and isinstance(call.args[1],ast.Constant) else 'r'
     if 'b' not in mode: self.assertIn('encoding',{keyword.arg for keyword in call.keywords},f'{path}:{call.lineno}')
 def test_adapter_uses_injected_bytes(self): self.assertEqual('synthetic.fixture',next(iter(SyntheticAdapter().discover(b'synthetic.fixture')))['stable_source_key'])

if __name__=='__main__': unittest.main()
