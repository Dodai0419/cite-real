"""Time imozuru (one fetch.py process per link, as its skill runs it) against cite-real.

    python bench/bench.py <imozuru checkout> [delay_seconds=0.3] [runs=3]

Uses the local test site with an artificial server delay per request, so the network is
the same for both. 11 links: 5 real pages and 6 fakes.
"""
import statistics, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.site import PAGES, serve  # noqa: E402

fetch = Path(sys.argv[1]) / "skills" / "imozuru" / "scripts" / "fetch.py"
delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
runs = int(sys.argv[3]) if len(sys.argv) > 3 else 3
srv, base = serve(delay=delay)
urls = [base + p for p in PAGES if p != "/moved"]
d = Path(tempfile.mkdtemp())
(d / "notes.md").write_text("\n".join(urls), encoding="utf-8")


def imozuru():
    return ["OK" if subprocess.run([sys.executable, str(fetch), str(d / "imo"), "p%d" % i, u], capture_output=True,
                                   encoding="utf-8", errors="replace").stdout.startswith("OK") else "FAIL"
            for i, u in enumerate(urls)]


def cite_real(jobs):
    out = subprocess.run([sys.executable, str(ROOT / "cite_real.py"), "check", str(d / "notes.md"), "--jobs", str(jobs)],
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    return [l.split()[0] for l in out.splitlines()[:-1]]


for name, fn in (("imozuru fetch.py x%d" % len(urls), imozuru), ("cite-real --jobs 1", lambda: cite_real(1)),
                 ("cite-real --jobs 8", lambda: cite_real(8))):
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        verdicts = fn()
        times.append((time.perf_counter() - t) * 1000)
    print("%-22s median %6.0f ms of %d  verdicts %s" % (name, statistics.median(times), runs, " ".join(verdicts)))
srv.shutdown()
