# IRP website

A static site: plain HTML and CSS in `public/`, and a gallery generated from
report data in `gallery/`. There is no frontend framework, bundler or npm
dependency. `scripts/website.py` builds, checks and serves it.

```bash
uv run python scripts/website.py build   # writes website/_site/
uv run python scripts/website.py check   # every internal link and asset resolves
uv run python scripts/website.py serve   # http://127.0.0.1:4173/
```

## Gallery

Each published study is one JSON file in `gallery/`, made from a reproduction
report submitted through the issue form. It holds the paper, the result line,
the claim table, the evidence head hash and a link to the bundle. The build
renders one page per study and the gallery index. A study is published only
after its bundle passes `irp verify`; a "not reproduced" study only after
its authors were contacted.

```json
{
  "slug": "example-paper",
  "paper": {"title": "Example Paper", "arxiv_id": "2501.12345", "version": "v2"},
  "report": "report.json contents (the full document)",
  "bundle_url": "https://github.com/Noshadi-sec/irp-gallery/releases/download/...",
  "submitted_by": "@handle",
  "authors_contacted": true
}
```

## Deploying

`.github/workflows/website.yml` builds and checks the site and deploys it to
GitHub Pages on manual dispatch from main. Set **Settings → Pages → Source** to
**GitHub Actions** first.
