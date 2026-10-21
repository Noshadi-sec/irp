# Evidence and report

## The evidence log

`<study>/evidence.jsonl` gets one line per action. Each record's hash covers its
content and the previous record's hash, so any edit, deletion or reordering
breaks the chain. Reads (`get_section`, `get_page_image`, `run_status`,
`study_status`, `verify`, `list_claims`) do not write records.

`verify` recomputes the chain and every recorded file hash: the paper files,
lock files, run output streams, archived outputs and the latest report. Files
in `code/` that a later run overwrote are reported as informational, because
their archived copies are what counts.

## The report

`report` writes `report.md` (for people) and `report.json` (for programs) from
the log alone. It has five parts:

1. **Claim table**: every claim, where it appears, the paper's value, ours, and
   the verdict.
2. **Four verdicts**: reproduced, close, not reproduced, could not run; a
   shortened run or hand-typed number never counts.
3. **Guess list**: every detail the paper left out, the choice and why.
4. **Method map**: each equation or algorithm step linked to a file and line,
   flagged when that code changed after mapping.
5. **Provenance**: arXiv ID and version, file hashes, git commit, lock files,
   GPU, seeds, every command with its exit code, the evidence head hash, and the
   verify command.

## The completion gate

A final report needs: the paper fetched, at least one claim, a verdict for
every claim, measured verdicts backed by completed full-scope runs, and every
"could not run" carrying its blocking error. Recorded files must verify.
`report draft=true` writes `report.draft.md` while work continues.

Warnings do not block the report but appear in it: default success bars,
values not found in the paper text, claims recorded after code, no method map,
runs on uncommitted code.

## Sharing

`report bundle="/abs/new/dir"` copies the report, the evidence log, the code at
its git HEAD, lock files, run logs and archived outputs. The paper itself is
never included; the report links to it.
