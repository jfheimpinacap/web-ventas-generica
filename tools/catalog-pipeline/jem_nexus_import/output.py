"""Atomic, idempotent output-set writer."""
import errno, os, tempfile
from pathlib import Path
from catalog_pipeline_common.serialization import canonical_bytes

_UNSUPPORTED_DIRECTORY_SYNC = frozenset(filter(None, (
    errno.EACCES, errno.EPERM, errno.EINVAL, getattr(errno, "ENOTSUP", None),
    getattr(errno, "EOPNOTSUPP", None), getattr(errno, "EBADF", None),
)))

def _fsync_directory_if_supported(directory):
    """Sync metadata unless the platform specifically rejects directory handles."""
    handle=None
    try:
        handle=os.open(directory,os.O_RDONLY)
        os.fsync(handle)
    except OSError as error:
        if error.errno not in _UNSUPPORTED_DIRECTORY_SYNC: raise
    finally:
        if handle is not None: os.close(handle)

def _publication_order(names):
    """Keep the artifact that signals a complete set behind its dependencies."""
    markers=("jem-state-snapshot.json","import-plan.json","import-dry-run-manifest.json")
    return sorted(names,key=lambda name:(name in markers,markers.index(name) if name in markers else -1,name))

def write_output_set(directory,documents):
    target=Path(directory); target.mkdir(parents=True,exist_ok=True)
    encoded={name:(value if isinstance(value,bytes) else canonical_bytes(value)) for name,value in documents.items()}
    for name,data in encoded.items():
        path=target/name
        if path.exists() and path.read_bytes()!=data: raise FileExistsError("DESTINATION_CONFLICT:"+name)
    staged=[]; published=[]
    try:
        for name,data in encoded.items():
            path=target/name
            if path.exists(): continue
            fd,temp=tempfile.mkstemp(prefix="."+name+".writing-",suffix=".tmp",dir=target)
            with os.fdopen(fd,"wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            staged.append((Path(temp),path))
        by_name={path.name:(temp,path) for temp,path in staged}
        for name in _publication_order(by_name):
            temp,path=by_name[name]; os.replace(temp,path); published.append(path)
        _fsync_directory_if_supported(target)
    except Exception:
        for path in reversed(published): path.unlink(missing_ok=True)
        raise
    finally:
        for temp,_ in staged: temp.unlink(missing_ok=True)
