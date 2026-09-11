"""Approved-package import contracts; no acquisition or transport dependencies."""
from .bindings import BindingResolver, MissingBindingError
from .projection import build_safe_product_payload, project_candidate
__all__ = ["BindingResolver", "MissingBindingError", "build_safe_product_payload", "project_candidate"]
