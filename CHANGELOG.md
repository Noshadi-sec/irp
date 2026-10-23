# Changelog

## [0.7.0](https://github.com/Noshadi-sec/irp/compare/irp-agents-0.6.0...irp-agents-0.7.0) (2026-10-23)


### Tests

* add the golden benchmark — five papers with verified study bundles ([a64cab3](https://github.com/Noshadi-sec/irp/commit/a64cab3d02aac5c6d0759d6dc72be41069dd3e83))

## [0.6.0](https://github.com/Noshadi-sec/irp/compare/irp-agents-0.5.0...irp-agents-0.6.0) (2026-10-21)


### IRP

* build any paper, prove every claim ([0428743](https://github.com/Noshadi-sec/irp/commit/0428743f0d5de25281d9de330f725e2f9559d3ef))

## [0.5.0](https://github.com/Noshadi-sec/irp/compare/irp-agents-0.4.0...irp-agents-0.5.0) (2026-10-21)


### Bug Fixes

* shorten the MCP Registry description to its 100-character limit ([e31d124](https://github.com/Noshadi-sec/irp/commit/e31d1248648faf119a28a137714339db6996ff8a))

## [0.4.0](https://github.com/Noshadi-sec/irp/compare/irp-agents-0.3.0...irp-agents-0.4.0) (2026-10-21)


### Bug Fixes

* make release qualification independent of the version number ([f5db418](https://github.com/Noshadi-sec/irp/commit/f5db4187a628fd070ec371a45850664b2fcf58c2))

## [0.3.0](https://github.com/Noshadi-sec/irp/compare/irp-agents-0.2.0...irp-agents-0.3.0) (2026-10-21)


### Bug Fixes

* keep the version out of the generated tool catalog ([f029c27](https://github.com/Noshadi-sec/irp/commit/f029c2753ff376d6e1554e9b7a78b585c879276f))

## [0.2.0](https://github.com/Noshadi-sec/irp/compare/irp-agents-0.1.0...irp-agents-0.2.0) (2026-10-21)


### Features

* IRP 0.1.0 — build any paper, prove every claim ([d26c22e](https://github.com/Noshadi-sec/irp/commit/d26c22e98f99299127b2250ad5cd5dd994b65c4e))

## 0.1.0 (unreleased)

### Highlights

- Build a paper from its arXiv LaTeX source or PDF and prove each claim with a hash-chained evidence log and a report written only from that log.

### Changes

- **Intake:** `fetch_paper` reads arXiv LaTeX source first (exact equations, file and line for every line), falls back to the PDF, and renders page images for math and figures.
- **Claims and plan:** `add_claim` checks that each value is printed in the paper; `add_guess`, `map_method` and `add_note` record missing details, code links and deviations.
- **Build and run:** uv and Docker environments with lock files; runs record exit code, time, peak memory, seed, the code commit and every file written; background runs with `run_status`.
- **Judge and report:** `extract_metrics` reads numbers only from a run's own output; `compare` gives one of four verdicts; `report` enforces the completion gate; `verify` rechecks every hash.
- **Paid compute:** experimental Modal sandboxes behind a person-set price, budget and approval.
- **Setup:** `setup`, `doctor`, `update` and `uninstall` for Claude Code, Codex and Cursor, with plans, backups and the bundled `reproduce-paper` skill.
