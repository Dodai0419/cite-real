<div align="center">

# cite-real

**Check that every link your agent cites is a real page, not a 404, a login wall or a fake PDF.**

Agents write notes and READMEs full of links that look right. imozuru learned that 5 of 11 search-result links were dead, walled or HTML pretending to be a PDF; claudemy refuses any citation of a page that was never read. cite-real does both checks on any Markdown file, in parallel.

Works with **Claude Code** and **Codex**.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg) ![Status: prototype](https://img.shields.io/badge/status-prototype-orange.svg)

</div>

## Quick start
```bash
git clone https://github.com/Dodai0419/cite-real && cd cite-real
python cite_real.py check NOTES.md --save sources/
```
Offline demo (`python examples/demo.py` serves a local test site):
```
OK   http://127.0.0.1:56363/article (1995 chars) # Why citations break
OK   http://127.0.0.1:56363/paper.pdf (3809 chars) checking look body quote, should because A text by ...
FAIL http://127.0.0.1:56363/fake.pdf hit a wall (access denied)
FAIL http://127.0.0.1:56363/login hit a wall (sign in to continue)
FAIL http://127.0.0.1:56363/soft404 hit a wall (page not found)
FAIL http://127.0.0.1:56363/gone HTTPError: HTTP Error 404: Not Found
4 of 8 cited pages are real; 4 are not.
```
Exit code 1 when any cited page is not real. Python 3.9+, standard library only; `pdftotext` (ships with Git for Windows and poppler) is used for PDFs when present.

## The problem
- A link that returns HTTP 200 can still be a "page not found" page, a login wall or a bot check.
- A URL ending in `.pdf` can be an HTML error page.
- Agents cite pages they never opened, and checking 30 links one by one takes minutes.

## The solution
| Idea | Fixes |
|------|-------|
| **Judge the content, not the status** (imozuru's rules: minimum text length, wall phrases in the first 4000 characters, real PDF text) | Soft 404s, login walls, fake PDFs |
| **All links in parallel, one process** | 11 links: 14.6 s down to 1.5 s with a 0.3 s server delay |
| **Save what was read** (`--save`), each page as Markdown with a `url:` line | A record of the exact text behind each citation |
| **`known` mode** (claudemy's rule): every cited URL must be a saved page, matched by page (scheme, `www.`, `#fragment`, trailing `/` ignored) | Citations of pages nobody read, checked offline |

```bash
python cite_real.py check draft.md --save sources/       # fetch and judge every link, keep the real ones
python cite_real.py known draft.md --sources sources/    # later, offline: no citation outside sources/
```

## Use with Claude Code
```bash
/plugin marketplace add Dodai0419/cite-real
/plugin install cite-real@cite-real
```
Then ask: "check the links in this README are real".

## Use with Codex (ChatGPT)
```bash
git clone https://github.com/Dodai0419/cite-real && cp -r cite-real/skills/* ~/.codex/skills/
```
Or copy `AGENTS.md` into your project root.

## Benchmarks
`python bench/bench.py <imozuru checkout> <delay> 3`: the local test site, 11 links (5 real, 6 fakes), median of 3 runs. imozuru is run the way its skill runs it: one `fetch.py` process per link. Windows 11, Python 3.11.1.

| | imozuru fetch.py, once per link | cite-real |
|-|-|-|
| 11 links, 0.3 s server delay | 14626 ms | 1457 ms (`--jobs 8`), 4346 ms (`--jobs 1`) |
| 11 links, no delay | 6585 ms | 745 ms (`--jobs 1`), 1091 ms (`--jobs 8`) |
| lines of code | 620 (fetch.py 484 + check_lessons.py 136) | 238 (cite_real.py) |
| dependencies | 0 (+ optional ax, pdftotext, tesseract, yt-dlp) | 0 (+ optional pdftotext) |

Same results:
- `test_same_verdict_and_text_as_imozuru`: on 13 test pages (real article, `<article>` blog post, Shift_JIS page, Markdown, real PDF, soft 404, login wall, short page, fake PDF, empty body, binary, 308 redirect, real 404) the OK/FAIL verdict and the saved text are identical to imozuru's (golden made by `bench/golden.py`).
- `test_same_urls_as_claudemy`: the URLs found in `tests/cites.md` and their page keys are identical to claudemy's `cited_urls` and `same_page` (cite-real also drops duplicates).
- Live web, 5 links (Wikipedia, docs.python.org, example.com, a GitHub 404, a raw README): same 5 verdicts and the same character counts as imozuru.

## What it leaves out
imozuru also fetches YouTube transcripts (yt-dlp), OCRs scanned PDFs (tesseract), retries arXiv PDFs as HTML and uses `ax` when installed. cite-real does not: it is a link checker, not a research crawler. X/Twitter links fail fast with a reason, as in imozuru.

## Inspired by
- [MaryCache/imozuru](https://github.com/MaryCache/imozuru) (MIT): the content-based verdict, the wall phrases, charset handling and HTML-to-text extraction.
- [assafkip/claudemy](https://github.com/assafkip/claudemy) (MIT): the URL pattern, the trailing-mark rules and "cite only pages that are on disk".

## Roadmap
- [ ] Check that a quoted sentence actually appears in the saved page.
- [ ] A GitHub Action that runs `check` on changed Markdown files.

## License
MIT. See `LICENSE` for the upstream copyright notices.
