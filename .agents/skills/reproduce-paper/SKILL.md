---
name: reproduce-paper
description: Turn a research paper (arXiv ID, PDF or LaTeX) into working code with IRP, run it, and prove claim by claim how close it gets, with a verifiable evidence report. Use when asked to build, implement, reproduce, replicate or check a paper's results. Skip it for papers whose official code you are only asked to run unchanged.
metadata:
  version: "1"
---

# IRP: build any paper, prove every claim

You are the brain: you read the paper, write the code and decide the runs.
IRP's tools act and keep the receipts. Every action lands in a
hash-chained evidence log, and the report is written only from that log, so a
person can check every verdict without trusting you.

## Hard rules

These are enforced by the tools where they can be; follow them everywhere else.

1. **Never type, estimate or copy a number as a result.** Results come only from
   `extract_metrics` on a run's own output. The paper's numbers go only into
   `add_claim`.
2. **Never change the paper's method to make a run succeed.** When the paper
   leaves a detail out, choose, and record the choice with `add_guess`. When the
   environment forces a change (less memory, no GPU), record it with `add_note`
   kind `deviation`.
3. **Report "could not run" with the blocking error instead of pushing
   through.** Use `compare` with `could_not_run` and the exact error.
4. **Run the smallest faithful version first; shortened runs never count.**
   Faithful means the paper's configuration on its smallest reported setting
   (one seed, the smallest dataset or model the paper reports). Fewer steps or
   less data is `scope: "shortened"` and can only be context.
5. **Record every claim before writing any code.** `create_env` and `run` refuse
   until claims exist; claims added after code are flagged in the report.
6. **Ask before any paid compute.** Show the person the estimate from
   `run_remote` and wait for their answer. Never set budgets or prices yourself;
   only the person can, with `irp budget`.

Support computational papers only (machine learning, algorithms, simulations).
Decline wet-lab protocols and anything weapons-related. Never redistribute the
paper's PDF, its source or its datasets; link to them.

## Connect only when needed

If IRP tools are available, go straight to the paper. Do not run doctor or
setup before every task. If the tools are missing or a call is blocked, read
[connection and recovery](references/connection-and-recovery.md): diagnose with
`irp doctor --client <id> --json` (`claude_code`, `codex` or `cursor`),
plan a repair with `irp setup --client <id> --dry-run --json`, show the
person the exact changes, and apply only with their approval. Restart the agent
afterwards. Every tool also exists as a CLI command (`irp --help`), with
identical evidence.

## Workflow

Pick one study directory per paper (an absolute path the person agrees to,
e.g. `~/studies/<short-name>`). Pass it as `study` to every tool.

1. **Intake.** `fetch_paper` (arXiv ID, PDF URL or local path). Read
   `get_section` with `abstract`, then `index` for the outline, then the method
   and experiment sections. Use `get_page_image` for equations, figures and
   tables that text loses. See [paper intake](references/paper-intake.md).
2. **Claims.** Record every number you will try to reproduce with `add_claim`,
   before any code: the value exactly as printed, where it appears (with
   `source_file` and `source_line` from `get_section`), and a success bar the
   paper's variance supports. See [claims and verdicts](references/claims-and-verdicts.md).
3. **Plan and build.** Write the implementation in `<study>/code` with your
   normal editing tools. Record each missing detail with `add_guess` as you
   decide it. Map every equation and algorithm step with `map_method`.
4. **Environment.** `create_env` with `backend: "uv"`, or `"docker"` for code
   you do not trust (a virtual environment is not a sandbox). Pin versions in
   `code/requirements.txt`. See [environments and runs](references/environments-and-runs.md).
5. **Run.** `run` the smallest faithful configuration first with a seed. For
   anything longer than a few minutes, use `wait: false` and poll
   `run_status`. Fix bugs in your implementation and run again; never fix a run
   by changing the method.
6. **Measure.** `extract_metrics` from stdout or the files the run wrote. Print
   or save metrics in a parseable form (`test_acc: 0.938` or a JSON file).
7. **Judge.** `compare` each claim with its measurements (one per seed). Use
   `unit_scale` only for unit conversion (e.g. 100 for fraction to percent).
   For claims that cannot run here, `compare` with `could_not_run`, the reason
   and the blocking error.
8. **Report.** `report` writes `report.md` and `report.json`. It refuses until
   every claim has a verdict with evidence. `verify` rechecks the hash chain.

Use `study_status` whenever you resume or lose track; its `next` field names
the next step and its gate lists what still blocks the report.

## Work efficiently

Start with the outline and read only the sections you need. Page long sections
with `offset`. Do not repeat an identical run; reuse recorded measurements.
Prefer one clean full run per seed over many partial ones. Keep the person
informed at milestones (claims recorded, first run, verdicts), not after every
call.

## Finish the task

Tell the person the result line from the report, each verdict with its
evidence, and every guess and deviation. Say "not reproduced by this run", not
"the paper is wrong". Distinguish what was measured, what was guessed, and what
was not checked. Point them to `report.md` and the verify command. Before
anyone publishes a "not reproduced" result about a paper, the authors should be
contacted; record that with `add_note` kind `author_contact`.

## Read only the relevant guide

- [Paper intake](references/paper-intake.md): sources, sections, page images.
- [Claims and verdicts](references/claims-and-verdicts.md): choosing claims and success bars, the four verdicts.
- [Environments and runs](references/environments-and-runs.md): uv and Docker, seeds, long runs, paid GPUs.
- [Evidence and report](references/evidence-and-report.md): what the report proves and how to verify it.
- [Connection and recovery](references/connection-and-recovery.md): missing tools, setup, timeouts.
