<!-- mcp-name: io.github.Noshadi-sec/irp -->
<div align="center">

**English** · [简体中文](docs/readme/README_zh.md) · [日本語](docs/readme/README_ja.md) · [한국어](docs/readme/README_ko.md) · [Español](docs/readme/README_es.md) · [Italiano](docs/readme/README_it.md)

# IRP: Build any paper. Prove every claim.

### One MCP server and CLI that lets your coding agent turn a research paper into working code, run it, and prove claim by claim how close it gets.

**Give it a paper. Get back working code and a report you can check without trusting the agent.**

[![PyPI version](https://img.shields.io/pypi/v/irp?style=flat-square&color=3775a9)](https://pypi.org/project/irp-agents/)
[![MCP tool catalog](https://img.shields.io/badge/MCP-tool_catalog-5c4ee5?style=flat-square)](docs/mcp-contracts.md#generated-catalog)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#what-you-can-reproduce)
[![MIT license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](LICENSE)

[Quick start](#quick-start) · [How IRP works](#how-irp-works) · [The report](#the-report) · [What you can reproduce](#what-you-can-reproduce) · [FAQ](#faq) · [Documentation](#documentation)

<code>uvx irp-agents setup</code>

</div>

> [!IMPORTANT]
> Get IRP from [Noshadi-sec/irp](https://github.com/Noshadi-sec/irp) or the
> [irp-agents package on PyPI](https://pypi.org/project/irp-agents/). Follow the
> installation and release links from these official sources. A similar
> repository name or copied README does not establish that a download is official.

<div align="center">

<br />

<img src="docs/assets/irp-flow.svg" alt="IRP flow: you ask your agent to build a paper; the agent reads the paper, records claims, writes code and decides runs through IRP's tools; IRP fetches the paper, runs the code and logs every step in a hash-chained evidence log; the report is written from that log." width="900" />

<br /><br />

</div>

---

Found a paper with no code, or code you cannot trust? Ask your agent to build
it with IRP. The agent reads the paper, records every number it claims,
writes the implementation, runs it and compares the results. IRP does the
fetching, running and record keeping, and refuses the shortcuts: a number typed
by hand never counts, a shortened run never counts, and the report is written
only from the evidence log.

IRP connects your agent (Claude Code, Codex or Cursor) to tools for paper
intake, environments, runs, measurements and verdicts. You can use the same
tools from your terminal. Everything runs locally; IRP never calls a model,
and data goes only where you send it.

## Quick start

### Set up your agent

With [uv](https://docs.astral.sh/uv/) installed, run:

```bash
uvx irp-agents setup
```

Choose your agents, review the proposed changes, and approve them. Setup adds
IRP's MCP server and its workflow skill, with backups of existing
configuration. Restart your agent afterward.

Setup supports Claude Code, Codex and Cursor. Other MCP clients can use
[manual registration](docs/installation.md#manual-registration).

### Ask your agent

```text
Build arXiv 2501.12345 and check Table 2.
```

You get back a working code folder plus a report: every claim, the paper's
number, your number, and a verdict.

### Use the terminal

Every tool is also a command. Fetch a paper into a new study and read its
outline:

```bash
irp fetch 2501.12345 --study ~/studies/example
irp section index --study ~/studies/example
```

To install the `irp` command for regular use:

```bash
uv tool install irp-agents
irp --help
```

See the [CLI guide](docs/cli.md) for the full workflow from the terminal.

### Check readiness

```bash
irp doctor
```

Doctor checks Python, uv, git, Docker, GPUs, disk space and your agents'
registrations, and changes nothing.

### Update IRP

IRP changes quickly. For an installed command:

```bash
irp update
```

With uvx, refresh your agent setup with `uvx irp-agents@latest setup`, review the
plan, and restart your agent.

## How IRP works

Your agent thinks; IRP acts and keeps the receipts. The agent reads the
paper, writes code and decides what to run. Every action goes through one core,
so the CLI and the MCP server behave the same, and every step lands in an
append-only, hash-chained evidence log. The report is built from that log alone.

| Stage | Tool | What it does |
| --- | --- | --- |
| Intake | `fetch_paper` | Downloads the arXiv LaTeX source or the PDF, hashes it, splits it into sections |
| Intake | `get_section`, `get_page_image` | Returns one section's text with file and line numbers, or one page as an image for equations and figures |
| Claims | `add_claim`, `list_claims` | Records each claim: metric, value, where it appears, and the success bar |
| Plan | `add_guess` | Records a missing detail, the choice made, and why |
| Plan | `map_method` | Links an equation or algorithm step to a file and line |
| Build | `create_env` | Makes a uv environment or Docker image and writes the lock file |
| Run | `run`, `run_status` | Runs one command; saves output, exit code, time, memory, seed, commit and files |
| Run | `run_remote` | Same on a paid GPU provider, after a cost estimate and approval |
| Measure | `extract_metrics` | Pulls numbers from logs and result files, with file and line |
| Judge | `compare`, `add_note` | Puts claim and measurement side by side and gives one of four verdicts |
| Report | `report`, `verify`, `study_status` | Writes report.md and report.json from the log; rechecks the hash chain |

The workflow skill gives the agent six hard rules, and the tools enforce them
wherever they can:

1. Never type, estimate or copy a number as a result.
2. Never change the paper's method to make a run succeed; record a guess instead.
3. Report "could not run" with the blocking error instead of pushing through.
4. Run the smallest faithful version first; shortened runs never count.
5. Record every claim before writing any code.
6. Ask before any paid compute.

## The report

The report is the product: a person must be able to check every verdict
without trusting the agent. It has five parts: the claim table, four verdicts
(reproduced, close, not reproduced, could not run), the guess list, the method
map from equations to code lines, and provenance (arXiv ID and version, file
hashes, git commit, lock files, GPU, seeds, every command with its exit code,
and a verify command that rechecks the hash chain).

The agent cannot finish until every claim has a verdict with evidence.

Example `report.md` (made-up numbers):

```markdown
# Reproduction report: Example Paper (arXiv 2501.12345v2)

Result: 2 reproduced, 1 close, 1 could not run (of 4 claims)

| Claim | Where | Paper | Ours | Verdict |
| --- | --- | --- | --- | --- |
| c1 Test accuracy | Table 2, row 3 | 94.1% | 93.8% (3 seeds, std 0.2) | close |
| c2 Training loss | Figure 4 | 0.31 | 0.31 (3 seeds) | reproduced |
| c3 Speed-up | Section 5.2 | 2.0x | 2.1x | reproduced |
| c4 ImageNet top-1 | Table 3 | 81.2% | not run: needs 8 GPUs for 2 days | could not run |

## Guesses
- g1 Warmup length not stated: used 5 epochs. Why: as in cited paper [12].

## Method map
- Eq. 3 (loss) -> code/src/loss.py:41
- Algorithm 1, line 4 -> code/src/train.py:88

## Provenance
- Paper: arXiv 2501.12345v2, source and PDF hashes
- Code: git commit 3f2a9c1 (clean)
- Commands logged: 37, 37 with an exit code
- Evidence log: 112 records, head sha256:…, verified
- Verify: `irp verify --study ~/studies/example`
```

See [evidence and report](docs/evidence-and-report.md) for every field.

<a id="what-you-can-reproduce"></a>

## What you can reproduce

IRP requires Python 3.11+ on macOS or Linux. Additional tools depend on
the paper:

| Need | What IRP uses | Requirements and guide |
| --- | --- | --- |
| Paper intake | arXiv LaTeX source first, the PDF as fallback, page images for math and figures | Network access to arXiv; [paper intake](docs/paper-intake.md) |
| Better PDF structure | Docling for text and tables | Optional `irp-agents[docling]`; [paper intake](docs/paper-intake.md#pdf-parsers) |
| Environments | uv virtual environments with lock files, or Docker images for isolation | uv, or Docker; [environments](docs/environments.md) |
| Compute | Your CPU or GPU; Modal GPU sandboxes after a cost estimate and approval (experimental) | Optional `irp-agents[modal]`; [compute](docs/compute.md) |
| Agents | Claude Code, Codex, Cursor; any MCP client by hand | [installation](docs/installation.md) |

IRP supports computational papers: machine learning, algorithms and
simulations. It does not support wet-lab work or anything weapons-related.

## Benchmark

Five light papers — official code exists, each runs on a CPU in minutes — rebuilt
from the paper alone and checked claim by claim. Every number comes from a verified
evidence log; re-check any study with `irp verify --study benchmarks/studies/<name>`.

| Paper | Claims | Result |
| --- | --- | --- |
| [Fashion-MNIST](benchmarks/studies/fashion-mnist/report.md) (1708.07747) | 3 | 1 reproduced, 1 close, 1 not reproduced |
| [KMNIST](benchmarks/studies/kmnist/report.md) (1812.01718) | 2 | both reproduced |
| [MNIST-1D](benchmarks/studies/mnist-1d/report.md) (2011.14439) | 1 | reproduced |
| [fastText](benchmarks/studies/fasttext/report.md) (1607.01759) | 1 | reproduced (92.86% vs 92.5%) |
| [QMNIST](benchmarks/studies/qmnist/report.md) (1905.10498) | 1 | reproduced (2.95% vs 2.95%) |

Across 8 claims: **6 reproduced, 1 close, 1 not reproduced (87.5% reproduced or
close)**, ~160s and $0 of paid compute per paper. Selection criteria and the full
set are in [benchmarks/golden/papers.json](benchmarks/golden/papers.json); the
protocol and `summarize.py` are in [benchmarks/](benchmarks/).

If you build a paper with IRP, share the report in an
[issue](https://github.com/Noshadi-sec/irp/issues) with the paper, your
question, and what you found.

## FAQ

<details>
<summary><strong>Which agents can use IRP?</strong></summary>

Any agent that supports local MCP servers. Setup configures Claude Code, Codex
and Cursor; other clients can use
[manual registration](docs/installation.md#manual-registration).

</details>

<details>
<summary><strong>Does IRP call an AI model or upload my paper?</strong></summary>

No. Your agent is the brain; IRP never calls a model and has no API key.
It downloads papers from arXiv, installs packages through uv or Docker, and
runs code on your machine. Your agent receives the tool results, and its model
provider has its own data policy.

</details>

<details>
<summary><strong>Is running a paper's code safe?</strong></summary>

Running code is running code. A uv virtual environment is not a sandbox: the
code runs with your permissions. Use `create_env` with `backend: "docker"` for
code you did not write or do not trust, and runs mount only the study's code
directory. See [security](SECURITY.md).

</details>

<details>
<summary><strong>What does "not reproduced" mean?</strong></summary>

That this run, with the recorded guesses, did not reach the paper's number
within the stated bar. The report says "not reproduced by this run" and lists
every guess. It is evidence about one attempt, not a verdict on the paper;
contact the authors before publishing it.

</details>

<details>
<summary><strong>The paper has official code. Should I use IRP?</strong></summary>

IRP builds missing code from the paper. To check that existing code
reproduces its README's numbers, a tool such as
[paper-repro](https://pypi.org/project/paper-repro/) fits better. IRP is
still useful for testing a paper by hiding its code and comparing your rebuild
with it afterwards.

</details>

<details>
<summary><strong>Can IRP spend money?</strong></summary>

Only on paid GPU providers, only after you record a price and a budget at a
terminal with `irp budget`, and only after you approve the estimate the
agent shows you. The run's time limit equals the estimated hours.

</details>

<details>
<summary><strong>What should I do if I hit a bug?</strong></summary>

Update first; a recent release may already fix it (`irp update`, or
`uvx irp-agents@latest setup`). If the problem persists, [open an
issue](https://github.com/Noshadi-sec/irp/issues) with your IRP version,
the `irp doctor --json` output, the steps to reproduce and the error.

</details>

## Documentation

- [Installation and setup](docs/installation.md): agent registration, updates and uninstall.
- [CLI](docs/cli.md): every command, output and exit status.
- [MCP contracts](docs/mcp-contracts.md) and [agent prompts](docs/mcp-prompts.md): tool results, errors and the [generated tool catalog](docs/mcp-contracts.md#generated-catalog).
- [Evidence and report](docs/evidence-and-report.md): the log, the gate, verification.
- [Paper intake](docs/paper-intake.md), [environments](docs/environments.md) and [compute](docs/compute.md).
- [Benchmarks](docs/benchmarks.md): how IRP is measured.
- [Roadmap](docs/roadmap.md): v0.1 to v1.0 and the gates between them.

Report vulnerabilities through [SECURITY.md](SECURITY.md).

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md) for responsible-use guidance. IRP is for
lawful research, education and the verification of published computational
work. A "not reproduced" verdict is evidence about one run, not a judgment of
the paper or its authors.

## Contributing

Contributions are welcome. [Open an issue](https://github.com/Noshadi-sec/irp/issues)
to report a bug or suggest a feature, or
[send a pull request](https://github.com/Noshadi-sec/irp/pulls).

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and checks,
[testing](docs/testing.md) for verification lanes, and the
[architecture map](docs/architecture.mermaid) for the project structure.

## License

[MIT](LICENSE)

IRP-authored code is licensed under MIT. Third-party material retains its
own licenses and notices; see [Third-party notices](THIRD_PARTY_NOTICES.md).
Papers and datasets keep their authors' licenses; IRP never redistributes
them.
