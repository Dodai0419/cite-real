---
name: cite-real
description: Check every link cited in a Markdown file is a real readable page (not a 404, soft 404, login wall, bot check or HTML pretending to be a PDF), save the real ones, and verify citations only point at saved pages. Use for "are these links real", "check the sources", "verify citations" before publishing notes, READMEs or research.
---

# cite-real

Use cite-real before you hand over any document with links you wrote or collected: research notes, READMEs, reports, lesson cards. Run the CLI instead of opening links one by one; it judges the page content, not the HTTP status, and fetches all links in parallel.

## Commands (run from the repo root; Python 3.9+, no dependencies; pdftotext optional for PDFs)

```bash
python cite_real.py check FILE.md [MORE.md ...]                 # judge every cited link
python cite_real.py check FILE.md --save sources/                # also keep each real page as Markdown (url: line first)
python cite_real.py known FILE.md --sources sources/             # offline: fail on any citation not saved in sources/
python cite_real.py check FILE.md --jobs 16 --timeout 30         # more parallel downloads, shorter timeout
```

Output: one `OK` / `FAIL` line per link with the character count and first line, or the reason. Exit code 1 if any link fails.

## Rules
- A FAIL is not proof the page is gone: bot checks and empty responses may open in a browser. Say which reason it gave.
- Replace or remove every FAIL link before you finish; do not keep a citation you could not read.
- When you quote a page, quote from the text saved by `--save`, not from memory.
- HTML comments are ignored; links inside them are not citations.
