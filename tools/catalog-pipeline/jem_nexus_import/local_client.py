"""The sole network boundary: bounded JSON GETs to an explicit loopback port."""
from __future__ import annotations
import json, os
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

READ_PATHS={"categories":"/api/categories","brands":"/api/brands","suppliers":"/api/suppliers","products":"/api/products","product_images":"/api/product-images","product_specs":"/api/product-specs","technical_sheets":"/api/technical-sheets/"}
TOKEN_ENV="JEM_NEXUS_LOCAL_READ_TOKEN"
class LocalReadError(ValueError):
    def __init__(self,code,detail): self.code=code; super().__init__(detail)
class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def validate_base_url(value):
    parsed=urlsplit(value)
    if parsed.scheme not in ("http","https") or parsed.hostname not in ("localhost","127.0.0.1","::1") or parsed.port is None or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise LocalReadError("UNSAFE_LOCAL_TARGET","an exact loopback URL with explicit port is required")
    return value.rstrip("/")

class LocalJemJsonReader:
    def __init__(self,base_url,transport=None,requires_auth=True,timeout=10,max_bytes=4_000_000):
        self.base_url=validate_base_url(base_url); self.transport=transport or self._get; self.timeout=timeout; self.max_bytes=max_bytes
        self.token=os.environ.get(TOKEN_ENV) if requires_auth else None
        if requires_auth and not self.token: raise LocalReadError("LOCAL_TOKEN_MISSING",TOKEN_ENV+" is required")
    def read_collection(self,name):
        if name not in READ_PATHS: raise LocalReadError("UNSAFE_READ_QUERY","unknown read endpoint")
        # The inspected list endpoints are currently unpaginated; no query is invented.
        url=self.base_url+READ_PATHS[name]
        status,mime,body=self.transport(url,{"Authorization":"Bearer "+self.token} if self.token else {},self.timeout,self.max_bytes)
        if status!=200: raise LocalReadError("READ_STATUS",str(status))
        if "json" not in mime.lower(): raise LocalReadError("READ_MIME","JSON response required")
        if len(body)>self.max_bytes: raise LocalReadError("READ_TOO_LARGE","response limit exceeded")
        try: return json.loads(body.decode("utf-8",errors="strict"))
        except (UnicodeDecodeError,json.JSONDecodeError) as error: raise LocalReadError("READ_INVALID_JSON","invalid JSON response") from error
    @staticmethod
    def _get(url,headers,timeout,max_bytes):
        response=build_opener(_NoRedirect).open(Request(url,headers=headers,method="GET"),timeout=timeout)
        return response.status,response.headers.get_content_type(),response.read(max_bytes+1)
