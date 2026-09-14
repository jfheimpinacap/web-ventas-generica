"""The sole concrete bounded local binary GET boundary."""
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

class BinaryTransportError(ValueError): pass
class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def _validate(base,path):
    parsed=urlsplit(base)
    if parsed.scheme!="http" or parsed.hostname not in ("localhost","127.0.0.1","::1") or parsed.port is None or parsed.username or parsed.password or parsed.path not in ("","/") or parsed.query or parsed.fragment: raise BinaryTransportError("UNSAFE_LOCAL_TARGET")
    if not path.startswith("/") or path.startswith("//") or urlsplit(path).query or urlsplit(path).fragment or "\\" in path: raise BinaryTransportError("UNSAFE_LOCAL_TARGET")
    target=urlsplit(base.rstrip("/")+path)
    if (target.scheme,target.hostname,target.port)!=(parsed.scheme,parsed.hostname,parsed.port): raise BinaryTransportError("UNSAFE_LOCAL_TARGET")

class LocalBinaryTransport:
    def __init__(self,token,opener_factory=build_opener):
        if not token: raise BinaryTransportError("CAPTURE_TOKEN_MISSING")
        self._token=token; self._opener=opener_factory(ProxyHandler({}),_NoRedirect)
    def __call__(self,base_url,root_relative_path,headers,timeout,limit):
        _validate(base_url,root_relative_path)
        request=Request(base_url.rstrip("/")+root_relative_path,headers={**headers,"Authorization":"Bearer "+self._token},method="GET")
        with self._opener.open(request,timeout=timeout) as response:
            location=response.headers.get("Location")
            if location is not None or 300<=response.status<400: raise BinaryTransportError("BINARY_READ_REDIRECT")
            return {"status":response.status,"mime":response.headers.get("Content-Type"),"content_length":response.headers.get("Content-Length"),"body":response.read(limit+1)}
