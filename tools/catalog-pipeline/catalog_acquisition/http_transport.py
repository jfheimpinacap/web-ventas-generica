"""Sequential standard-library HTTP transport; it never interprets catalog HTML."""
from __future__ import annotations
import gzip, io, time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .discovery import REQUEST_POLICY_VERSION, SourceDefinition
from .errors import PipelineError
from .urls import canonicalize

ALLOWED_MIME=frozenset({"text/html","application/xhtml+xml","text/plain","application/json","application/ld+json","application/xml","text/xml"})
TRANSIENT=frozenset({408,429,500,502,503,504})
class TransportError(PipelineError): code="DISCOVERY_TRANSPORT_ERROR"
class ResponseTooLarge(TransportError): code="RESPONSE_TOO_LARGE"
class ContentTypeBlocked(TransportError): code="CONTENT_TYPE_BLOCKED"

@dataclass(frozen=True)
class HttpPolicy:
    user_agent: str="JEM-Catalog-Discovery/1.0 (+auditable-offline-replay)"
    timeout: float=20.0; min_host_pause: float=1.0; retries: int=2
    max_redirects: int=5; max_body: int=5*1024*1024; max_retry_after: int=30

@dataclass(frozen=True)
class HttpResponse:
    requested_url: str; final_url: str; status: int; content_type: str
    encoding: str | None; body: bytes; headers: dict[str,str]; fetched_at: str
    redirects: tuple[str,...]; network_status: int

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

class SafeHttpTransport:
    def __init__(self, policy: HttpPolicy=HttpPolicy(), *, opener=None, sleeper=time.sleep, monotonic=time.monotonic):
        if policy.max_body<=0: raise ValueError("body limit must be positive")
        self.policy=policy; self.opener=opener or build_opener(_NoRedirect); self.sleeper=sleeper; self.monotonic=monotonic; self._last={}
    def fetch(self,url: str,source: SourceDefinition,*,method: str="GET",extra_headers: dict[str,str]|None=None)->HttpResponse:
        if method not in ("GET","HEAD"): raise TransportError("only GET and HEAD are allowed")
        requested=canonicalize(url,base_url=source.start_url,source=source,require_scope=False).canonical
        current=requested; redirects=[]
        for redirect_count in range(self.policy.max_redirects+1):
            response=self._attempt(current,source,method,extra_headers or {})
            if response.status not in (301,302,303,307,308):
                return HttpResponse(requested,current,response.status,response.content_type,response.encoding,response.body,response.headers,response.fetched_at,tuple(redirects),response.status)
            location=response.headers.get("location")
            if not location: raise TransportError("redirect has no Location")
            if redirect_count>=self.policy.max_redirects: raise TransportError("maximum redirects exceeded")
            redirected=canonicalize(location,base_url=current,source=source,require_scope=True)
            if urlsplit(requested).path == "/robots.txt" and urlsplit(redirected.canonical).path != "/robots.txt":
                raise TransportError("robots redirect may not become a catalog request")
            current=redirected.canonical; redirects.append(current)
        raise TransportError("maximum redirects exceeded")
    def _attempt(self,url,source,method,extra):
        host=canonicalize(url,base_url=url,source=source,require_scope=False).canonical.split("/",3)[2]
        elapsed=self.monotonic()-self._last.get(host,-10**9)
        if elapsed<self.policy.min_host_pause: self.sleeper(self.policy.min_host_pause-elapsed)
        headers={"User-Agent":self.policy.user_agent,"Accept-Encoding":"identity","Accept":"text/html, application/xhtml+xml, application/json, text/plain;q=0.8"}
        headers.update(extra)
        for attempt in range(self.policy.retries+1):
            self._last[host]=self.monotonic()
            try:
                raw=self.opener.open(Request(url,method=method,headers=headers),timeout=self.policy.timeout)
                return self._read(raw,url,method)
            except HTTPError as exc:
                if exc.code in (301,302,303,307,308): return self._read(exc,url,method)
                if exc.code not in TRANSIENT or attempt==self.policy.retries: return self._read(exc,url,method)
                self.sleeper(_retry_after(exc.headers,self.policy.max_retry_after))
            except (TimeoutError,URLError) as exc:
                if attempt==self.policy.retries: raise TransportError("transient connection failure",url=sanitize_url(url)) from exc
        raise AssertionError("unreachable")
    def _read(self,raw,url,method):
        status=getattr(raw,"status",getattr(raw,"code",0)); headers=_safe_headers(raw.headers)
        mime=raw.headers.get_content_type() if hasattr(raw.headers,"get_content_type") else raw.headers.get("Content-Type","application/octet-stream").split(";",1)[0]
        if method!="HEAD" and status not in (204,304) and mime.lower() not in ALLOWED_MIME: raise ContentTypeBlocked("response MIME is not allowed",mime=mime)
        data=b"" if method=="HEAD" else _bounded_read(raw,self.policy.max_body)
        encoding=raw.headers.get_content_charset() if hasattr(raw.headers,"get_content_charset") else None
        if raw.headers.get("Content-Encoding","").casefold()=="gzip": data=_gunzip_limited(data,self.policy.max_body)
        return HttpResponse(url,url,status,mime.lower(),encoding,data,headers,datetime.now(timezone.utc).isoformat(),(),status)

def _bounded_read(stream,limit):
    chunks=[]; size=0
    while True:
        chunk=stream.read(min(65536,limit-size+1))
        if not chunk: break
        size+=len(chunk)
        if size>limit: raise ResponseTooLarge("response exceeds configured maximum",limit=limit)
        chunks.append(chunk)
    return b"".join(chunks)
def _gunzip_limited(data,limit): return _bounded_read(gzip.GzipFile(fileobj=io.BytesIO(data)),limit)
def _retry_after(headers: Message,max_value:int)->int:
    try: value=int(headers.get("Retry-After","1"))
    except (TypeError,ValueError): return 1
    return max(0,min(value,max_value))
def _safe_headers(headers)->dict[str,str]:
    allowed={"content-type","content-encoding","etag","last-modified","location","retry-after","content-length"}
    return {k.casefold():v for k,v in headers.items() if k.casefold() in allowed}
def sanitize_url(url):
    from urllib.parse import urlsplit,urlunsplit
    p=urlsplit(url); return urlunsplit((p.scheme,p.hostname or "",p.path,"<redacted>" if p.query else "",""))
