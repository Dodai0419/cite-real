"""Regenerate tests/golden.json by running the upstream code on the local test site.

    python bench/golden.py <imozuru checkout> <claudemy checkout>

imozuru: skills/imozuru/scripts/fetch.py is run once per page (as the skill does), with `ax`
absent, and its OK/FAIL plus the saved text are recorded. claudemy: cited_urls() and same_page()
from skills/claudemy/scripts/check_lessons.py on tests/cites.md.
"""
import json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.site import PAGES, serve  # noqa: E402

imozuru, claudemy = Path(sys.argv[1]), Path(sys.argv[2])
fetch = imozuru / "skills" / "imozuru" / "scripts" / "fetch.py"
srv, base = serve()
pages = {}
for path in list(PAGES) + ["/nope"]:
    with tempfile.TemporaryDirectory() as d:
        out = subprocess.run([sys.executable, str(fetch), d, "page", base + path], capture_output=True,
                             encoding="utf-8", errors="replace").stdout.split("\t")
        text = ""
        if out[0] == "OK":
            text = Path(out[2]).read_text(encoding="utf-8")
        pages[path] = {"ok": out[0] == "OK", "text": text.replace(base, "{BASE}")}
srv.shutdown()

sys.path.insert(0, str(claudemy / "skills" / "claudemy" / "scripts"))
import check_lessons  # noqa: E402

doc = (ROOT / "tests" / "cites.md").read_text(encoding="utf-8")
body = check_lessons.re.sub(r"<!--.*?-->", "", doc, flags=check_lessons.re.S)
urls = check_lessons.cited_urls(body)
golden = {"pages": pages, "cited": urls, "same_page": {u: check_lessons.same_page(u) for u in urls}}
(ROOT / "tests" / "golden.json").write_text(json.dumps(golden, indent=1), encoding="utf-8")
print({p: v["ok"] for p, v in pages.items()}, len(urls), "urls")
