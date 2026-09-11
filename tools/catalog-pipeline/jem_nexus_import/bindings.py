"""Namespace-aware future binding resolution; contains no API behavior."""
from dataclasses import dataclass

@dataclass(frozen=True)
class MissingBindingError(Exception):
    code: str; namespace: str; key: str; binding_type: str
    def as_dict(self): return {"code": self.code, "namespace": self.namespace, "key": self.key, "binding_type": self.binding_type, "resolution_status": "missing"}

class BindingResolver:
    def __init__(self, external_bindings=(), produced_bindings=()):
        self._values = {"external": {}, "produced": {}}
        seen=set()
        for scope, values in (("external", external_bindings), ("produced", produced_bindings)):
            for item in values:
                key=(item["namespace"], item["key"], item["binding_type"])
                if key in seen: raise ValueError("DUPLICATE_BINDING:"+":".join(key))
                seen.add(key); self._values[scope][key]=item.get("value")
    def resolve(self, reference):
        scope = reference["scope"]; key = (reference["namespace"], reference["key"], reference["binding_type"])
        value = self._values.get(scope, {}).get(key)
        if value is None: raise MissingBindingError("MISSING_BINDING", *key)
        return value

    def produce(self, reference, value):
        key=(reference["namespace"],reference["key"],reference["binding_type"])
        if key in self._values["external"] or self._values["produced"].get(key) is not None:
            raise ValueError("DUPLICATE_BINDING:"+":".join(key))
        self._values["produced"][key]=value
