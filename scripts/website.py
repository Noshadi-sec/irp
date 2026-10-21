"""Build, check and serve the static website.

Usage: python scripts/website.py build | check | serve

build copies website/public to website/_site, adds the README figure, and
renders the gallery from website/gallery/*.json. check verifies that every
internal link and asset in the built site resolves.
"""

from __future__ import annotations

import html
import http.server
import json
import re
import shutil
import socketserver
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "website" / "_site"
PUBLIC = REPO / "website" / "public"
GALLERY = REPO / "website" / "gallery"

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
  <header>
    <a class="brand" href="{root}">IRP</a>
    <nav><a href="{root}gallery/">Gallery</a><a href="https://github.com/Noshadi-sec/irp">GitHub</a></nav>
  </header>
  <main>
{body}
  </main>
  <footer>Reports are written from each study's evidence log. Verify a bundle with <code>irp verify --study DIR</code>.</footer>
</body>
</html>
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def load_entries() -> list[dict[str, Any]]:
    entries = []
    for path in sorted(GALLERY.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", entry.get("slug", "")):
            raise SystemExit(f"{path.name}: slug must be lowercase letters, digits and hyphens")
        entries.append(entry)
    return entries


def ours(claim: dict[str, Any]) -> str:
    if claim.get("verdict") == "could_not_run":
        return "not run: " + esc((claim.get("could_not_run") or {}).get("reason"))
    aggregate = claim.get("ours") or {}
    if aggregate.get("value") is None:
        return "-"
    text = f"{aggregate['value']:.4g}"
    if (aggregate.get("count") or 0) > 1:
        text += f" ({aggregate['count']} seeds)"
    return esc(text)


def study_page(entry: dict[str, Any]) -> str:
    report = entry["report"]
    rows = "\n".join(
        f"<tr><td>{esc(c['id'])} {esc(c['statement'])}</td><td>{esc(c['where']['label'])}</td>"
        f"<td>{esc(c['paper']['text'])}</td><td>{ours(c)}</td>"
        f'<td class="verdict-{esc(c["verdict"])}">{esc(c["verdict_label"])}</td></tr>'
        for c in report["claims"]
    )
    paper = entry["paper"]
    link = (
        f'<a href="https://arxiv.org/abs/{esc(paper["arxiv_id"])}{esc(paper.get("version") or "")}">arXiv {esc(paper["arxiv_id"])}{esc(paper.get("version") or "")}</a>'
        if paper.get("arxiv_id")
        else esc(paper.get("title"))
    )
    head = esc(report["provenance"]["evidence"]["head"])
    body = f"""    <h1>{esc(paper.get("title"))}</h1>
    <p class="lead">{link}. Submitted by {esc(entry.get("submitted_by"))}.</p>
    <table><thead><tr><th>Claim</th><th>Where</th><th>Paper</th><th>Ours</th><th>Verdict</th></tr></thead>
    <tbody>
{rows}
    </tbody></table>
    <p>Evidence head: <code>{head}</code>. <a href="{esc(entry.get("bundle_url"))}">Download the bundle</a> and run <code>irp verify</code>.</p>"""
    return PAGE.format(title=esc(paper.get("title")) + " | IRP gallery", root="../../", body=body)


def gallery_index(entries: list[dict[str, Any]]) -> str:
    if entries:
        items = "\n".join(
            f'<tr><td><a href="{esc(e["slug"])}/">{esc(e["paper"].get("title"))}</a></td>'
            f"<td>{esc(e['report']['summary']['claims'])}</td>"
            f"<td>{esc(sum(v for k, v in e['report']['summary']['verdicts'].items() if k in ('reproduced', 'close')))}</td></tr>"
            for e in entries
        )
        body = f"""    <h1>Gallery</h1>
    <table><thead><tr><th>Paper</th><th>Claims</th><th>Reproduced or close</th></tr></thead>
    <tbody>
{items}
    </tbody></table>"""
    else:
        body = """    <h1>Gallery</h1>
    <p class="lead">No reports are published yet. The first showcases arrive with the public launch.</p>"""
    return PAGE.format(title="Gallery | IRP", root="../", body=body)


def build() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(PUBLIC, SITE)
    shutil.copyfile(REPO / "docs" / "assets" / "irp-flow.svg", SITE / "assets" / "irp-flow.svg")
    entries = load_entries()
    (SITE / "gallery").mkdir(exist_ok=True)
    (SITE / "gallery" / "index.html").write_text(gallery_index(entries), encoding="utf-8")
    for entry in entries:
        page = SITE / "gallery" / entry["slug"] / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(study_page(entry), encoding="utf-8")
    print(f"built {SITE} ({len(entries)} gallery entries)")


def check() -> int:
    if not SITE.is_dir():
        build()
    problems = []
    for page in SITE.rglob("*.html"):
        for target in re.findall(r'(?:href|src)="([^"]+)"', page.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (page.parent / target.split("#")[0]).resolve()
            if resolved.is_dir():
                resolved = resolved / "index.html"
            if not resolved.exists():
                problems.append(f"{page.relative_to(SITE)} -> {target}")
    for problem in problems:
        print(problem, file=sys.stderr)
    print("site check ok" if not problems else f"{len(problems)} broken links")
    return 1 if problems else 0


def serve() -> None:
    build()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(SITE), **kwargs)

    with socketserver.TCPServer(("127.0.0.1", 4173), Handler) as server:
        print("serving http://127.0.0.1:4173/")
        server.serve_forever()


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "build"
    if command == "build":
        build()
        return 0
    if command == "check":
        build()
        return check()
    if command == "serve":
        serve()
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
