# Compute

## Local runs

`run` executes one shell command in `code/` (or `cwd` inside it). IRP:

- commits `code/` first (with IRP's own identity and no hooks), so the
  report names the exact code; files a run creates are kept out of later
  commits through `.git/info/exclude` and archived under the run instead;
- sets `IRP_SEED` and `PYTHONHASHSEED` from `seed`, `IRP_RUN_ID`, and
  `PYTHONUNBUFFERED=1`;
- writes stdout and stderr to `runs/<id>/` as the command prints them;
- stops the whole process group at the time limit (SIGTERM, then SIGKILL after 10 seconds);
- records the exit code or signal, wall time, peak resident memory (POSIX),
  hardware, and the hash of every file the run created or changed; text files
  up to 10 MiB are archived under `runs/<id>/outputs/`.

One run executes at a time per study, so changed files are attributed to the
right run.

### Scopes

| Scope | Use | Counts toward a verdict |
| --- | --- | --- |
| `full` | The paper's configuration on its smallest reported setting | Yes, when it exits 0 |
| `shortened` | Fewer steps, epochs or examples | Never |
| `smoke` | A quick crash check | Never |

### Long runs

Agent clients stop waiting after their own tool timeout. For anything longer
than a few minutes, call `run` with `wait: false`: a detached runner process
executes the recorded run and writes the result itself, beating a heartbeat
file every five seconds. Poll with `run_status` (`wait_s` up to 600). A run
whose heartbeat stops for 90 seconds without a result is recorded as lost; its
command may still be running.

## Paid GPUs: run_remote

`run_remote` runs one command on a paid provider. Modal is available
(experimental); RunPod and Hugging Face Jobs are planned.

Three things come from a person, never from the agent:

1. **A price.** IRP ships no price list, because prices change. Read the
   provider's pricing page and record it:

   ```bash
   irp budget price --study ~/studies/x --provider modal --gpu A10G --usd-per-hour <price>
   ```

2. **A budget**, a hard cap for the study:

   ```bash
   irp budget set --study ~/studies/x --usd 25
   ```

   Both commands ask for confirmation at a terminal and refuse to run without
   one (for CI only, `IRP_ALLOW_NONINTERACTIVE_BUDGET=1`). There is no MCP
   tool for either.

3. **Approval of the estimate.** The first `run_remote` call returns
   `needs_confirmation` with the estimate (price x GPUs x hours). The agent
   shows it to the person and calls again with `approved: true` only after a
   clear yes.

The run's time limit equals the estimated hours, so billed GPU time cannot
exceed the estimate. Image builds, storage and provider minimums are billed by
the provider separately. Committed spend counts the estimate of every started
paid run.

### Modal

Install `irp-agents[modal]` and authenticate (`modal setup`). IRP runs the
Modal SDK in a child process, builds an image from the environment's Python
version and requirements, uploads `code/`, executes the command in a
`modal.Sandbox` with the requested GPU, and copies back the files listed in
`outputs`. No real-provider verification of this adapter is recorded yet; treat
it as experimental.

## Isolation summary

| Where | Isolation recorded | Notes |
| --- | --- | --- |
| uv or host | `none` | Your permissions, your network |
| Docker | `container` | Only `code/` mounted; optional `--network none` |
| Modal | `cloud-sandbox` | The provider's sandbox; `code/` is uploaded |
