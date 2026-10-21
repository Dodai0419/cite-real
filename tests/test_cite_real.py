import io, json, shutil, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cite_real as cr  # noqa: E402
from tests.site import PAGES, serve  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "golden.json").read_text(encoding="utf-8"))


def run(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cr.main(list(argv))
    return code, buf.getvalue()


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.base = serve()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_same_verdict_and_text_as_imozuru(self):
        # golden = imozuru fetch.py run once per page on this site (bench/golden.py)
        for path, want in GOLDEN["pages"].items():
            if path == "/paper.pdf" and not shutil.which("pdftotext"):
                continue
            ok, reason, text, kind = cr.judge(self.base + path, 10)
            self.assertEqual(ok, want["ok"], (path, reason))
            if ok:
                self.assertEqual(text.replace(self.base, "{BASE}"), want["text"], path)

    def test_check_saves_real_pages_and_fails_on_fakes(self):
        d = Path(tempfile.mkdtemp())
        doc = d / "notes.md"
        doc.write_text("Good: %s/article and %s/readme.md. Bad: [paper](%s/fake.pdf), %s/login."
                       % ((self.base,) * 4), encoding="utf-8")
        code, out = run("check", str(doc), "--save", str(d / "sources"))
        self.assertEqual(code, 1)
        self.assertIn("2 of 4 cited pages are real; 2 are not", out)
        self.assertIn("FAIL %s/fake.pdf hit a wall (access denied)" % self.base, out)
        self.assertEqual(len(list((d / "sources").glob("*.md"))), 2)
        # the saved pages now back the citations offline, the fake ones do not
        code, out = run("known", str(doc), "--sources", str(d / "sources"))
        self.assertEqual(code, 1)
        self.assertIn("2 of 4 cited pages are saved", out)

    def test_parallel_order_is_stable(self):
        d = Path(tempfile.mkdtemp())
        doc = d / "n.md"
        paths = [p for p in PAGES if p not in ("/paper.pdf",)]
        doc.write_text("\n".join(self.base + p for p in paths), encoding="utf-8")
        _, out = run("check", str(doc), "--jobs", "16")
        self.assertEqual([l.split()[1] for l in out.splitlines()[:-1]], [self.base + p for p in paths])


class Urls(unittest.TestCase):
    def test_same_urls_as_claudemy(self):
        doc = (ROOT / "tests" / "cites.md").read_text(encoding="utf-8")
        self.assertEqual(cr.cited_urls(doc), list(dict.fromkeys(GOLDEN["cited"])))
        for u, key in GOLDEN["same_page"].items():
            self.assertEqual(cr.same_page(u), key)

    def test_no_links_is_not_a_failure(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.md").write_text("no links here", encoding="utf-8")
        self.assertEqual(run("check", str(d / "a.md"))[0], 0)


if __name__ == "__main__":
    unittest.main()
