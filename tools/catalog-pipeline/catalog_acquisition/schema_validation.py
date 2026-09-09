"""Fail-closed validator for the documented JSON Schema subset used by v1."""
from __future__ import annotations
from datetime import datetime
import json, math, re
from pathlib import Path, PurePosixPath
from .errors import PipelineError

ANNOTATION_KEYWORDS=frozenset({"$schema","$id","$defs","title","description","schema_version"})
VALIDATION_KEYWORDS=frozenset({"$ref","type","properties","required","additionalProperties","enum","const","items","minItems","uniqueItems","minLength","maxLength","minimum","maximum","pattern","format"})
SUPPORTED_KEYWORDS=ANNOTATION_KEYWORDS|VALIDATION_KEYWORDS

class SchemaValidationError(PipelineError):
    code="SCHEMA_INVALID"
    def __init__(self, message: str, *, schema: str, instance_path: str, keyword: str) -> None:
        super().__init__(message, schema=schema, instance_path=instance_path, keyword=keyword)
        self.schema=schema; self.instance_path=instance_path; self.keyword=keyword

def _fail(message: str, schema: Path, path: str, keyword: str) -> None:
    raise SchemaValidationError(message, schema=schema.name, instance_path=path, keyword=keyword)

def _schema_root(path: Path) -> Path: return path.parent.resolve()

def validate_schema_keywords(schema_path: Path) -> None:
    root=json.loads(schema_path.read_text(encoding="utf-8"))
    def scan(node: object, path: str) -> None:
        if isinstance(node,dict):
            for key,value in node.items():
                # Property names and $defs member names are data, not schema keywords.
                if path.endswith(".properties") or path.endswith(".$defs"): scan(value,f"{path}.{key}"); continue
                if key not in SUPPORTED_KEYWORDS: _fail(f"Unsupported schema keyword: {key}",schema_path,path,key)
                scan(value,f"{path}.{key}")
        elif isinstance(node,list):
            for index,value in enumerate(node): scan(value,f"{path}[{index}]")
    scan(root,"$")

def validate(instance: object, schema_path: Path) -> None:
    schema_path=schema_path.resolve(); allowed_root=_schema_root(schema_path)
    validate_schema_keywords(schema_path)
    documents: dict[Path,dict[str,object]]={}
    active_refs: set[tuple[Path,str]] = set()
    def load(path: Path) -> dict[str,object]:
        resolved=path.resolve()
        if resolved.parent != allowed_root: _fail("Schema reference escapes v1 root",schema_path,"$","$ref")
        if not resolved.is_file(): _fail("Referenced schema does not exist",schema_path,"$","$ref")
        if resolved not in documents:
            documents[resolved]=json.loads(resolved.read_text(encoding="utf-8")); validate_schema_keywords(resolved)
        return documents[resolved]
    def resolve(ref: str, current: Path, instance_path: str) -> tuple[dict[str,object],Path]:
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:",ref) or ref.startswith(("/","\\")):
            _fail("Absolute or remote schema references are forbidden",current,instance_path,"$ref")
        filename,separator,fragment=ref.partition("#")
        pure=PurePosixPath(filename)
        if ".." in pure.parts: _fail("Schema reference traversal is forbidden",current,instance_path,"$ref")
        target=current if not filename else current.parent.joinpath(*pure.parts)
        document=load(target); node: object=document
        if separator and fragment:
            if not fragment.startswith("/"): _fail("Only JSON Pointer fragments are supported",current,instance_path,"$ref")
            for token in fragment[1:].split("/"):
                token=token.replace("~1","/").replace("~0","~")
                if not isinstance(node,dict) or token not in node: _fail("Schema fragment does not exist",current,instance_path,"$ref")
                node=node[token]
        if not isinstance(node,dict): _fail("Schema reference target is not a schema object",current,instance_path,"$ref")
        return node,target.resolve()
    def walk(value: object, schema: dict[str,object], path: str, current: Path) -> None:
        if "$ref" in schema:
            marker=(current,str(schema["$ref"]))
            if marker in active_refs: _fail("Cyclic schema reference is unsupported",current,path,"$ref")
            active_refs.add(marker)
            try:
                referenced,target=resolve(str(schema["$ref"]),current,path); walk(value,referenced,path,target)
            finally: active_refs.remove(marker)
            return
        if "const" in schema and value != schema["const"]: _fail("Value differs from required constant",current,path,"const")
        if "enum" in schema and value not in schema["enum"]: _fail("Unknown enum value",current,path,"enum")
        expected=schema.get("type")
        actual=("null" if value is None else "boolean" if isinstance(value,bool) else "integer" if isinstance(value,int) else "number" if isinstance(value,float) else "string" if isinstance(value,str) else "array" if isinstance(value,list) else "object" if isinstance(value,dict) else "unknown")
        if expected:
            allowed=expected if isinstance(expected,list) else [expected]
            if actual not in allowed and not (actual=="integer" and "number" in allowed): _fail(f"Expected {allowed}, got {actual}",current,path,"type")
        if isinstance(value,dict):
            props=schema.get("properties",{}); missing=[name for name in schema.get("required",[]) if name not in value]
            if missing: _fail(f"Missing required properties: {missing}",current,path,"required")
            additional=schema.get("additionalProperties",True); extra=set(value)-set(props)
            if additional is False and extra: _fail(f"Undeclared properties: {sorted(extra)}",current,path,"additionalProperties")
            for key,item in value.items():
                if key in props: walk(item,props[key],f"{path}.{key}",current)
                elif isinstance(additional,dict): walk(item,additional,f"{path}.{key}",current)
        if isinstance(value,list):
            if len(value)<schema.get("minItems",0): _fail("Array has too few items",current,path,"minItems")
            if schema.get("uniqueItems"):
                encoded=[json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(",",":")) for item in value]
                if len(encoded)!=len(set(encoded)): _fail("Array items are not unique",current,path,"uniqueItems")
            if "items" in schema:
                for index,item in enumerate(value): walk(item,schema["items"],f"{path}[{index}]",current)
        if isinstance(value,str):
            if len(value)<schema.get("minLength",0): _fail("String is too short",current,path,"minLength")
            if "maxLength" in schema and len(value)>schema["maxLength"]: _fail("String is too long",current,path,"maxLength")
            if "pattern" in schema and not re.search(schema["pattern"],value): _fail("String does not match pattern",current,path,"pattern")
            if schema.get("format")=="date-time":
                if not re.search(r"T.*(?:Z|[+-][0-9]{2}:[0-9]{2})$",value): _fail("Invalid date-time",current,path,"format")
                try: datetime.fromisoformat(value.replace("Z","+00:00"))
                except ValueError: _fail("Invalid date-time",current,path,"format")
            elif "format" in schema: _fail("Unsupported format",current,path,"format")
        if actual in {"integer","number"} and not isinstance(value,bool):
            if isinstance(value,float) and not math.isfinite(value): _fail("Number must be finite",current,path,"type")
            if "minimum" in schema and value<schema["minimum"]: _fail("Number is below minimum",current,path,"minimum")
            if "maximum" in schema and value>schema["maximum"]: _fail("Number is above maximum",current,path,"maximum")
    root=load(schema_path); walk(instance,root,"$",schema_path)
