# Paper intake

## Sources, best first

1. **arXiv LaTeX source.** `fetch_paper` with an arXiv ID (`2501.12345`) or URL
   downloads the source the authors uploaded. Equations, tables and labels are
   exact, and every line keeps its file and line number.
2. **PDF.** Papers without source, or `prefer: "pdf"`, are read from the PDF.
   pypdf is always available; Docling (`irp-agents[docling]`) recovers better
   structure when installed. PDF text loses display math.
3. **Page images.** `get_page_image` renders one PDF page as PNG. Use it for
   equations, plots and dense tables. Raise `dpi` (up to 300) for small math.

Unversioned arXiv IDs are pinned to the latest version at fetch time; the
report names the exact version. A study holds one paper; use a new study
directory for another paper or version.

## Reading

- `get_section id="abstract"`, then `id="index"` for every section, table,
  figure, equation, algorithm and LaTeX label.
- Read by id (`sec:3`, `sec:3.2`, `tab:2`, `eq:4`, `alg:1`), by label
  (`eq:loss`, `tab:main`), or by title (`Experiments`).
- `lines:120-180` reads flattened line numbers; `page:5` reads one PDF page's
  text.
- Long selections page with `offset`; `next_offset` tells you where to resume.

Output looks like `cat -n` with a header whenever the source file changes:

```text
== sections/method.tex ==
   12  \begin{equation}\label{eq:loss}
   13    \mathcal{L} = \dots
```

Use exactly that file and line in `add_claim` (`source_file`,
`source_line`) and in your method notes.

Item numbers (Table 2, Eq. 4) are inferred from document order; labels are
exact. When an inferred number disagrees with the rendered paper, trust the
page image and cite the label.

## Appendices and supplements

Hyperparameters often live in the appendix. Read it before deciding a detail is
missing. A detail that only appears in the official code is still "missing from
the paper": record it with `add_guess` and cite where you found it.
