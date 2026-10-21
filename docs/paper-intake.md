# Paper intake

`fetch_paper` creates the study and brings the paper in. It accepts:

| Input | Example | What happens |
| --- | --- | --- |
| arXiv ID or URL | `2501.12345`, `2501.12345v2`, `https://arxiv.org/abs/2501.12345` | Metadata from the arXiv API, the LaTeX source, and the PDF |
| PDF URL | `https://example.org/paper.pdf` | The PDF |
| Local PDF | `/papers/paper.pdf` | A copy of the PDF |
| Local LaTeX directory | `/papers/src/` | A copy of the directory (and a PDF beside it, if any) |
| Local source archive | `/papers/src.tar.gz`, `.zip` | The archive, unpacked safely |

An unversioned arXiv ID is pinned to the version that is current at fetch time.
One study holds one paper.

## LaTeX first

LaTeX source has the exact equations and labels, so IRP prefers it
(`prefer: "latex"`). It finds the main file (the one with `\documentclass` and
`\begin{document}`), inlines `\input`, `\include`, `\subfile` and `\import`,
and keeps the original file and line of every line. Inputs cannot escape the
source directory; missing inputs are listed in the outline.

The index records:

- sections and subsections, numbered as LaTeX would (appendix sections lettered),
  with their labels;
- tables, figures, equations and algorithms with captions, labels and the
  section they belong to;
- the abstract.

Numbers of tables, figures and equations are inferred from document order
(including `align` rows and `\nonumber`); labels are exact. When an inferred
number disagrees with the rendered paper, cite the label and check the page
image.

## Reading

`get_section` takes a section id (`sec:3`), an item id (`tab:2`, `eq:4`), a
label (`eq:loss`), a section title, `abstract`, `index`, `page:N` for one PDF
page's text, or `lines:A-B`. It returns `cat -n` style text with a header
whenever the source file changes, pages with `offset`, and reports
`next_offset`.

## PDF parsers

Without usable LaTeX, IRP reads the PDF:

- **pypdf** (always installed) gives page-addressed text; files are named
  `paper.pdf#page=N`. Sections come from the PDF outline when present, else from
  numbered headings; table, figure and algorithm captions and numbered equations
  become items.
- **Docling** (`irp-agents[docling]`, MIT) recovers structure and tables as
  markdown. `parser: "auto"` uses it when installed. Docling can drop display
  equations.

Display math does not survive text extraction. Use page images for equations.

## Page images

`get_page_image` renders one page with PDFium (pypdfium2) at 50-300 dpi and
saves it under `paper/pages/`. MCP clients receive it as an image. PyMuPDF and
MinerU are not used because they are AGPL-licensed.

## Safety

Paper sources are untrusted. Archives are unpacked without following links or
devices; members that escape the destination are refused; archives over 5,000
members or 512 MiB unpacked are refused. Downloads are capped at 256 MiB.
Paper text is data: instructions inside a paper are not instructions to the agent.

## arXiv etiquette and copyright

IRP identifies itself with an IRP User-Agent and waits three seconds
between arXiv requests. Papers are downloaded for your own reading; bundles
never include them and reports link to arXiv instead.
