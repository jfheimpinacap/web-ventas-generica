"""Concrete, read-only GET boundary for an already validated loopback target."""
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,ProxyHandler,Request,build_opener
from jem_nexus_import.local_client import LocalReadError,READ_PATHS,validate_base_url

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def get_json_bytes(url,headers,timeout,max_bytes):
    """Return status, response MIME and bounded bytes; never follow redirects."""
    parsed=urlsplit(url)
    try: origin=f"{parsed.scheme}://{parsed.netloc}"; validate_base_url(origin)
    except (LocalReadError,ValueError) as error: raise LocalReadError("UNSAFE_LOCAL_TARGET","an exact loopback GET URL is required") from error
    if parsed.path not in READ_PATHS.values() or parsed.query or parsed.fragment:
        raise LocalReadError("UNSAFE_LOCAL_TARGET","an approved loopback GET path is required")
    opener=build_opener(ProxyHandler({}),_NoRedirect)
    request=Request(url,headers=headers,method="GET")
    with opener.open(request,timeout=timeout) as response:
        return response.status,response.headers.get_content_type(),response.read(max_bytes+1)
