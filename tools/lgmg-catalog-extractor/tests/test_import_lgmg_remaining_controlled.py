import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).parents[1] / "import_lgmg_remaining_controlled.py"
spec = importlib.util.spec_from_file_location("remaining_controlled", MODULE)
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)


class Args:
    dry_run = apply = verify = rollback = False
    checkpoint = "state.json"; batch_size = 20; resume = False
    confirm_apply = confirm_rollback = None
    approved_partial_resume_fingerprint = None


class Response:
    def __init__(self, url, value, mime="application/json"):
        self.url = url; self.raw = json.dumps(value).encode(); self.mime = mime
        self.headers = self
    def geturl(self): return self.url
    def read(self, limit): return self.raw
    def get_content_type(self): return self.mime


class Opener:
    def __init__(self, response): self.response = response; self.request = None; self.timeout = None
    def open(self, request, timeout): self.request = request; self.timeout = timeout; return self.response


class ControlledImporterTests(unittest.TestCase):
    @staticmethod
    def spec_row(label="Altura Ⅱ", value="≤ 3", order="7", unit="m", **changes):
        row = dict(zip(tool.SPECIFICATION_COLUMNS,
            ("source", "MⅡ", "1", "", str(order), label, value, "", "", unit, "false", "")))
        row.update(changes)
        return row

    def test_01_cli_has_exact_inputs_modes_and_no_token_argument(self):
        parser = tool.build_parser(); destinations = {a.dest for a in parser._actions}
        self.assertTrue({"plan_input", "remaining_audit_input", "repaired_media_input", "output_dir", "api_base_url"} <= destinations)
        self.assertFalse({"token", "publish", "model", "filter"} & destinations)
        with self.assertRaises(SystemExit): parser.parse_args([])
        base = ["--plan-input","p","--remaining-audit-input","a","--repaired-media-input","r","--output-dir","o","--api-base-url","https://api.example"]
        with self.assertRaises(SystemExit): parser.parse_args(base + ["--dry-run", "--verify"])
        for mode in ("--dry-run", "--apply", "--verify", "--rollback"):
            with self.assertRaises(SystemExit): parser.parse_args(base + [mode])

    def test_02_token_only_environment_and_never_returned_in_error(self):
        self.assertEqual(tool.access_token({tool.TOKEN_ENV: "opaque-secret"}), "opaque-secret")
        for env in ({}, {tool.TOKEN_ENV: "bad\nsecret"}):
            with self.assertRaises(tool.ConflictError) as caught: tool.access_token(env)
            self.assertNotIn("secret", str(caught.exception))

    def test_03_exact_confirmations_and_read_modes_reject_them(self):
        a = Args(); a.apply = True
        with self.assertRaises(tool.ConflictError): tool.validate_cli(a)
        a.confirm_apply = tool.APPLY_CONFIRMATION; self.assertEqual(tool.validate_cli(a), "apply")
        b = Args(); b.rollback = True; b.confirm_rollback = tool.ROLLBACK_CONFIRMATION
        self.assertEqual(tool.validate_cli(b), "rollback")
        c = Args(); c.dry_run = True; c.confirm_apply = tool.APPLY_CONFIRMATION
        with self.assertRaises(tool.ConflictError): tool.validate_cli(c)

    def test_04_fingerprints_families_outputs_and_verdicts_are_closed(self):
        self.assertEqual(len(tool.APPROVED_FINGERPRINTS), 6)
        self.assertTrue(all(len(x) == 64 for x in tool.APPROVED_FINGERPRINTS.values()))
        self.assertEqual(len(tool.FAMILIES), 6); self.assertEqual(len(tool.OUTPUT_NAMES), 8)
        self.assertEqual(tool.VERDICTS, {"DRY_RUN_READY","APPLY_COMPLETE","APPLY_PARTIAL","VERIFY_COMPLETE","PARTIAL_RESUME_READY","ROLLBACK_COMPLETE","CONFLICT"})

    def test_05_closed_cohort_is_read_from_ast(self):
        pairs = tool._load_closed_pairs()
        self.assertEqual((len(pairs), len(set(pairs))), (21, 21))
        self.assertIn(("S0607EⅡ", "lgmg-c7eb4374a0c40929"), pairs)

    def test_06_literal_payload_is_conservative(self):
        row = {"approved_name":"Elevador LGMG SR1018E-2", "metric_model":"SR1018E-2", "stock_status":"on_request",
               "maximum_load_capacity_kg":"450", "target_power_source":"electric_lithium", "description":"Preservada"}
        payload = tool.product_payload(row, 2, 3)
        self.assertEqual(payload["model"], "SR1018E-2"); self.assertEqual(payload["maximum_load_capacity_kg"], 450.0)
        self.assertEqual(payload["power_source"], "electric_lithium"); self.assertEqual(payload["description"], "Preservada")
        for key in ("year","hours_meter","working_height_m","terrain_type","machine_weight_kg","price"):
            self.assertIsNone(payload[key])
        self.assertFalse(payload["price_visible"]); self.assertFalse(payload["is_published"]); self.assertFalse(payload["is_featured"])

    def test_07_capacity_and_energy_are_not_invented(self):
        row = {"approved_name":"N Ⅱ", "metric_model":"Ⅱ", "stock_status":"on_request",
               "maximum_load_capacity_kg":"invalid", "target_power_source":"diesel"}
        payload = tool.product_payload(row, 1, 1)
        self.assertIsNone(payload["maximum_load_capacity_kg"]); self.assertIsNone(payload["power_source"])

    def test_08_specs_preserve_unicode_value_unit_and_order(self):
        value = tool.spec_payload(self.spec_row("Ángulo", "≤ Ⅱ", unit="°"), 9)
        self.assertEqual(value, {"product":9,"name":"Ángulo","key":"","value":"≤ Ⅱ","unit":"°","order":7})

    def test_08a_exact_specification_header_is_closed(self):
        header = ",".join(tool.SPECIFICATION_COLUMNS)
        row = "source,M,1,,1,MODÈLE,Métrica,,,,false,"
        parsed = tool.specification_csv_rows((header + "\n" + row + "\n").encode())
        self.assertEqual(parsed[0]["source_label"], "MODÈLE")
        for bad in (header.rsplit(",", 1)[0], header + ",unexpected",
                    header.replace("source_label", "name")):
            with self.assertRaises(tool.ConflictError):
                tool.specification_csv_rows((bad + "\n").encode())

    def test_08b_approved_adapter_fallbacks_order_unit_and_unicode(self):
        source = self.spec_row("MODÈLE", "Métrica Ⅱ ≤", order="2", unit="")
        self.assertEqual(tool.specification_identity(source),
            {"name":"MODÈLE", "key":"", "value":"Métrica Ⅱ ≤", "unit":"", "order":2})
        normalized = dict(source, normalized_label="Ángulo máximo", normalized_value="9.8 m",
                          group_order="99", specification_order="4", unit="°")
        self.assertEqual(tool.specification_identity(normalized),
            {"name":"Ángulo máximo", "key":"", "value":"9.8 m", "unit":"°", "order":4})

    def test_09_batch_default_split_and_range(self):
        self.assertEqual([len(x) for x in tool.batch_ranges()], [20, 16])
        self.assertEqual(len(tool.batch_ranges(36, 1)), 36)
        for value in (0, -1, 21):
            with self.assertRaises(tool.ConflictError): tool.batch_ranges(36, value)

    def test_10_safe_paths_reject_traversal_absolute_backslash(self):
        for value in ("../x", "/x", "C:/x", "a\\b", "./x", ""):
            with self.assertRaises(tool.ConflictError): tool.safe_relative(value)
        self.assertEqual(tool.safe_relative("corrected-media/images/x.jpg"), "corrected-media/images/x.jpg")

    def test_11_http_requires_https_except_loopback(self):
        self.assertEqual(tool.normalize_origin("https://API.EXAMPLE/"), "https://api.example")
        self.assertEqual(tool.normalize_origin("http://127.0.0.1:8765"), "http://127.0.0.1:8765")
        for url in ("http://example.com", "https://u:p@example.com", "https://example.com/path", "https://example.com?q=x"):
            with self.assertRaises(tool.ConflictError): tool.normalize_origin(url)

    def test_12_read_client_uses_timeout_auth_and_blocks_mutation(self):
        opener = Opener(Response("http://127.0.0.1:5000/api/auth/me", {"id": 1}))
        client = tool.ApiClient("http://127.0.0.1:5000", "opaque", "dry_run", opener)
        self.assertEqual(client.get("/api/auth/me"), {"id":1}); self.assertEqual(opener.timeout, 20)
        self.assertEqual(opener.request.headers["Authorization"], "Bearer opaque")
        with self.assertRaises(tool.ControlledImportError): client.post("/api/products", {})

    def test_13_redirects_are_rejected(self):
        handler = tool.NoRedirect()
        request = type("R", (), {"full_url":"https://one.example/api/products"})()
        with self.assertRaises(tool.ControlledImportError): handler.redirect_request(request, None, 302, "", {}, "https://two.example/api/products")

    def test_14_pagination_is_bounded_and_detects_cycle(self):
        class Client:
            origin="https://api.example"
            def get(self, path): return {"results":[], "next":path}
        with self.assertRaises(tool.ControlledImportError): tool.paginated(Client(), "/api/products")

    def test_15_taxonomy_exact_brand_duplicate_and_hierarchy(self):
        state = {"categories":[{"id":1,"name":"Maquinaria","slug":"maquinaria","product_type":"machinery","parent":None,"is_active":True}] +
                [{"id":i+2,"name":name,"slug":tool.CATEGORY_CONTRACT[name],"product_type":"machinery","parent":1,"is_active":True} for i,name in enumerate(tool.FAMILIES)],
                "brands":[{"id":9,"name":"LGMG","is_active":True}]}
        _, cats, brand = tool.resolve_taxonomy(state); self.assertEqual((len(cats), brand["id"]), (6, 9))
        state["brands"].append(dict(state["brands"][0], id=10))
        with self.assertRaises(tool.ConflictError): tool.resolve_taxonomy(state)

    def test_16_classification_exact_conflict_and_idempotence(self):
        row={"approved_name":"Producto A13JE","metric_model":"A13JE","approved_family":tool.FAMILIES[0],"stock_status":"on_request"}
        data={"products":[row]}; cats={tool.FAMILIES[0]:{"id":2}}; brand={"id":3}
        empty={"products":[]}; self.assertEqual(tool.classify_products(data,empty,cats,brand)[0]["status"],"create_candidate")
        exact={"id":4,"name":"Producto A13JE","model":"A13JE","category":2,"brand":3,"is_published":False,"is_featured":False,"price":None,"price_visible":False}
        self.assertEqual(tool.classify_products(data,{"products":[exact]},cats,brand)[0]["status"],"already_imported_exact")
        self.assertEqual(tool.classify_products(data,{"products":[dict(exact,name="Otro")]},cats,brand)[0]["status"],"conflict_existing_product")

    def test_17_checkpoint_atomic_and_secret_absence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"state.json"; expected={"state":"dry_run_ready","dry_run_fingerprint_sha256":"x"}
            tool.atomic_json(path, expected)
            self.assertEqual(json.loads(path.read_text()), expected)
            self.assertFalse(list(Path(temp).glob("*.staging")))
            self.assertNotIn("Bearer", path.read_text())

    def test_18_csv_bom_crlf_formula_and_exact_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"x.csv"; tool.write_csv(path,("v",),[{"v":"=cmd"},{"v":"ok"}]); raw=path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf")); self.assertIn(b"\r\n",raw); self.assertIn(b"'=cmd",raw)

    def test_19_media_multipart_preserves_bytes_and_primary(self):
        raw=b"\xff\xd8\xffunchanged"
        body,mime=tool._multipart_image(4,{"association_order":"1","is_primary":"true","original_filename":"A13JE.jpg","mime":"image/jpeg"},"a.jpg",raw)
        self.assertIn(raw,body); self.assertIn(b"is_main",body); self.assertIn(b"true",body); self.assertTrue(mime.startswith("multipart/form-data"))

    def test_20_dry_fingerprint_deterministic_and_sensitive(self):
        data={"fingerprints":tool.APPROVED_FINGERPRINTS}; decision={"row":{"approval_key":"a"},"status":"create_candidate","payload":{"model":"Ⅱ"}}
        first=tool.dry_run_fingerprint(data,[decision],"https://a","remote","head")
        self.assertEqual(first,tool.dry_run_fingerprint(data,[decision],"https://a","remote","head")); self.assertNotEqual(first,tool.dry_run_fingerprint(data,[decision],"https://b","remote","head"))

    def test_22_complete_operation_plan_contracts_and_dependencies(self):
        products=[]; specs={}; images={}; sheets={}; decisions=[]
        for index in range(36):
            model=f"M{index:02}"; key=f"s{index:02}"
            row={"source_order":index+1,"source_key":key,"metric_model":model,"approval_key":f"a{index:02}"}
            products.append(row)
            spec_count=30 if index < 13 else 29
            specs[key]=[self.spec_row(f"Ángulo {n} Ⅱ", f"≤ {n}", n, "°",
                        source_key=key, metric_model=model) for n in range(spec_count)]
            count=2 if index < 35 else 1
            images[model]=[{"sha256":f"{index:02x}"*32,"size_bytes":"10","association_order":str(n+1),
                "is_primary":"true" if n == 0 else "false","original_filename":"x.jpg"} for n in range(count)]
            sheets[model]={"datasheet_upload_allowed":index < 33,"corrected_sha256":f"{index+1:02x}"*32,"corrected_size_bytes":"20"}
            decisions.append({"row":row,"payload":{"model":model},"status":"create_candidate","product":None})
        data={"products":products,"specs":specs,"images":images,"sheets":sheets}
        operations=tool.build_operations(data,decisions,20)
        counts=tool.operation_counts(operations)
        self.assertEqual(counts["product_operations"],36)
        self.assertEqual(counts["image_operations"],71)
        self.assertEqual(counts["datasheet_operations"],33)
        self.assertEqual(counts["specification_operations"],1057)
        self.assertEqual(counts["total"],1197)
        self.assertEqual(len({op["operation_key"] for op in operations}),1197)
        spec_operations=[op for op in operations if op["resource_type"]=="specification"]
        self.assertEqual(len({op["payload_sha256"] for op in spec_operations}),1057)
        self.assertEqual(len({tool.canonical(op["request_template"]) for op in spec_operations}),1057)
        self.assertTrue(all(op["specification_index"] >= 1 for op in spec_operations))
        tool.validate_operation_dependencies(operations)
        self.assertTrue(all(op["path_template"] in {"/api/technical-sheets","/api/products","/api/product-specs","/api/product-images"} for op in operations))
        self.assertTrue(all(op["depends_on_operation"] for op in operations if op["resource_type"] in {"image","specification"}))

    def test_23_superseded_fingerprint_and_checkpoint_states(self):
        self.assertEqual(tool.SUPERSEDED_INCOMPLETE_DRY_RUN_FINGERPRINT_SHA256,
            "85bb67b06624bbbb5b7a8d102c00faa776884c9a394eaf62cd8be3e7f9e72553")
        self.assertEqual(len(tool.CHECKPOINT_STATES),7)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"cp.json"; tool.atomic_json(path,{"state":"dry_run_ready",
                "dry_run_fingerprint_sha256":tool.SUPERSEDED_INCOMPLETE_DRY_RUN_FINGERPRINT_SHA256})
            with self.assertRaises(tool.ConflictError): tool.read_checkpoint(path)
            tool.atomic_json(path,{"state":"dry_run_ready", "dry_run_fingerprint_sha256":
                "bda45b2889f54055332a529df141fc6abfcfa5f3e9cfe04320d5313b991cbd31"})
            with self.assertRaises(tool.ConflictError): tool.read_checkpoint(path)

    def test_26_schema_slug_policy_and_noncanonical_conflict(self):
        self.assertEqual((tool.TOOL_VERSION,tool.CHECKPOINT_SCHEMA_VERSION,tool.OPERATION_CONTRACT_VERSION),("2.2.2","2.2","2.2"))
        self.assertEqual(set(tool.CATEGORY_CONTRACT),set(tool.FAMILIES))
        self.assertEqual(tool.CATEGORY_SLUG_POLICY,"blocking_functional_filter")
        state={"categories":[{"id":1,**tool.ROOT_CATEGORY_CONTRACT}] +
            [{"id":i+2,"name":name,"slug":tool.CATEGORY_CONTRACT[name],"parent":1,
              "product_type":"machinery","is_active":True} for i,name in enumerate(tool.FAMILIES)],
            "brands":[{"id":9,"name":"LGMG","slug":"lgmg","is_active":True}]}
        target=next(x for x in state["categories"] if x["name"]=="Elevadores tipo brazo articulado")
        target["slug"]="levadores-tipo-brazo-articulado"
        with self.assertRaisesRegex(tool.ConflictError,"category_slug_mismatch"):
            tool.resolve_taxonomy(state)

    def test_27_individual_spec_template_keys_dependencies_and_duplicate(self):
        row={"source_order":1,"source_key":"source","metric_model":"MⅡ","approval_key":"approved"}
        decision={"row":row,"payload":{"model":"MⅡ"},"status":"create_candidate","product":None}
        base={"products":[row],"images":{"MⅡ":[]},"sheets":{"MⅡ":{"datasheet_upload_allowed":False}}}
        first=self.spec_row()
        data={**base,"specs":{"source":[first,dict(first,source_value="≤ 4")]}}
        one=tool.build_operations(data,[decision],20); two=tool.build_operations(data,[decision],20)
        specs=[op for op in one if op["resource_type"]=="specification"]
        self.assertEqual(one,two); self.assertEqual([x["specification_index"] for x in specs],[1,2])
        self.assertEqual(specs[0]["specification_name"],"Altura Ⅱ")
        self.assertEqual(specs[0]["association_order"],"")
        self.assertEqual(specs[0]["payload_sha256"],tool.sha(tool.canonical(specs[0]["request_template"])))
        self.assertEqual(len({op["operation_key"] for op in one}),len(one))
        tool.validate_operation_dependencies(one)
        duplicate={**base,"specs":{"source":[first,dict(first)]}}
        with self.assertRaisesRegex(tool.ConflictError,"duplicate_specification_request"):
            tool.build_operations(duplicate,[decision],20)

    def test_27a_real_sr0818_rows_are_distinct_and_index_is_not_signature(self):
        row={"source_order":1,"source_key":"lgmg-86a5a5b6b61de976","metric_model":"SR0818E-2","approval_key":"a"}
        decision={"row":row,"payload":{"model":"SR0818E-2"},"status":"create_candidate","product":None}
        base={"products":[row],"images":{"SR0818E-2":[]},"sheets":{"SR0818E-2":{"datasheet_upload_allowed":False}}}
        first=self.spec_row("MODÈLE","SR0818E-2",1,"",source_key=row["source_key"],metric_model="SR0818E-2",
                            requires_review="true",maximum_load_capacity_candidate_kg="680")
        second=self.spec_row("Medidas","Métrica",2,"",source_key=row["source_key"],metric_model="SR0818E-2",requires_review="true")
        operations=tool.build_operations({**base,"specs":{row["source_key"]:[first,second]}},[decision],20)
        specs=[op for op in operations if op["resource_type"]=="specification"]
        self.assertEqual([op["specification_index"] for op in specs],[1,2])
        self.assertEqual(len({op["payload_sha256"] for op in specs}),2)
        self.assertEqual(len({op["operation_key"] for op in specs}),2)
        self.assertEqual(specs[0]["depends_on_operation_key"],specs[1]["depends_on_operation_key"])
        # El índice de auditoría no forma parte de la firma semántica.
        duplicate=dict(first, specification_order="1")
        with self.assertRaisesRegex(tool.ConflictError,"duplicate_specification_request"):
            tool.build_operations({**base,"specs":{row["source_key"]:[first,duplicate]}},[decision],20)

        twenty_nine=[first,second] + [self.spec_row(f"Dato {n} Ⅱ",f"Valor {n} ≤",n,"",
            source_key=row["source_key"],metric_model="SR0818E-2") for n in range(3,30)]
        full=tool.build_operations({**base,"specs":{row["source_key"]:twenty_nine}},[decision],20)
        self.assertEqual(len([op for op in full if op["resource_type"]=="specification"]),29)

    def test_27b_checkpoint_210_is_rejected_before_mutation(self):
        expected={"schema_version":"2.1","tool":tool.TOOL_NAME,"version":tool.TOOL_VERSION}
        old=dict(expected,version="2.1.0")
        with self.assertRaisesRegex(tool.ConflictError,"incompatible"):
            tool.validate_checkpoint_static(old,expected)

    def test_24_resources_are_reduced_and_dynamic(self):
        root={"id":41,"name":"Maquinaria","slug":"maquinaria","parent":None,"product_type":"machinery","is_active":True,"volatile":"x"}
        cats={name:{"id":100+i,"name":name,"slug":tool.CATEGORY_CONTRACT[name],"parent":41,"product_type":"machinery","is_active":True} for i,name in enumerate(tool.FAMILIES)}
        value=tool.resource_view(root,cats,{"id":77,"name":"LGMG","is_active":True})
        self.assertEqual(value["brand"],{"id":77,"name":"LGMG"}); self.assertEqual(len(value["categories"]),7)
        self.assertNotIn("volatile",value["categories"][0])

    def test_25_origin_rejects_api_suffix(self):
        with self.assertRaises(tool.ConflictError): tool.normalize_origin("http://localhost:5000/api")

    def test_21_source_contains_no_lgmg_download_url_or_publish_option(self):
        source=MODULE.read_text(encoding="utf-8")
        self.assertNotIn("https://www.lgmglifts.com",source); self.assertNotIn('"--publish"',source)
        self.assertNotIn("import requests",source); self.assertNotIn("telemetry",source.casefold())


    def test_28_closed_legacy_constants_and_cli_binding(self):
        self.assertEqual(tool.LEGACY_CHECKPOINT_SHA256, "dbb5ece22d1dcaabf16e8cb9c3bba1ebb57c1acec30fde68ec8bfe40a9a25eef")
        self.assertEqual(tool.LEGACY_CHECKPOINT_SIZE, 1825474)
        a = Args(); a.apply = True; a.resume = True; a.confirm_apply = tool.APPLY_CONFIRMATION
        with self.assertRaises(tool.ConflictError): tool.validate_cli(a)
        a.approved_partial_resume_fingerprint = "a" * 64
        self.assertEqual(tool.validate_cli(a), "apply")
        b = Args(); b.verify = True; b.approved_partial_resume_fingerprint = "a" * 64
        with self.assertRaises(tool.ConflictError): tool.validate_cli(b)

    def test_29_rate_pacing_uses_fake_clock_and_sleep(self):
        now = [0.0]; waits = []
        def sleep(seconds): waits.append(seconds); now[0] += seconds
        pace = tool.RateLimitCoordinator(clock=lambda: now[0], sleep=sleep)
        pace.before_request(); pace.before_request()
        self.assertEqual(waits, [33.0])
        self.assertEqual(pace.diagnostic["proactive_wait_count"], 1)
        self.assertEqual(tool.RATE_LIMIT_POLICY["queue_limit"], 0)
        self.assertTrue(tool.RATE_LIMIT_POLICY["rejection_before_handler"])

    def test_30_retry_after_seconds_date_fallback_and_bounds(self):
        pace = tool.RateLimitCoordinator(clock=lambda: 0, sleep=lambda _: None)
        self.assertEqual(pace.retry_delay("12"), 12)
        current = tool.datetime(2026, 1, 1, tzinfo=tool.timezone.utc)
        self.assertEqual(pace.retry_delay("Thu, 01 Jan 2026 00:00:10 GMT", current), 10)
        self.assertEqual(pace.retry_delay(None), 660)
        for bad in ("invalid", "0", "901"):
            with self.assertRaises(tool.ControlledImportError): pace.retry_delay(bad, current)

    def test_31_product_status_and_partial_fingerprint_are_derived(self):
        planned = [{"operation_key":"a","metric_model":"uno"}, {"operation_key":"b","metric_model":"uno"},
                   {"operation_key":"c","metric_model":"dos"}, {"operation_key":"d","metric_model":"tres"}]
        completed = [{"operation_key":"a","resource_id":1,"resolved_payload_sha256":"1"},
                     {"operation_key":"c","resource_id":2,"resolved_payload_sha256":"2"}]
        self.assertEqual(tool.product_statuses(planned, completed),
                         {"uno":"in_progress", "dos":"completed", "tres":"not_started"})
        value = {"version":tool.LEGACY_VERSION,"tool_head":tool.LEGACY_TOOL_HEAD,
            "fingerprints":tool.APPROVED_FINGERPRINTS,"remote_state_fingerprint_sha256":tool.LEGACY_REMOTE_FINGERPRINT,
            "planned_operations_fingerprint_sha256":tool.LEGACY_OPERATIONS_FINGERPRINT,
            "dry_run_fingerprint_sha256":tool.LEGACY_DRY_RUN_FINGERPRINT,
            "completed_operations":completed,"planned_operations":planned}
        first = tool.partial_resume_fingerprint(value, "f"*64, {"remote":"same"}, "h"*40)
        self.assertEqual(first, tool.partial_resume_fingerprint(value, "f"*64, {"remote":"same"}, "h"*40))
        self.assertNotEqual(first, tool.partial_resume_fingerprint(value, "f"*64, {"remote":"changed"}, "h"*40))

    def test_32_legacy_plan_is_validated_and_reused_before_remote_reconstruction(self):
        planned = ([{"resource_type":"datasheet","metric_model":"M","operation_key":f"d{i}"} for i in range(33)] +
                   [{"resource_type":"product","metric_model":"M","operation_key":f"p{i}"} for i in range(36)] +
                   [{"resource_type":"specification","metric_model":"M","operation_key":f"s{i}"} for i in range(1057)] +
                   [{"resource_type":"image","metric_model":"M","operation_key":f"i{i}"} for i in range(71)])
        for order, operation in enumerate(planned, 1): operation["operation_order"] = order
        completed = [dict(operation, resource_id=order) for order, operation in enumerate(planned[:65], 1)]
        legacy = {"version":tool.LEGACY_VERSION,"schema_version":tool.LEGACY_SCHEMA_VERSION}
        checkpoint_value = {**legacy, "planned_operations":planned, "completed_operations":completed,
                            "resources_created":{"products":[],"images":[],"specifications":[],"datasheets":[]},
                            "planned_operations_fingerprint_sha256":tool.LEGACY_OPERATIONS_FINGERPRINT,
                            "dry_run_fingerprint_sha256":tool.LEGACY_DRY_RUN_FINGERPRINT}
        events = []
        def validate(value, raw):
            events.append("legacy_validated")
            return checkpoint_value
        def snapshot(client):
            events.append("snapshot")
            return {}
        base_result = {"operations":planned,"resources_created":{},"external_effects":{},"products":[{"metric_model":"M"}]}
        with tempfile.TemporaryDirectory() as temp, mock.patch.multiple(tool,
                validate_paths=mock.DEFAULT, validate_inputs=mock.DEFAULT, normalize_origin=mock.DEFAULT,
                batch_ranges=mock.DEFAULT, classify_checkpoint=mock.DEFAULT, snapshot=mock.DEFAULT,
                resolve_taxonomy=mock.DEFAULT, classify_products=mock.DEFAULT, resource_view=mock.DEFAULT,
                build_operations=mock.DEFAULT, remote_fingerprint=mock.DEFAULT, operations_fingerprint=mock.DEFAULT,
                tool_head=mock.DEFAULT, dry_run_fingerprint=mock.DEFAULT, validate_operation_dependencies=mock.DEFAULT,
                checkpoint_contract=mock.DEFAULT, _base_result=mock.DEFAULT, partial_resume_fingerprint=mock.DEFAULT,
                product_statuses=mock.DEFAULT, validate_canonical_operations=mock.DEFAULT,
                validate_completed_operations=mock.DEFAULT, validate_completed_remote_resources=mock.DEFAULT,
                write_outputs=mock.DEFAULT) as mocks:
            mocks["validate_inputs"].return_value = {"fingerprints":{},"products":[]}
            mocks["normalize_origin"].return_value = "https://api.example"
            mocks["batch_ranges"].return_value = []
            mocks["classify_checkpoint"].side_effect = lambda *args: (events.append("legacy_validated") or
                ("legacy_apply_partial", checkpoint_value, b"legacy"))
            mocks["snapshot"].side_effect = snapshot
            mocks["resolve_taxonomy"].return_value = ({}, {}, {})
            mocks["classify_products"].return_value = [{"row":{"metric_model":str(i)},"status":"create_candidate"} for i in range(36)]
            mocks["resource_view"].return_value = {}
            checkpoint_value["resources_preexisting"] = {}
            checkpoint_value["mutations_executed"] = 65
            mocks["remote_fingerprint"].return_value = "remote"
            mocks["operations_fingerprint"].return_value = "operations"
            mocks["tool_head"].return_value = "head"
            mocks["dry_run_fingerprint"].return_value = "dry"
            mocks["_base_result"].return_value = base_result
            mocks["partial_resume_fingerprint"].return_value = "partial"
            mocks["product_statuses"].return_value = {"M":"in_progress"}
            code = tool.run(Path(temp),Path(temp),Path(temp),Path(temp),"https://api.example","verify","token",
                            checkpoint=Path(temp)/"checkpoint.json",client_factory=lambda *args: object())
        self.assertEqual(code, 0)
        self.assertEqual(events, ["legacy_validated", "snapshot"])
        mocks["build_operations"].assert_not_called()

    @staticmethod
    def canonical_fixture(completed_count=65, state="apply_partial"):
        planned = []
        def append(kind, model, dependency=None, sequence=0):
            template = {"kind":kind,"model":model,"sequence":sequence}
            operation = {"operation_order":len(planned)+1,"metric_model":model,"resource_type":kind,
                "depends_on_operation":dependency["operation_order"] if dependency else "",
                "depends_on_operation_key":dependency["operation_key"] if dependency else "",
                "request_template":template,"payload_sha256":tool.sha(tool.canonical(template))}
            operation["operation_key"] = tool.operation_key_for(operation); planned.append(operation); return operation
        for index in range(36):
            model=f"M{index:02}"; sheet=append("datasheet",model) if index < 33 else None
            product=append("product",model,sheet)
            for sequence in range(30 if index < 13 else 29): append("specification",model,product,sequence)
            for sequence in range(2 if index < 35 else 1): append("image",model,product,sequence)
        completed = [dict(op, resource_id=1000 + op["operation_order"]) for op in planned[:completed_count]]
        resources = {name:[] for name in ("products","images","specifications","datasheets")}
        for done in completed: resources[done["resource_type"] + "s"].append(done["resource_id"])
        products = [{"approval_key":f"a{i:02}","metric_model":f"M{i:02}"} for i in range(36)]
        checkpoint = {"schema_version":"2.2","operation_contract_version":"2.2","tool":tool.TOOL_NAME,
            "version":tool.TOOL_VERSION,"tool_head":"head","state":state,"api_base":"https://api.example",
            "batch_size":20,"fingerprints":tool.APPROVED_FINGERPRINTS,
            "approval_keys":sorted(x["approval_key"] for x in products),"models":sorted(x["metric_model"] for x in products),
            "planned_operations":planned,"completed_operations":completed,"resources_created":resources,
            "mutations_executed":completed_count,"dry_run_fingerprint_sha256":"d"*64}
        checkpoint["planned_operations_fingerprint_sha256"] = tool.operations_fingerprint(planned)
        statuses = tool.product_statuses(planned, completed)
        checkpoint["products"] = {row["approval_key"]:{"metric_model":row["metric_model"],
            "status":statuses[row["metric_model"]],"created":{}} for row in products}
        return checkpoint, {"fingerprints":tool.APPROVED_FINGERPRINTS,"products":products}

    def test_33_checkpoint_classification_is_early_explicit_and_fail_closed(self):
        self.assertEqual(tool.CHECKPOINT_KINDS,{"new_dry_run","dry_run_ready","legacy_apply_partial",
            "current_apply_partial","current_rollback_in_progress","current_apply_complete",
            "current_rollback_complete","invalid_checkpoint"})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"checkpoint.json"
            self.assertEqual(tool.classify_checkpoint(path,"dry_run",False)[0],"new_dry_run")
            cases = (("dry_run_ready","dry_run",True,"dry_run_ready"),
                     ("apply_partial","verify",False,"current_apply_partial"),
                     ("rollback_in_progress","rollback",False,"current_rollback_in_progress"),
                     ("apply_complete","verify",False,"current_apply_complete"),
                     ("rollback_complete","rollback",False,"current_rollback_complete"))
            for state, mode, resume, expected in cases:
                checkpoint, _ = self.canonical_fixture(state=state)
                tool.atomic_json(path, checkpoint)
                with self.subTest(state=state): self.assertEqual(tool.classify_checkpoint(path,mode,resume)[0],expected)
            checkpoint["schema_version"] = "unexpected"; tool.atomic_json(path, checkpoint)
            with self.assertRaisesRegex(tool.ConflictError,"invalid_checkpoint"):
                tool.classify_checkpoint(path,"rollback",False)

    def test_34_current_partial_plan_contract_and_tampering_are_validated(self):
        checkpoint, data = self.canonical_fixture()
        with mock.patch.object(tool,"tool_head",return_value="head"):
            self.assertIs(tool.validate_current_checkpoint(checkpoint,data,"https://api.example",20),checkpoint)
            completed_by_key, pending, following = tool.checkpoint_progress(checkpoint)
            self.assertEqual((len(completed_by_key),len(pending),following["operation_order"]),(65,1132,66))
            self.assertEqual(tool.operation_counts(checkpoint["planned_operations"]),tool.REQUIRED_OPERATION_COUNTS)
            mutations = (
                lambda cp: cp["planned_operations"].pop(),
                lambda cp: cp["planned_operations"].append(dict(cp["planned_operations"][-1],operation_order=1198)),
                lambda cp: cp["completed_operations"].pop(2),
                lambda cp: cp["completed_operations"][0].update(resource_id=""),
                lambda cp: cp["planned_operations"][1].update(depends_on_operation=1,depends_on_operation_key="bad"),
            )
            for mutate in mutations:
                altered = json.loads(json.dumps(checkpoint)); mutate(altered)
                with self.subTest(mutate=mutate), self.assertRaises(tool.ConflictError):
                    tool.validate_current_checkpoint(altered,data,"https://api.example",20)

    def test_35_current_partial_verify_and_rollback_reuse_persisted_plan(self):
        for kind, mode, state in (("current_apply_partial","verify","apply_partial"),
                                  ("current_rollback_in_progress","rollback","rollback_in_progress")):
            checkpoint, data = self.canonical_fixture(state=state)
            deleted = []
            client = type("Client",(),{"delete":lambda self,path: deleted.append(path)})()
            base_result = {"operations":checkpoint["planned_operations"],"resources_created":{},
                           "external_effects":{},"errors":[],"followups":[],"resource_warnings":[],
                           "products":[{"metric_model":f"M{i:02}"} for i in range(36)]}
            with tempfile.TemporaryDirectory() as temp, mock.patch.multiple(tool,
                    validate_paths=mock.DEFAULT,validate_inputs=mock.DEFAULT,normalize_origin=mock.DEFAULT,
                    batch_ranges=mock.DEFAULT,classify_checkpoint=mock.DEFAULT,validate_current_checkpoint=mock.DEFAULT,
                    snapshot=mock.DEFAULT,resolve_taxonomy=mock.DEFAULT,classify_products=mock.DEFAULT,
                    resource_view=mock.DEFAULT,build_operations=mock.DEFAULT,remote_fingerprint=mock.DEFAULT,
                    tool_head=mock.DEFAULT,validate_operation_dependencies=mock.DEFAULT,checkpoint_contract=mock.DEFAULT,
                    _base_result=mock.DEFAULT,validate_completed_remote_resources=mock.DEFAULT,
                    partial_resume_fingerprint=mock.DEFAULT,product_statuses=mock.DEFAULT,
                    validate_checkpoint_static=mock.DEFAULT,atomic_json=mock.DEFAULT,write_outputs=mock.DEFAULT) as mocks:
                mocks["validate_inputs"].return_value=data; mocks["normalize_origin"].return_value="https://api.example"
                mocks["batch_ranges"].return_value=[]; mocks["classify_checkpoint"].return_value=(kind,checkpoint,b"same")
                mocks["snapshot"].return_value={}; mocks["resolve_taxonomy"].return_value=({}, {}, {})
                mocks["classify_products"].return_value=[{"row":{"metric_model":f"M{i:02}"},"status":"create_candidate"} for i in range(36)]
                mocks["resource_view"].return_value=checkpoint.setdefault("resources_preexisting",{})
                mocks["remote_fingerprint"].return_value="remote"; mocks["tool_head"].return_value="head"
                mocks["_base_result"].return_value=base_result; mocks["partial_resume_fingerprint"].return_value="partial"
                mocks["product_statuses"].return_value={f"M{i:02}":("in_progress" if i == 0 else "not_started") for i in range(36)}
                code=tool.run(Path(temp),Path(temp),Path(temp),Path(temp),"https://api.example",mode,"token",
                    checkpoint=Path(temp)/"cp",client_factory=lambda *args:client)
            self.assertEqual(code,0); mocks["build_operations"].assert_not_called()
            if mode == "verify":
                self.assertEqual(base_result["verdict"],"PARTIAL_RESUME_READY")
                self.assertEqual(base_result["operation_status_counts"],{"completed":65,"failed":0,"planned":1132,"total":1197})
                mocks["atomic_json"].assert_not_called()
            else:
                self.assertTrue(deleted[0].endswith("/1065"))
                self.assertEqual(len(deleted),65)

    def test_36_migrated_checkpoint_can_become_partial_again_without_losing_its_plan(self):
        legacy, data = self.canonical_fixture()
        legacy.update(version=tool.LEGACY_VERSION,schema_version=tool.LEGACY_SCHEMA_VERSION,
                      tool_head=tool.LEGACY_TOOL_HEAD)
        original_keys = [operation["operation_key"] for operation in legacy["planned_operations"]]
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(tool,"tool_head",return_value="head"):
            path=Path(temp)/"checkpoint.json"
            migrated=tool.migrate_legacy_checkpoint(path,legacy,"f"*64)
            for operation in migrated["planned_operations"][65:68]:
                tool._record_mutation(path,migrated,operation,operation["resource_type"]+"s",2000+operation["operation_order"])
            migrated["state"]="apply_partial"
            statuses=tool.product_statuses(migrated["planned_operations"],migrated["completed_operations"])
            for item in migrated["products"].values(): item["status"]=statuses[item["metric_model"]]
            tool.atomic_json(path,migrated)
            validated=tool.validate_current_checkpoint(migrated,data,"https://api.example",20)
        completed,pending,next_operation=tool.checkpoint_progress(validated)
        self.assertEqual([operation["operation_key"] for operation in validated["planned_operations"]],original_keys)
        self.assertEqual((len(completed),len(pending),next_operation["operation_order"]),(68,1129,69))
        self.assertEqual(validated["migration"]["legacy_completed_operations"],65)

    def test_37_product_progress_is_derived_by_key_as_two_complete_one_in_progress(self):
        planned=[]
        for index in range(36):
            count=2 if index < 3 else 1
            planned.extend({"operation_key":f"{index}-{part}","metric_model":f"M{index:02}"}
                           for part in range(count))
        completed=[{"operation_key":operation["operation_key"]} for operation in planned[:5]]
        statuses=tool.product_statuses(planned,completed)
        self.assertEqual({name:list(statuses.values()).count(name) for name in
            ("completed","in_progress","not_started")},{"completed":2,"in_progress":1,"not_started":33})


if __name__ == "__main__": unittest.main()
