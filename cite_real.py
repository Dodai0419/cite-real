#!/usr/bin/env python3
"""cite-real: check that every link an agent cites is a real page, not a 404, a login wall or a fake PDF.

    python cite_real.py check NOTES.md [MORE.md ...] [--save sources/] [--jobs 8]
    python cite_real.py known NOTES.md --sources sources/     # offline: cites only pages saved on disk

`check` fetches every cited URL in parallel and judges the CONTENT (length, wall phrases,
PDF text), not the HTTP status. `--save` keeps each real page as Markdown with a `url:`
line, so `known` can later refuse a citation of a page nobody read.
Verdicts follow MaryCache/imozuru fetch.py; URL rules follow assafkip/claudemy check_lessons.py.
Standard library only (pdftotext, if installed, for PDFs).
"""
import argparse, codecs, hashlib, re, shutil, subprocess, sys, tempfile
import urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

MIN_TEXT_CHARS, MIN_HTML_CHARS, MAX_BYTES = 3000, 1000, 40_000_000
WALL_PATTERNS = ("404 not found", "page not found", "access denied", "you do not currently have access",
                 "sign in to continue", "log in to continue", "enable javascript", "are you a robot", "captcha")
# Balanced parentheses stay in a URL (Mercury_(planet)); a lone ")" ends it, as in a Markdown link.
URL = re.compile(r"https?://(?:[^\s()<>\[\]`]|\([^\s()<>]*\))+")
TRAILING = ".,;:!?*_'\"`"
X_POST = re.compile(r"^https?://(www\.)?(x|twitter)\.com/")
CHARSET_ALIASES = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "x-sjis": "cp932",
                   "windows-31j": "cp932", "ms_kanji": "cp932"}


# --- which URLs a document cites (claudemy) -------------------------------------------------
def cited_urls(text):
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)  # editor notes are not citations
    return list(dict.fromkeys(u.rstrip(TRAILING) for u in URL.findall(body)))


def same_page(url):
    """One key per page: scheme, www., #fragment and a trailing slash do not change the page."""
    url = url.rstrip(TRAILING)
    m = re.match(r"https?://([^/?#]+)([^#]*)", url, re.I)
    if not m:
        return url
    path, q, query = m.group(2).partition("?")
    return m.group(1).lower().removeprefix("www.") + path.rstrip("/") + q + query


# --- is the page real (imozuru) -------------------------------------------------------------
class _Redirect308(urllib.request.HTTPRedirectHandler):
    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302  # Python 3.10 lacks it

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, 307 if code == 308 else code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_Redirect308)


def download(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 cite-real"})
    with _OPENER.open(req, timeout=timeout) as res:
        return res.read(MAX_BYTES), res.headers.get("Content-Type", "")


def decode_text(body, ctype=""):
    """Declared charset, then UTF-8, then the usual Japanese ones; the first that decodes cleanly."""
    found = re.findall(r"charset\s*=\s*[\"']?([\w.:-]+)", ctype or "", re.I)
    found += [n.decode("ascii", "ignore") for n in re.findall(rb"<meta[^>]*charset\s*=\s*[\"']?([\w.:-]+)", body[:4096], re.I)]
    codecs_ = []
    for name in [CHARSET_ALIASES.get(n.lower(), n.lower()) for n in found] + ["utf-8", "cp932", "euc_jp"]:
        try:
            c = codecs.lookup(name).name
        except LookupError:
            continue
        codecs_ += [c] if c not in codecs_ else []
    for c in codecs_:
        try:
            return body.decode(c)
        except UnicodeDecodeError:
            pass
    return min((body.decode(c, errors="replace") for c in codecs_), key=lambda t: t.count(chr(0xFFFD)))


class _Text(HTMLParser):
    """Page text as Markdown-ish lines; links kept as [text](url); <main>/<article> if substantial."""
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}
    BLOCK = {"p", "div", "section", "article", "main", "header", "footer", "nav", "aside", "li", "tr", "br", "hr",
             "pre", "blockquote", "table", "ul", "ol", "dl", "dt", "dd", "figure", "figcaption"}
    HEADING = {"h%d" % n: "#" * n + " " for n in range(1, 7)}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.parts, self.focus_parts = base, [], []
        self.skip = self.focus = 0
        self.href, self.link_text = None, []

    def _emit(self, piece):
        self.parts.append(piece)
        if self.focus:
            self.focus_parts.append(piece)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif tag in ("main", "article"):
            self.focus += 1
        elif tag in self.HEADING:
            self._emit("\n\n" + self.HEADING[tag])
        elif tag in self.BLOCK:
            self._emit("\n")
        elif tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("#", "javascript:")):
                self.href, self.link_text = urllib.parse.urljoin(self.base, href), []

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif self.skip:
            return
        elif tag in ("main", "article"):
            self.focus = max(0, self.focus - 1)
        elif tag in self.HEADING or tag in self.BLOCK:
            self._emit("\n")
        elif tag == "a" and self.href is not None:
            text = " ".join("".join(self.link_text).split())
            self._emit("[%s](%s)" % (text, self.href) if text else "")
            self.href = None

    def handle_data(self, data):
        if not self.skip:
            if self.href is not None:
                self.link_text.append(data)
            else:
                self._emit(data)

    def text(self):
        focused = "".join(self.focus_parts)
        raw = focused if len(focused.strip()) >= MIN_HTML_CHARS else "".join(self.parts)
        return re.sub(r"\n{3,}", "\n\n", "\n".join(" ".join(l.split()) for l in raw.splitlines())).strip() + "\n"


def pdf_text(body):
    if not shutil.which("pdftotext"):
        return ""
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "a.pdf"
        pdf.write_bytes(body)
        subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), str(pdf.with_suffix(".txt"))],
                       check=False, stderr=subprocess.DEVNULL)
        out = pdf.with_suffix(".txt")
        return out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""


def judge(url, timeout=90):
    """-> (ok, reason_or_None, text, kind). Same rules as imozuru: the content decides."""
    if X_POST.match(url):
        return False, "X shows a login wall instead of the post", "", ""
    try:
        body, ctype = download(url, timeout)
    except Exception as e:  # HTTP errors and connection failures are both "cannot read it"
        return False, "%s: %s" % (type(e).__name__, e), "", ""
    if not body.strip():
        return False, "empty response (often a bot check; may open in a browser)", "", ""
    if body[:5] == b"%PDF-":
        text, kind = pdf_text(body), "pdf"
    elif ctype.startswith(("text/plain", "text/markdown", "application/json", "text/csv")):
        text, kind = decode_text(body, ctype), "text"
    elif "html" in ctype or body.lstrip()[:1] == b"<":
        p = _Text(url)
        p.feed(decode_text(body, ctype))
        text, kind = p.text(), "html"
    else:
        return False, "unsupported type: %s" % (ctype or "unknown"), "", ""
    floor = MIN_TEXT_CHARS if kind == "pdf" else MIN_HTML_CHARS
    wall = next((w for w in WALL_PATTERNS if w in text[:4000].lower()), None)
    if len(text) < floor or (wall and len(text) < MIN_TEXT_CHARS * 4):
        reason = "hit a wall (%s)" % wall if wall else "text too short (%d chars)" % len(text)
        if kind == "pdf" and not shutil.which("pdftotext"):
            reason += "; pdftotext is not installed"
        return False, reason, text, kind
    return True, None, text, kind


def first_line(text):
    return next((l[:100] for l in (" ".join(x.split()) for x in text.splitlines()) if len(l) > 8), "")


# --- commands -------------------------------------------------------------------------------
def saved_urls(folder):
    return {line[5:].strip() for f in Path(folder).rglob("*.md")
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines()[:12] if line.startswith("url: ")}


def cmd_check(a, urls):
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        results = list(pool.map(lambda u: judge(u, a.timeout), urls))
    for url, (ok, reason, text, kind) in zip(urls, results):
        if ok and a.save:
            out = Path(a.save) / ("%s-%s.md" % (re.sub(r"[^a-z0-9]+", "-", same_page(url).lower())[:60].strip("-"),
                                                  hashlib.sha1(url.encode()).hexdigest()[:8]))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("url: %s\nkind: %s\nchars: %d\n\n%s" % (url, kind, len(text), text), encoding="utf-8")
        print("OK  " if ok else "FAIL", url, "(%d chars) %s" % (len(text), first_line(text)) if ok else reason)
    bad = sum(1 for r in results if not r[0])
    print("%d of %d cited pages are real%s." % (len(urls) - bad, len(urls), "; %d are not" % bad if bad else ""))
    return 1 if bad else 0


def cmd_known(a, urls):
    known = {same_page(u) for u in saved_urls(a.sources)}
    missing = [u for u in urls if same_page(u) not in known]
    for u in missing:
        print("FAIL cites a page that is not in %s: %s" % (a.sources, u))
    print("%d of %d cited pages are saved in %s." % (len(urls) - len(missing), len(urls), a.sources))
    return 1 if missing else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["check", "known"])
    ap.add_argument("files", nargs="+", help="Markdown or text files whose links to check")
    ap.add_argument("--save", help="check: keep the text of every real page here")
    ap.add_argument("--sources", default="sources", help="known: folder of saved pages")
    ap.add_argument("--jobs", type=int, default=8, help="check: parallel downloads (default 8)")
    ap.add_argument("--timeout", type=float, default=90, help="check: seconds per download (default 90)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # page titles in any language must not crash the report
        sys.stdout.reconfigure(errors="replace")
    urls = list(dict.fromkeys(u for f in a.files for u in cited_urls(Path(f).read_text(encoding="utf-8"))))
    if not urls:
        print("no links found; nothing to check")
        return 0
    return (cmd_check if a.command == "check" else cmd_known)(a, urls)


if __name__ == "__main__":
    sys.exit(main())
