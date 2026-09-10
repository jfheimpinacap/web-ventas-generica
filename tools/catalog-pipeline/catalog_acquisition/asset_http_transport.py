"""The only network-capable module for asset bytes: one bounded GET, no redirects."""
from __future__ import annotations
from dataclasses import dataclass
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

ALLOWED_RESPONSE_HEADERS=frozenset({"content-type","content-length","content-range","etag","last-modified","location","accept-ranges","content-encoding"})
FORBIDDEN_REQUEST_HEADERS=frozenset({"authorization","cookie","proxy-authorization","x-api-key"})

class AssetTransportError(RuntimeError):
    def __init__(self,state): super().__init__(state); self.state=state
class AssetLimitExceeded(AssetTransportError): pass
class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

@dataclass(frozen=True)
class AssetResponse:
    status:int; headers:dict[str,str]; chunks:tuple[bytes,...]

class SafeAssetHttpTransport:
    def __init__(self,*,user_agent,timeout,max_header_bytes,max_chunk_bytes,opener=None):
        if not user_agent or min(timeout,max_header_bytes,max_chunk_bytes)<=0: raise ValueError("invalid transport policy")
        self.user_agent=user_agent; self.timeout=timeout; self.max_header_bytes=max_header_bytes; self.max_chunk_bytes=max_chunk_bytes
        context=ssl.create_default_context()
        self._opener=opener or build_opener(ProxyHandler({}),_NoRedirect(),HTTPSHandler(context=context))
    def request(self,method,url,headers=None,*,max_body_bytes):
        if method!="GET": raise AssetTransportError("method_blocked")
        supplied={k.casefold():v for k,v in (headers or {}).items()}
        if set(supplied)&FORBIDDEN_REQUEST_HEADERS: raise AssetTransportError("sensitive_header_blocked")
        allowed={"range","if-range"}
        if set(supplied)-allowed: raise AssetTransportError("request_header_blocked")
        request_headers={"User-Agent":self.user_agent,"Accept-Encoding":"identity",**supplied}
        try: raw=self._opener.open(Request(url,headers=request_headers,method="GET"),timeout=self.timeout)
        except HTTPError as exc: raw=exc
        except (URLError,TimeoutError,OSError) as exc: raise AssetTransportError("transport_failed") from exc
        safe={k.casefold():v for k,v in raw.headers.items() if k.casefold() in ALLOWED_RESPONSE_HEADERS}
        if sum(len(k)+len(v) for k,v in safe.items())>self.max_header_bytes: raise AssetLimitExceeded("headers_too_large")
        declared=safe.get("content-length")
        if declared and (not declared.isdigit() or int(declared)>max_body_bytes):
            raise AssetLimitExceeded("content_length_blocked")
        chunks=[]; total=0
        while True:
            try: chunk=raw.read(self.max_chunk_bytes)
            except (OSError,TimeoutError) as exc: raise AssetTransportError("stream_interrupted") from exc
            if not chunk: break
            total+=len(chunk)
            if total>max_body_bytes: raise AssetLimitExceeded("body_too_large")
            chunks.append(chunk)
        return AssetResponse(getattr(raw,"status",getattr(raw,"code",0)),safe,tuple(chunks))
