# Roadmap

Five phases over about six months. Each phase ends with a gate, and the next
phase starts only when its gate passes. IRP goes public only at the v0.5
launch gate, when the showcases and benchmark numbers are ready.

## v0.1 Prototype (week 1)

- [x] Name, repository, MIT license.
- [x] `fetch_paper`, claims, uv environments, `run`, `extract_metrics`,
  `compare`, `report` on one laptop.
- [x] Hash-chained evidence log, `verify`, completion gate.
- [x] Offline golden study (the toy paper) with a hidden reference implementation.
- [ ] Reproduce a couple of papers end to end, to feel what good looks like.
- [ ] Three small papers that have official code and run on a CPU in under
  30 minutes, built from the paper with the official code hidden.

**Gate:** three papers end to end, numbers checked against the hidden code.

## v0.2 Agent-ready (weeks 2 to 4)

- [x] Skill with the hard rules; `setup` and `doctor` for Claude Code, Codex and Cursor.
- [x] Claims read from LaTeX and PDF; guess list; method map.
- [ ] The first 10 papers from the Paper2Code dataset.

**Gate:** the same results in three agents; ten papers reported.

## v0.3 GPU and trust (weeks 5 to 8)

- [x] Docker environments with mount verification and per-run network control.
- [x] Paid compute gate: person-set price and budget, estimate, approval, time limit.
- [ ] Modal GPU runs verified on a real account (the adapter exists and is experimental).
- [ ] Human spot-check of 50 verdicts, with the agreement rate published.

**Gate:** one GPU paper reproduced; spot-check agreement published.

## v0.5 Launch (weeks 9 to 12)

- [ ] Three showcases, each with its own repository and report: a famous paper
  without official code rebuilt and reproduced, one visible result, one honest
  miss published after contacting its authors.
- [ ] Website with guides and a gallery of reports.
- [ ] Full PaperBench and Paper2Code numbers.
- [ ] A 60-second demo video and a 20-second README GIF; a screenshot of a real report.
- [x] README in five languages (Chinese, Japanese, Korean, Spanish, Italian).
- [ ] Discord; official-sources notice everywhere the project is listed.

**Launch gate:** showcases and numbers ready, then go public on one day.

## v1.0 Grow (months 4 to 6)

- [ ] Community gallery and "Reproduced by IRP" badges for authors.
- [ ] Domain packs: vision, NLP, scientific machine learning.
- [ ] RunPod and Hugging Face Jobs providers.
- [ ] Weekly releases; a second maintainer.

## Admission criteria for new capabilities

New capabilities must record their actions as evidence, keep the hard rules
enforced, declare their effects truthfully, and pass their real-provider lane.
Anything that spends money or runs code outside the study needs a maintainer
scope decision first. See [tool design](tool-design.md).
