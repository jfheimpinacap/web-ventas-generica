import pathlib,sys,unittest
from unittest import mock

ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from jem_nexus_import.local_client import READ_TARGETS,LocalJemJsonReader,LocalReadError
from jem_nexus_import.normalization import NormalizationError,normalize_collections
from jem_nexus_local_transport import get_json_bytes

class Prompt311ReadContractTests(unittest.TestCase):
 def test_exact_complete_targets_are_constant(self):
  self.assertEqual({
   "categories":"/api/categories?include_inactive=true","brands":"/api/brands?include_inactive=true",
   "suppliers":"/api/suppliers?include_inactive=true","products":"/api/products?include_unpublished=true",
   "product_images":"/api/product-images","product_specs":"/api/product-specs","technical_sheets":"/api/technical-sheets/"},READ_TARGETS)

 def test_transport_rejects_every_non_literal_query_before_network_objects(self):
  invalid=("/api/products?include_unpublished=false","/api/products?include_unpublished=true&search=x",
           "/api/products?include_unpublished=true&include_unpublished=true","/api/products?include_unpublished%3Dtrue",
           "/api/product-images?include_unpublished=true","/api/categories?include_inactive=True")
  with mock.patch("jem_nexus_local_transport.build_opener") as opener, mock.patch("jem_nexus_local_transport.Request") as request:
   for target in invalid:
    with self.subTest(target=target),self.assertRaises(LocalReadError): get_json_bytes("http://localhost:1"+target,{},1,10)
   opener.assert_not_called(); request.assert_not_called()

 def test_reader_requires_array_collection(self):
  reader=LocalJemJsonReader("http://localhost:1",transport=lambda *_:(200,"application/json",b'{}'),requires_auth=False)
  with self.assertRaisesRegex(LocalReadError,"JSON array"): reader.read_collection("products")

 def test_real_dto_shape_normalizes_relations_and_preserves_explicit_null(self):
  product={field:None for field in ("brand_id","supplier_id","technical_sheet_id","model","sku","working_height_m","terrain_type","year","hours_meter","maximum_load_capacity_kg","machine_weight_kg","power_source","price")}
  product.update({"id":4,"name":"P","slug":"p","category_id":1,"category":{"id":1},"brand":None,
   "product_type":"machinery","condition":"used","short_description":"s","description":"d",
   "includes_technical_review":True,"includes_commercial_technical_advice":True,"includes_coordinated_delivery":True,
   "price_currency":"CLP","price_tax_mode":"plus_vat","price_visible":False,"stock_status":"available",
   "is_featured":False,"is_published":False,"created_at":"x","updated_at":"x"})
  source={"categories":[{"id":1,"parent":None}],"products":[product],"product_images":[{"id":5,"product":4,"image":"/media/x","file_url":"/api/product-images/5/file"}],"product_specs":[{"id":6,"product":4,"name":"k"}]}
  value=normalize_collections(source)
  self.assertIsNone(value["categories"][0]["parent_id"]); self.assertTrue(value["products"][0]["relations_complete"])
  self.assertEqual((4,"k"),(value["product_images"][0]["product_id"],value["product_specs"][0]["key"]))

 def test_missing_bool_and_contradictory_relationships_fail_closed(self):
  with self.assertRaises(NormalizationError): normalize_collections({"product_images":[{"id":1,"product":True}]})
  with self.assertRaises(NormalizationError): normalize_collections({"products":[{"category_id":1,"category":{"id":2}}]})

 def test_nullable_relation_must_be_present_and_nested_relations_must_agree(self):
  base={field:None for field in ("brand_id","supplier_id","technical_sheet_id","model","sku","working_height_m","terrain_type","year","hours_meter","maximum_load_capacity_kg","machine_weight_kg","power_source","price")}
  base.update({"id":4,"name":"P","slug":"p","category_id":1,"category":{"id":1},"product_type":"machinery","condition":"used","short_description":"","description":"","includes_technical_review":False,"includes_commercial_technical_advice":False,"includes_coordinated_delivery":False,"price_currency":"CLP","price_tax_mode":"plus_vat","price_visible":False,"stock_status":"available","is_featured":False,"is_published":False,"created_at":"x","updated_at":"x"})
  missing=dict(base); missing.pop("supplier_id")
  with self.assertRaises(NormalizationError): normalize_collections({"products":[missing]})
  contradictory=dict(base,brand_id=2,brand={"id":3})
  with self.assertRaises(NormalizationError): normalize_collections({"products":[contradictory]})
  incomplete=dict(base,brand_id=2,brand={"name":"missing id"})
  with self.assertRaises(NormalizationError): normalize_collections({"products":[incomplete]})

if __name__=="__main__": unittest.main()
