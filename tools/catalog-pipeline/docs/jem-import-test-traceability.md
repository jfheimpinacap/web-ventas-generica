# Trazabilidad funcional Prompt 284/284B

Diagnóstico previo: 12 requisitos estaban cubiertos, 13 parciales y 55 ausentes. La causa principal
era que `plan` devolvía siempre 3, no existían reconciliadores y las operaciones solo podían ser
entregadas por el caller. La corrección conecta paquete, snapshot, reconciliación, grafo y simulación.
`covered` significa que el método indicado construye una variante y atraviesa el símbolo productivo;
varias filas comparten un método solamente cuando este contiene assertions diferenciadas.

|#|test / variante|símbolo productivo|resultado exacto|etapa|cobertura|
|-:|---|---|---|---|---|
|1|case_a_real_package / ZIP builder|build_package, create_plan|plan construido|package|covered|
|2|package_requires_zip / JSON suelto|read_verified_package|INVALID_PACKAGE_INPUT|package|covered|
|3|package_requires_zip / directorio|read_verified_package|INVALID_PACKAGE_INPUT|package|covered|
|4|receipt_and_package_corruption / bytes|verify_package, read_verified_package|INVALID_PACKAGE|package|covered|
|5|receipt_and_package_corruption / size receipt|verify_package|INVALID_PACKAGE|package|covered|
|6|receipt_and_package_corruption / fingerprint|verify_package|INVALID_PACKAGE|package|covered|
|7|receipt_and_package_corruption / manifest|verify_package|INVALID_PACKAGE|package|covered|
|8|case builder blocked|build_package|PLAN_BLOCKED|package|covered|
|9|case builder empty|build_package|PLAN_BLOCKED|package|covered|
|10|corruption / entry list|verify_package|INVALID_PACKAGE|package|covered|
|11|case A / in-memory ZipFile|read_verified_package|entries bytes|package|covered|
|12|package_requires / callback changes source|read_verified_package|PACKAGE_CHANGED|TOCTOU|covered|
|13|complete_snapshot_validates|validate_snapshot|accepted|snapshot|covered|
|14|order_and_capture_time|semantic_fingerprint|equal|snapshot|covered|
|15|order_and_capture_time / captured_at|semantic_fingerprint|equal|snapshot|covered|
|16|missing_endpoint_and_truncated / pop|validate_snapshot|SnapshotError|snapshot|covered|
|17|missing_endpoint_and_truncated / pages|validate_snapshot|PAGINATION_INCOMPLETE|snapshot|covered|
|18|duplicate_and_casefold / duplicate id|validate_snapshot|DUPLICATE_ID|snapshot|covered|
|19|orphan_relations|validate_snapshot|ORPHAN_RELATION|snapshot|covered|
|20|non_json_and_oversize / two branches|read_collection|READ_MIME/READ_TOO_LARGE|GET|covered|
|21|exact_loopback / localhost|validate_base_url|accepted|GET|covered|
|22|exact_loopback / 127.0.0.1|validate_base_url|accepted|GET|covered|
|23|exact_loopback / ::1|validate_base_url|accepted|GET|covered|
|24|unsafe_targets / production|validate_base_url|UNSAFE_LOCAL_TARGET|GET|covered|
|25|unsafe_targets / private IP|validate_base_url|UNSAFE_LOCAL_TARGET|GET|covered|
|26|unsafe_targets / credentials/query/fragment|validate_base_url|UNSAFE_LOCAL_TARGET|GET|covered|
|27|fake transport redirect status|read_collection|READ_STATUS|GET|covered|
|28|fake_transport_observes_get|read_collection|one fixed-path GET|GET|covered|
|29|token_absence|LocalJemJsonReader|LOCAL_TOKEN_MISSING before call|GET|covered|
|30|token_absence / message|LocalJemJsonReader|no Bearer/token value|GET|covered|
|31|field_evidence|project_candidate|pointer/target/provenance|projection|covered|
|32|safe_commercial_defaults|project_candidate|null/false and blocker|projection|covered|
|33|case A source identity|build_operations|source ID absent payload|projection|covered|
|34|lift_height_remains_spec|project_candidate|ProductSpec, no working_height|projection|covered|
|35|unknown_enum|project_candidate|UNKNOWN_ENUM|projection|covered|
|36|field_evidence unknown|project_candidate|review_required|projection|covered|
|37|case A primary/secondary|reconcile_assets|two image operations|assets|covered|
|38|case A sheet|build_operations|technical_sheet operation|assets|covered|
|39|case A additional|build_operations|retained_not_imported|assets|covered|
|40|case A filename|reconcile_assets|metadata only|assets|covered|
|41|ambiguous_and_parent|reconcile_category|exact/create/block|reconcile|covered|
|42|ambiguous_and_parent supplier|reconcile_supplier|optional/exact/block|reconcile|covered|
|43|root_maquinarias_resolves|simulate|dry_run_ready|bindings|covered|
|44|missing_root|simulate|MISSING_BINDING|bindings|covered|
|45|missing_root|simulate|typed error, no KeyError|bindings|covered|
|46|case A bindings|build_operations|external/produced scopes|bindings|covered|
|47|duplicate_external_and_produced|BindingResolver|DUPLICATE_BINDING|bindings|covered|
|48|type_mismatch|resolve|MISSING_BINDING|bindings|covered|
|49|cycle_and_missing_dependency / missing|topological|DEPENDENCY_CYCLE_OR_MISSING|graph|covered|
|50|cycle_and_missing_dependency / cycle|topological|DEPENDENCY_CYCLE_OR_MISSING|graph|covered|
|51|stable_topology|topological|stable dependency order|graph|covered|
|52|operation_ids|operation|same deterministic ID|graph|covered|
|53|case A|build_operations, topological|category/brand before product|graph|covered|
|54|stable_topology|topological|product before child assets|graph|covered|
|55|symbolic_results|simulate|`<symbolic:...>`|dry-run|covered|
|56|root resolves / all refs|simulate|dry_run_ready only resolved|dry-run|covered|
|57|missing_root|simulate|state not partial|dry-run|covered|
|58|case A root-only snapshot|build_operations|create category/brand/product|reconcile|covered|
|59|existing_entities|reconcile_category/reconcile_brand|reuse_exact|reconcile|covered|
|60|existing_entities / exact product|reconcile_product|noop_exact|reconcile|covered|
|61|existing_entities / changed name|reconcile_product|PRODUCT_DIVERGED|reconcile|covered|
|62|ambiguous natural candidates|reconcile_product|AMBIGUOUS_NATURAL_KEY|reconcile|covered|
|63|duplicate_and_casefold|validate_snapshot|IDENTITY_COLLISION|snapshot|covered|
|64|semantic_snapshot_change|semantic_fingerprint|different|fingerprint|covered|
|65|operation_ids and canonical output|operation/canonical_bytes|identical bytes|fingerprint|covered|
|66|output_atomic_idempotent|write_output_set|same bytes|outputs|covered|
|67|output_atomic_idempotent / conflict|write_output_set|no tmp, conflict|outputs|covered|
|68|all_dry_run_guarantees|simulate|0/0|dry-run|covered|
|69|fake_transport_observes_get|read_collection|no method parameter/mutation|GET|covered|
|70|cli_surface|parser|three commands|CLI|covered|
|71|cli_surface|parser|unsafe options absent|CLI|covered|
|72|CLI main branch tests|main|0/2/3/4/5|CLI|covered|
|73|seven_import_schemas|validate|seven accepted/rejected mutations|schemas|covered|
|74|architecture boundary test|module sources/import graph|no EP/GAM imports|architecture|covered|
|75|architecture boundary test|module sources|no LGMG/temp access|architecture|covered|
|76|all_dry_run_guarantees|simulate|authorization remains false|dry-run|covered|
|77|case A additional unsupported|build_operations|retained in plan|assets|covered|
|78|case A excluded count|create_plan|plan allowed|package|covered|
|79|builder blocked variant|build_package/create_plan|blocked|package|covered|
|80|all_dry_run_guarantees|simulate|zero network/mutation/auth|manifest|covered|
|81|reader_requires_transport|LocalJemJsonReader|LOCAL_TRANSPORT_MISSING|GET core|covered|
|82|transport interface and request|get_json_bytes|four arguments, method GET|GET boundary|covered|
|83|redirects/proxies disabled|get_json_bytes|NoRedirect and empty ProxyHandler|GET boundary|covered|
|84|direct unsafe targets|get_json_bytes|UNSAFE_LOCAL_TARGET before opener|GET boundary|covered|
|85|three direct loopbacks|get_json_bytes|localhost/IPv4/IPv6 accepted with fake opener|GET boundary|covered|
|86|normal CLI composition|main|dedicated transport injected|CLI|covered|
|87|unique boundary|module sources/import graph|urllib only in explicit transport|architecture|covered|
