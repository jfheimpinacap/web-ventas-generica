"""Stable, actionable errors for fail-closed pipeline behavior."""

class PipelineError(Exception):
    code = "PIPELINE_ERROR"

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.context = context

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "context": self.context}

class IdentityCollisionError(PipelineError): code = "IDENTITY_COLLISION"
class PathCollisionError(PipelineError): code = "PATH_COLLISION"
class UnsafePathError(PipelineError): code = "UNSAFE_PATH"
class ImmutableEvidenceError(PipelineError): code = "RAW_EVIDENCE_IMMUTABLE"
class HashMismatchError(PipelineError): code = "HASH_MISMATCH"
