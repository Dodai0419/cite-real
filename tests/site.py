"""A local test site: real articles, soft 404s, login walls, fake PDFs, a real PDF.

    python tests/site.py [port] [delay_seconds]     # serve until Ctrl+C
    from tests.site import serve                     # (server, base_url) for tests
"""
import sys, threading, time, zlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

WORDS = ("Citation checking matters because agents invent links that look right. A real page has a body "
         "of text that a reader can quote, line by line, and the claim should be found there. ").split()


def prose(n_words, seed=0):
    return " ".join(WORDS[(i * 7 + seed) % len(WORDS)] for i in range(n_words))


def tiny_pdf(text):
    """A one-page PDF with real text, built by hand so tests need no PDF library."""
    lines = [text[i:i + 90] for i in range(0, len(text), 90)]
    ops = "BT /F1 8 Tf 20 800 Td 10 TL " + " ".join("(%s) '" % l.replace("(", "").replace(")", "") for l in lines) + " ET"
    stream = zlib.compress(ops.encode("latin-1"))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def html(title, body, head=""):
    return ("<!doctype html><html><head>%s<title>%s</title></head><body><nav><a href='/'>Home</a> "
            "<a href='/about'>About</a></nav>%s<footer>footer text</footer></body></html>" % (head, title, body))


JA = "".join(map(chr, (0x5f15, 0x7528, 0x306f, 0x672c, 0x6587, 0x306e, 0x884c, 0x3092, 0x6307, 0x3059, 0x3002)))  # a short Japanese sentence

PAGES = {  # path -> (status, content-type, body bytes)
    "/article": (200, "text/html; charset=utf-8", html("Real article", "<main><h1>Why citations break</h1><p>%s</p>"
                 "<p>See <a href='/paper.pdf'>the paper</a> and <a href='https://example.org/x'>this</a>.</p><p>%s</p></main>"
                 % (prose(200), prose(150, 3))).encode()),
    "/blog/post/": (200, "text/html", html("Blog", "<article><h2>Post</h2><p>%s</p></article>" % prose(260, 5)).encode()),
    "/sjis": (200, "text/html", ("<html><head><meta charset='Shift_JIS'></head><body><main><p>" + JA * 120
              + "</p></main></body></html>").encode("cp932")),
    "/readme.md": (200, "text/markdown; charset=utf-8", ("<!-- generated -->\n# Readme\n\n" + prose(220, 2)).encode()),
    "/paper.pdf": (200, "application/pdf", tiny_pdf(prose(700, 1))),
    "/soft404": (200, "text/html", html("Oops", "<h1>Page not found</h1><p>%s</p>" % prose(200, 4)).encode()),
    "/login": (200, "text/html", html("Login", "<h1>Sign in to continue</h1><p>%s</p>" % prose(300, 6)).encode()),
    "/short": (200, "text/html", html("Short", "<p>Only a teaser.</p>").encode()),
    "/fake.pdf": (200, "text/html", html("Denied", "<h1>Access denied</h1><p>%s</p>" % prose(40)).encode()),
    "/empty": (200, "text/html", b""),
    "/blob": (200, "application/octet-stream", b"\x00\x01binary" * 300),
    "/moved": (308, "", b""),
}


class Handler(BaseHTTPRequestHandler):
    delay = 0.0

    def do_GET(self):
        time.sleep(self.delay)
        path = self.path.split("?")[0].split("#")[0]
        status, ctype, body = PAGES.get(path, (404, "text/html", b"<h1>404 Not Found</h1>"))
        self.send_response(status)
        if status == 308:
            self.send_header("Location", "/article")
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(port=0, delay=0.0):
    handler = type("H", (Handler,), {"delay": delay})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_address[1]


if __name__ == "__main__":
    srv, base = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765, float(sys.argv[2]) if len(sys.argv) > 2 else 0)
    print("serving", base, "paths:", " ".join(PAGES))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
