import binascii, pathlib, struct, sys, unittest
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.media import validate_binary

LIMITS={"max_bytes":1024*1024,"max_width":1000,"max_height":1000,"max_pixels":1000000}

def chunk(kind,data): return struct.pack(">I",len(data))+kind+data+struct.pack(">I",binascii.crc32(kind+data)&0xffffffff)
def png(width=1,height=1): return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+chunk(b"IEND",b"")
def jpeg(): return b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xd9"
def webp():
 payload=b"\x2f\x00\x00\x00\x00"; body=b"WEBPVP8L"+struct.pack("<I",len(payload))+payload+b"\x00"; return b"RIFF"+struct.pack("<I",len(body))+body
def pdf(extra=b""):
 body=b"%PDF-1.4\n1 0 obj<<>>endobj\n"+extra+b"xref\n0 1\n0000000000 65535 f \ntrailer<< /Size 1 >>\nstartxref\n9\n%%EOF\n"; return body

class BinaryValidationTests(unittest.TestCase):
 def check(self,data,kind,mime,name): return validate_binary(data,kind,mime,name,LIMITS)
 def test_jpeg_container_and_truncation(self):
  self.assertEqual("valid_container",self.check(jpeg(),"image","image/jpeg","invented.jpg")["status"])
  self.assertEqual("invalid",self.check(jpeg()[:-2],"image","image/jpeg","invented.jpg")["status"])
 def test_png_crc_end_and_dimensions(self):
  self.assertEqual({"width":1,"height":1},self.check(png(),"image","image/png","invented.png")["dimensions"])
  damaged=bytearray(png()); damaged[-1]^=1
  self.assertIn("crc_mismatch",self.check(bytes(damaged),"image","image/png","invented.png")["risks"])
  self.assertEqual("invalid",self.check(png(0,1),"image","image/png","invented.png")["status"])
 def test_webp_container_and_truncation(self):
  self.assertEqual("valid_container",self.check(webp(),"image","image/webp","invented.webp")["status"])
  self.assertEqual("invalid",self.check(webp()[:-1],"image","image/webp","invented.webp")["status"])
 def test_mime_empty_size_and_unsupported_svg(self):
  self.assertIn("mime_signature_mismatch",self.check(png(),"image","image/jpeg","same.jpg")["risks"])
  self.assertEqual("invalid",self.check(b"","image",None,"empty")["status"])
  tiny=dict(LIMITS,max_bytes=1); self.assertIn("size_limit_exceeded",validate_binary(png(),"image","image/png","x.png",tiny)["risks"])
  self.assertEqual("unsupported",self.check(b"<svg><script/></svg>","image","image/svg+xml","x.svg")["status"])
 def test_pdf_valid_truncated_encrypted_active_and_disguised(self):
  self.assertEqual("valid_container",self.check(pdf(),"document","application/pdf","invented.pdf")["status"])
  self.assertEqual("invalid",self.check(pdf()[:-8],"document","application/pdf","invented.pdf")["status"])
  self.assertEqual("encrypted_review_required",self.check(pdf(b"/Encrypt "),"document","application/pdf","invented.pdf")["status"])
  self.assertEqual("active_content_review_required",self.check(pdf(b"/JavaScript /OpenAction "),"document","application/pdf","invented.pdf")["status"])
  self.assertEqual("unsupported",self.check(b"<html>invented</html>","document","application/pdf","invented.pdf")["status"])
 def test_same_filename_different_bytes_and_exact_bytes_only(self):
  first=self.check(png(),"image","image/png","same.png"); second=self.check(png(2,1),"image","image/png","same.png")
  self.assertNotEqual(first["dimensions"],second["dimensions"])

if __name__=="__main__": unittest.main()
