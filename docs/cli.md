# CLI

Every MCP tool is also a command, backed by the same core: a study built from
the terminal and one built by an agent produce identical evidence (the log
records `actor: "cli"` or `"mcp"`). `--study` defaults to the current
directory. `--json` prints JSON; otherwise output is readable text.

## A study from the terminal

```bash
S=~/studies/linear-trend
irp fetch 2501.12345 --study $S
irp section abstract --study $S
irp section index --study $S
irp section tab:main --study $S

irp claim add --study $S --statement "Slope estimate" --metric slope \
  --value "2.00" --where "Table 1, row 1" --source-file main.tex --source-line 41 \
  --tol-abs 0.01 --close-abs 0.03 --seeds-in-paper 3

# write the implementation in $S/code, then:
irp guess add --study $S --missing "Sampling order not stated" \
  --choice "train then test from one generator" --why "unstated in the paper" --claim c1
irp map --study $S --element "Eq. 3 (closed-form slope)" --paper-ref eq:closed --file ols.py --line 18
irp env create --study $S --python 3.11

irp run --study $S --seed 0 -- python ols.py
irp run --study $S --seed 1 -- python ols.py
irp run --study $S --seed 2 -- python ols.py

irp metrics r1 --study $S --key slope      # m1
irp metrics r2 --study $S --key slope      # m2
irp metrics r3 --study $S --key slope      # m3
irp compare c1 --study $S -m m1 -m m2 -m m3

irp report --study $S
irp verify --study $S
```

## Commands

| Command | Tool | Notes |
| --- | --- | --- |
| `fetch PAPER` | `fetch_paper` | `--prefer latex\|pdf`, `--parser auto\|pypdf\|docling`, `--no-pdf` |
| `section ID` | `get_section` | `--offset`, `--max-lines` |
| `page N` | `get_page_image` | `--dpi` |
| `claim add` / `claim list` | `add_claim` / `list_claims` | Bars: `--tol-rel`, `--tol-abs`, `--close-rel`, `--close-abs`, `--comparator` |
| `guess add` | `add_guess` | `--claim` is repeatable |
| `map` | `map_method` | `--element`, `--file`, `--line`, `--end-line`, `--paper-ref` |
| `note add` | `add_note` | `--kind limitation\|deviation\|not_checked\|author_contact\|other` |
| `env create` | `create_env` | `--backend uv\|docker`, `--python`, `--requirements`, `--package`, `--base-image`, `--system-package`, `--gpu` |
| `run -- COMMAND` | `run` | `--env`, `--no-env`, `--scope`, `--seed`, `--cwd`, `--timeout`, `--detach`, `--no-network`, `--memory`, `--no-commit` |
| `run-status RUN` | `run_status` | `--wait SECONDS`, `--tail LINES` |
| `run-remote -- COMMAND` | `run_remote` | `--gpu`, `--hours`, `--gpu-count`, `--approve`, `--output` |
| `metrics RUN` | `extract_metrics` | One spec with `--key`/`--regex`/`--json-pointer`/`--csv-column`, or `--specs-json` |
| `compare CLAIM` | `compare` | `-m` per measurement, `--unit-scale`, `--could-not-run --reason --blocking-error --failed-run`, `--context` |
| `report` | `report` | `--draft`, `--bundle DIR` |
| `verify` | `verify` | Exit 1 when verification fails |
| `status` | `study_status` | What is recorded and what blocks the report |
| `tools` | | The catalog |
| `call TOOL --input JSON` | any | The exact MCP input; `--input @file.json` reads a file |
| `budget show\|set\|price` | | Paid compute; `set` and `price` need a person at a terminal |
| `setup` | | See [installation](installation.md) |
| `doctor` | | Read-only readiness |
| `update` | | Upgrade the owning installation |
| `uninstall` | | Remove IRP-owned registrations and skills |
| `mcp` | | Serve MCP over stdio |

## Output and exit status

Results go to stdout; prompts, progress and logs go to stderr. With `--json`, a
failure prints `{"error": {...}}`, the same diagnostic MCP returns.

| Status | Meaning |
| --- | --- |
| `0` | The command completed. A run that exited non-zero is still a completed `run` command; read its `status`. |
| `1` | The command failed: a typed error, a refused rule, failed verification, or setup needing confirmation or repair. |
| `2` | Invalid command-line usage. |
| `130` / `143` | Interrupted by SIGINT / SIGTERM. A foreground run is stopped and recorded as `cancelled`. |

`IRP_LOG_LEVEL` (`debug`, `info`, `warning`, `error`, `silent`) enables
logs on stderr; an invalid value stops every command except `doctor`, which
reports it.
