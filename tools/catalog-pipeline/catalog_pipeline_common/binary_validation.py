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
    """Validate JPEG container structure without decoding entropy-coded data."""
    if len(data)<4 or data[:2]!=b"\xff\xd8": return False
    position=2; frame_components=None; saw_scan=False
    sof_markers={0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf}
    length_markers=sof_markers|{0xc4,0xcc,0xdb,0xdc,0xdd,0xde,0xdf,0xda,0xfe,*range(0xe0,0xfe)}
    while position<len(data):
        # Segment context: a marker starts with one or more FF fill bytes.
        if data[position]!=0xff: return False
        while position<len(data) and data[position]==0xff: position+=1
        if position>=len(data): return False
        marker=data[position]; position+=1
        if marker==0xd9:
            return position==len(data) and frame_components is not None and saw_scan
        if marker in {0x00,0x01,0xd8,*range(0xd0,0xd8)} or marker not in length_markers: return False
        if position+2>len(data): return False
        length=int.from_bytes(data[position:position+2],"big")
        if length<2 or position+length>len(data): return False
        payload=position+2; end=position+length
        if marker in sof_markers:
            if frame_components is not None or length<8: return False
            components=data[payload+5]
            if data[payload+1:payload+3]==b"\x00\x00" or data[payload+3:payload+5]==b"\x00\x00": return False
            if components not in range(1,5) or length!=8+3*components: return False
            frame_components=components
        elif marker==0xda:
            if frame_components is None or length<6: return False
            components=data[payload]
            if components not in range(1,frame_components+1) or length!=6+2*components: return False
            saw_scan=True; position=end
            # Scan context: stuffed FF and restart markers remain entropy data;
            # any other marker returns control to the segment parser.
            while position<len(data):
                if data[position]!=0xff: position+=1; continue
                marker_start=position
                while position<len(data) and data[position]==0xff: position+=1
                if position>=len(data): return False
                scan_marker=data[position]
                if scan_marker==0x00 or scan_marker in range(0xd0,0xd8):
                    position+=1; continue
                position=marker_start; break
            else: return False
            continue
        position=end
    return False

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
