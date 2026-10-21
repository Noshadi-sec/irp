# Environments and runs

## Environments

- `create_env backend="uv"`: a pinned virtual environment and `lock.txt`. Fast.
  It is not a sandbox: the paper's code runs with the person's permissions.
- `create_env backend="docker"`: an image built from a generated Dockerfile;
  runs mount only `code/`. Use it for code you did not write or do not trust,
  and pass `network: false` on runs that need no downloads.
- Environments are never rebuilt in place; create `main2` when requirements
  change so earlier runs keep their lock.
- IRP reuses the person's uv and Docker. It never installs them.

Put exact versions in `code/requirements.txt` (`torch==2.5.1`), not ranges.

## Runs

`run` executes one shell command in `code/` and records the command, exit code,
time, peak memory, seed, the git commit of `code/` (committed automatically
before the run), and the hash of every file the run creates or changes. Small
text outputs (JSON, CSV, logs up to 10 MiB) are archived under `runs/<id>/`.

- **Scope.** `full` is the faithful configuration and the only scope that
  counts. Use `smoke` for a quick crash check and `shortened` for fewer steps;
  neither can support a verdict.
- **Seeds.** Pass `seed`; IRP exports `IRP_SEED` and
  `PYTHONHASHSEED`. Make the code read the seed and seed every RNG it uses.
- **Long runs.** Clients stop waiting on a tool call after their own timeout.
  For anything longer than a few minutes, `run` with `wait: false` and poll
  `run_status wait_s=600`. One run at a time per study.
- **Logs.** Print metrics as `name: value` or write a JSON results file;
  `extract_metrics` reads both. Print progress so `run_status` tails are useful.

## When a run fails

Read `stderr_tail`. If your implementation has a bug, fix it and run again
(that is engineering, not changing the method). If the paper's method cannot
run here, record `could_not_run` with the blocking error. If the environment
forces a change (smaller batch for memory, CPU instead of GPU), record it with
`add_note kind="deviation"` and say which claims it affects.

## Paid GPUs

`run_remote` (Modal today; experimental) needs three things from the person:

1. a price per GPU-hour recorded with `irp budget price` (IRP ships
   no price list);
2. a budget recorded with `irp budget set`;
3. their approval of the estimate you show them.

The first call without `approved` returns the estimate. Show it, ask, and call
again with `approved: true` only after a clear yes. The time limit equals the
estimated hours, so GPU time cannot exceed the estimate. Budget and price
commands need a person at a terminal; never run them yourself.
