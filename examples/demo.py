"""Offline demo: serve the local test site and check a note that cites real and fake pages."""
import sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cite_real  # noqa: E402
from tests.site import serve  # noqa: E402

srv, base = serve()
note = Path(tempfile.mkdtemp()) / "notes.md"
note.write_text("""# Notes an agent wrote
The main result is in [the article](%(b)s/article) and [the paper](%(b)s/paper.pdf).
Setup steps: %(b)s/readme.md. Background: %(b)s/blog/post/.
Also cited: [the PDF](%(b)s/fake.pdf), %(b)s/login, %(b)s/soft404 and %(b)s/gone.
""" % {"b": base}, encoding="utf-8")
code = cite_real.main(["check", str(note), "--save", str(note.parent / "sources")])
srv.shutdown()
print("(exit code of check: %d; this demo exits 0)" % code)
