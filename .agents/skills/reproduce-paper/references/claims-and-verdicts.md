# Claims and verdicts

## Choose claims

Record every number you intend to check, before writing code:

- Headline results the person asked about (for "check Table 2", every cell you
  will reproduce from Table 2).
- The paper's own baseline numbers when you will rerun the baseline.
- Qualitative claims only when they have a number (a speed-up, a ratio).

A claim's `value` is the paper's number exactly as printed (`94.1%`, `0.31`,
`2.0x`). Give `where` as a reader would say it (`Table 2, row 3`) and the
`source_file`/`source_line` from `get_section`; IRP checks that the value
is printed there and flags it when it is not.

## Set the success bar

The bar decides "reproduced" and "close". State it from the paper's own
variance whenever possible:

| Situation | Bar |
| --- | --- |
| Paper reports mean ± std over seeds | `tolerance_abs` = the std; `close_abs` = 2-3 std |
| Accuracy-like metric, no variance given | `tolerance_rel` 0.01, `close_rel` 0.03-0.05 |
| Loss or error where lower is better and the claim is a bound | `comparator: "at_most"` |
| Speed-up or "at least" claim | `comparator: "at_least"` |

Without a bar, IRP uses 1% relative (reproduced) and 5% (close) and labels
it as a default convention, not a statistical test. `seeds_in_paper` records
how many runs the paper averaged, so the report can show when you used fewer.

## The four verdicts

| Verdict | Means |
| --- | --- |
| reproduced | The mean of full-scope measurements is within the reproduced bar. |
| close | Outside the reproduced bar, within the close bar. |
| not reproduced | Outside both bars. The report says "not reproduced by this run". |
| could not run | The faithful configuration could not run here; the blocking error is recorded. |

`compare` refuses:

- measurements from `shortened` or `smoke` runs (rule 4); pass them as
  `context_measurement_ids` on a `could_not_run` verdict instead;
- measurements from runs that did not exit 0 (rule 3);
- two measurements from the same run;
- a `unit_scale` that is not a power of ten.

A later `compare` for the same claim supersedes the earlier verdict; the report
keeps the history, so do not re-judge until the result looks better.

## Could not run

Use it when the paper's configuration is out of reach (8 GPUs for 2 days, a
dataset behind a license you do not have, a dependency that will not install).
Give a short `reason` and the exact `blocking_error`. Never substitute a smaller
model and call it reproduced.
