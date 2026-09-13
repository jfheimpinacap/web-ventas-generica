"""Concrete POST-only boundary for an explicitly authorized loopback API."""
import json,os
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,ProxyHandler,Request,build_opener
from catalog_pipeline_common.serialization import canonical_bytes,content_fingerprint
from jem_nexus_import.authorization import validate_authorization
from jem_nexus_import.execution import ALLOWED_ENDPOINTS
from jem_nexus_import.local_client import validate_base_url

TOKEN_ENV="JEM_NEXUS_LOCAL_MUTATION_TOKEN"
MAX_RESPONSE_BYTES=1024*1024
class MutationTransportError(ValueError): pass
class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def target_fingerprint(base_url):
    validate_base_url(base_url); parsed=urlsplit(base_url)
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password: raise MutationTransportError("UNSAFE_LOCAL_TARGET")
    return content_fingerprint({"scheme":parsed.scheme,"host":parsed.hostname,"port":parsed.port})

def deterministic_multipart(fields,file_field,filename,mime,data,request_fingerprint,max_bytes):
    if len(data)>max_bytes or "/" in filename or "\\" in filename or filename in (".",".."): raise MutationTransportError("UNSAFE_MULTIPART_FILE")
    boundary="jem-"+request_fingerprint[:48]; chunks=[]
    for key in sorted(fields): chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{fields[key]}\r\n".encode()])
    chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),data,f"\r\n--{boundary}--\r\n".encode()])
    return "multipart/form-data; boundary="+boundary,b"".join(chunks)

class LocalMutationTransport:
    def __init__(self,base_url,authorization,expected,token=None,opener_factory=build_opener):
        validate_authorization(authorization,expected,real_transport=True)
        self._base=base_url.rstrip("/"); target_fingerprint(self._base)
        self._token=token if token is not None else os.environ.get(TOKEN_ENV)
        if not self._token: raise MutationTransportError("MUTATION_TOKEN_REQUIRED")
        self._opener=opener_factory(ProxyHandler({}),_NoRedirect)
    def post_json(self,kind,payload):
        endpoint=ALLOWED_ENDPOINTS.get(kind)
        if endpoint is None or kind in ("image","technical_sheet"): raise MutationTransportError("ENDPOINT_NOT_ALLOWED_FOR_JSON")
        body=canonical_bytes(payload); return self._post(endpoint,body,"application/json")
    def post_multipart(self,kind,fields,filename,mime,data,expected_sha256,expected_size,request_fingerprint):
        if kind not in ("image","technical_sheet") or len(data)!=expected_size or __import__("hashlib").sha256(data).hexdigest()!=expected_sha256: raise MutationTransportError("FILE_INTEGRITY_INVALID")
        content_type,body=deterministic_multipart(fields,"file",filename,mime,data,request_fingerprint,25*1024*1024)
        return self._post(ALLOWED_ENDPOINTS[kind],body,content_type)
    def _post(self,endpoint,body,content_type):
        request=Request(self._base+endpoint,data=body,headers={"Authorization":"Bearer "+self._token,"Content-Type":content_type},method="POST")
        with self._opener.open(request,timeout=30) as response:
            raw=response.read(MAX_RESPONSE_BYTES+1)
            if len(raw)>MAX_RESPONSE_BYTES: raise MutationTransportError("RESPONSE_TOO_LARGE")
            if response.status!=201 or response.headers.get_content_type()!="application/json": raise MutationTransportError("UNEXPECTED_RESPONSE")
            try: value=json.loads(raw.decode("utf-8",errors="strict"))
            except (UnicodeError,json.JSONDecodeError) as error: raise MutationTransportError("INVALID_RESPONSE") from error
            if not isinstance(value,dict) or type(value.get("id")) is not int: raise MutationTransportError("INVALID_RESPONSE")
            return {"status":response.status,"body":value}
