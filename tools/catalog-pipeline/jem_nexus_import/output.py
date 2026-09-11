"""Atomic, idempotent output-set writer."""
import os, tempfile
from pathlib import Path
from catalog_acquisition.serialization import canonical_bytes

def write_output_set(directory,documents):
    target=Path(directory); target.mkdir(parents=True,exist_ok=True)
    encoded={name:(value if isinstance(value,bytes) else canonical_bytes(value)) for name,value in documents.items()}
    for name,data in encoded.items():
        path=target/name
        if path.exists() and path.read_bytes()!=data: raise FileExistsError("DESTINATION_CONFLICT:"+name)
    staged=[]
    try:
        for name,data in encoded.items():
            path=target/name
            if path.exists(): continue
            fd,temp=tempfile.mkstemp(prefix="."+name+".writing-",suffix=".tmp",dir=target)
            with os.fdopen(fd,"wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            staged.append((Path(temp),path))
        for temp,path in staged: os.replace(temp,path)
        handle=os.open(target,os.O_RDONLY); os.fsync(handle); os.close(handle)
    finally:
        for temp,_ in staged: temp.unlink(missing_ok=True)
