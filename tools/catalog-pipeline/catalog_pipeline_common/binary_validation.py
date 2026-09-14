"""Pure bounded validation shared by acquisition and local observation."""
import binascii
import re

def _png(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"): return False
    position=8; kinds=[]
    while position<len(data):
        if position+12>len(data): return False
        length=int.from_bytes(data[position:position+4],"big"); kind=data[position+4:position+8]; end=position+12+length
        if end>len(data): return False
        payload=data[position+8:position+8+length]; crc=int.from_bytes(data[position+8+length:end],"big")
        if binascii.crc32(kind+payload)&0xffffffff != crc: return False
        kinds.append(kind); position=end
        if kind==b"IEND": return position==len(data) and len(payload)==0 and kinds[0]==b"IHDR" and kinds.count(b"IHDR")==1
    return False

def _jpeg(data):
    if len(data)<4 or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"): return False
    position=2; saw_structure=False
    while position<len(data)-2:
        if data[position]!=0xff: position+=1; continue
        while position<len(data) and data[position]==0xff: position+=1
        if position>=len(data): return False
        marker=data[position]; position+=1
        if marker in {0x01,*range(0xd0,0xd8)}: continue
        if marker==0xd9: break
        if position+2>len(data): return False
        length=int.from_bytes(data[position:position+2],"big")
        if length<2 or position+length>len(data): return False
        if marker in {0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf}: saw_structure=length>=7
        position+=length
    return saw_structure

def _pdf(data):
    if not re.match(br"%PDF-[12]\.[0-9]",data[:12]) or b"%%EOF" not in data[-2048:]: return "BINARY_SIGNATURE_INVALID"
    matches=list(re.finditer(br"startxref\s+(\d+)",data[-2048:]))
    if not matches or int(matches[-1].group(1))>=len(data): return "BINARY_SIGNATURE_INVALID"
    if b"/Encrypt" in data or any(x in data for x in (b"/JavaScript",b"/JS",b"/Launch",b"/EmbeddedFile",b"/OpenAction",b"/AA")): return "BINARY_PDF_UNSAFE"
    return None

def validate_observed_binary(data,media_class,mime,bindings):
    if media_class=="image":
        fmt="jpeg" if mime=="image/jpeg" else "png" if mime=="image/png" else None
        valid=_jpeg(data) if fmt=="jpeg" else _png(data) if fmt=="png" else False
        extensions={b.get("declared_extension") for b in bindings if b.get("declared_extension")}
        allowed={".jpg",".jpeg"} if fmt=="jpeg" else {".png"}
        code=None if valid and extensions<=allowed else "BINARY_SIGNATURE_INVALID"
        return {"code":code,"validation":"bounded_"+str(fmt)+"_container","declared_size_match":None}
    code=_pdf(data); sizes={b.get("declared_size_bytes") for b in bindings if b.get("declared_size_bytes") is not None}
    size_match=all(size==len(data) for size in sizes)
    if code is None and not size_match: code="BINARY_SIZE_MISMATCH"
    return {"code":code,"validation":"bounded_pdf_structure_and_safety","declared_size_match":size_match}
