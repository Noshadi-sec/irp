# Evidence and report

The report is IRP's product: a person must be able to check every verdict
without trusting the agent. It is written only from the evidence log.

## The study directory

```text
<study>/
  irp.json     manifest: schema, study id, creation time (never a source of results)
  evidence.jsonl    hash-chained, append-only log: the only source of truth
  paper/            fetched paper, outline, page images (never redistributed)
  code/             the implementation, a git repository
  envs/<name>/      lock files, requirements snapshots, Dockerfiles
  runs/<id>/        stdout.txt, stderr.txt, archived small outputs, heartbeat
  report.md         for people
  report.json       for programs
```

## The evidence log

Every action that changes a study appends one JSON line. Reads (`get_section`,
`get_page_image`, `list_claims`, `run_status`, `study_status`, `verify`) append
nothing.

```json
{"actor":"mcp","data":{...},"hash":"sha256:…","prev":"sha256:…","schema":1,"seq":7,"ts":"2026-10-21T10:29:02.081Z","tool_version":"0.1.0","type":"claim.added"}
```

| Field | Meaning |
| --- | --- |
| `seq` | Position, from 0, with no gaps |
| `ts` | UTC time of the action |
| `type` | One of the record types below |
| `actor` | `cli`, `mcp`, or `runner` (a background run recording its own result) |
| `tool_version` | IRP version that wrote the record |
| `data` | The action's facts |
| `prev` | Hash of the previous record; the first record's is `sha256:` and 64 zeros |
| `hash` | SHA-256 of the canonical JSON of every other field |

Canonical JSON sorts keys, has no whitespace, and rejects NaN and infinity, so
equal facts always hash equally.

| Type | Written by | Data |
| --- | --- | --- |
| `study.created` | `fetch_paper` | study id, paper reference, layout, initial code commit |
| `paper.fetched` | `fetch_paper` | arXiv ID and version, title, authors, links, every paper file with its hash, the source tree digest, outline counts |
| `claim.added` | `add_claim` | claim id, statement, metric, value as printed and parsed, unit, location, success bar, paper check, recorded before code |
| `guess.added` | `add_guess` | what was missing, the choice, why, source, affected claims |
| `method.mapped` | `map_method` | paper element and index entry, code file and lines, the file's hash and commit |
| `note.added` | `add_note` | kind (limitation, deviation, not checked, author contact, other), text, claims |
| `env.created` | `create_env` | backend, Python, requirements hash, lock file and hash, tool versions, image and base digest for Docker |
| `run.started` | `run`, `run_remote` | command, environment, scope, seed, working directory, time limit, launcher, isolation, code commit; for paid runs the estimate and approval |
| `run.completed` | the run's owner | status, exit code, signal, times, peak memory, stdout and stderr hashes, every changed file with its hash and archive, hardware |
| `metrics.extracted` | `extract_metrics` | measurements with value, source file and hash, line or pointer, raw text |
| `verdict.recorded` | `compare` | claim, verdict, measurements, unit scale, mean and std, difference; or the could-not-run reason and blocking error |
| `budget.set`, `price.set` | `irp budget` (a person) | amount or price, whether set at an interactive terminal |
| `report.written` | `report` | final or draft, report file hashes, summary, evidence head |

## Verification

`irp verify` (or the `verify` tool):

1. re-derives every record's hash and checks `seq` and `prev` links, naming
   each broken line;
2. rehashes every file the log vouches for: paper files and the source tree,
   lock files and Dockerfiles, run stdout and stderr, archived outputs, and the
   latest report.

A file in `code/` that a later run overwrote is informational: the archived
copy under `runs/<id>/outputs/` is what counts. In a bundle, the missing paper
is informational by design.

IRP refuses to append to a log that fails verification and never repairs
one. The chain proves that a log was not edited after the fact; it does not
stop someone from rewriting a whole study. Publish the evidence head hash with
a report when that matters.

## The completion gate

A final report requires:

- the paper fetched and at least one claim;
- a current verdict for every claim;
- every reproduced, close or not-reproduced verdict backed by measurements from
  full-scope runs that exited 0;
- every could-not-run verdict carrying its blocking error;
- every recorded file verifying.

`report draft=true` writes `report.draft.md` and `report.draft.json` before
the gate passes. Warnings never block a report but appear in it: default
success bars, values not found in the paper text, claims recorded after code,
no method map, mapped code that changed, runs on uncommitted code, runs still
in progress.

## The report

`report.md` has the five parts every reader needs:

1. **Claim table**: claim, where it appears, the paper's value, ours (mean,
   seeds and std), and the verdict. "Not reproduced" always reads "not
   reproduced by this run".
2. **Evidence per claim**: where the paper prints the value, the success bar,
   each measurement with its run, seed, file and line, the unit scale, the
   difference, and superseded verdicts.
3. **Guesses**: every missing detail, the choice and why.
4. **Method map**: each equation or algorithm step and its code lines, flagged
   when the code changed after mapping.
5. **Provenance**: arXiv ID and version, file hashes, the code commit for each
   group of runs, environments and lock hashes, GPUs, seeds, commands with exit
   codes, paid compute, the evidence head and the verify command.

`report.json` holds the same content with every field, under `schema: 1`.

## Bundles

`report bundle="/abs/new/dir"` copies the report, the evidence log, the
manifest, the code at its git HEAD, lock files, Dockerfiles, run logs and
archived outputs, plus `bundle.json` naming what was excluded. The paper is
never included.
