# Benchmarks

How IRP is measured. See [docs/benchmarks.md](../docs/benchmarks.md) for
the benchmark list and the numbers each release publishes.

## Protocol: rebuild with the official code hidden

For each paper with official code (the golden papers and the Paper2Code set):

1. Create a study from the paper alone: `irp fetch <arXiv ID> --study <dir>`.
   Do not give the agent the official repository, and do not install it in the
   environment the agent uses.
2. Ask the agent: "Build arXiv <ID> and check <table or claims>." Record the
   agent, model and IRP version.
3. Let the agent finish: every claim needs a verdict, and `irp report`
   must pass the completion gate.
4. Separately, run the official code on the same claims and record its numbers
   in `official.json` beside the study: `{"c1": 94.0, "c2": 0.31}`.
5. Bundle the study (`irp report --bundle`), never including the paper.

## Summarize

```bash
uv run python benchmarks/summarize.py path/to/studies [--spot-check spot-check.csv]
```

The summary reports, from each study's `report.json` and `evidence.jsonl`:

- the share of claims reproduced or close;
- the verdict counts;
- median wall time per paper (sum of run durations) and median paid compute;
- agreement with a human spot-check, when a CSV of `study,claim_id,human_verdict`
  is given;
- agreement with the hidden official code, when `official.json` files exist
  (whether our number lands within the claim's own bar around the official number).

Every number comes from verified evidence: studies that fail `verify` are
listed and excluded.

## Golden papers

`golden/papers.json` lists five light papers (official code exists, each runs on a
CPU in minutes, a numeric table claim, a permissive license) and why each was
chosen: Fashion-MNIST, KMNIST, MNIST-1D, fastText and QMNIST. Their verified bundles
are in `studies/`. Summarize them with:

    uv run python benchmarks/summarize.py benchmarks/studies

Current result: 8 claims across the five — 6 reproduced, 1 close, 1 not reproduced
(87.5% reproduced or close). The `official.json` files (the official code's own
numbers) are not added yet, so agreement-with-official is not reported.
