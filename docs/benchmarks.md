# Benchmarks

Before launch, IRP publishes real numbers on public benchmarks, then shows
papers nobody has code for. Only about 19.5% of 2024 papers at top machine
learning conferences released code
([Paper2Code](https://arxiv.org/pdf/2504.17192v5)), so candidates for
showcases are plentiful.

## Benchmarks

| Benchmark | What is in it | How IRP uses it |
| --- | --- | --- |
| [Paper2Code dataset](https://huggingface.co/datasets/iaminju/paper2code) | 90 papers from ICML, NeurIPS and ICLR 2024 that have official code | Hide the code, rebuild from the paper, compare with the real code. The main test set. |
| [PaperBench](https://arxiv.org/html/2504.01848v2) | 20 ICML 2024 papers split into 8,316 graded tasks | Report the full version, which runs code and checks results, not the lighter Code-Dev score |
| [ResearchCodeBench](https://arxiv.org/html/2506.02314v1) | 212 coding tasks from 20 recent ML papers | Checks that core equations are implemented correctly |
| [SciReplicate-Bench](https://arxiv.org/abs/2504.00255v1) | 100 algorithm tasks from 36 NLP papers | Checks algorithm-level accuracy |

## Numbers published with each release

- Share of claims reproduced or close, on the Paper2Code set.
- Median cost and time per paper.
- Share of verdicts a human agrees with, from a spot-check of 50 claims.

Each number is computed from the studies' `report.json` files; the studies
themselves (bundles, without papers) are published so anyone can run `verify`.

## Golden papers

The golden set in [`benchmarks/golden/papers.json`](../benchmarks/golden/papers.json)
holds five light papers — official code exists, each runs on a CPU in minutes, at
least one numeric claim in a table, and a license that allows running the code:
Fashion-MNIST, KMNIST, MNIST-1D, fastText and QMNIST. Each was built from the paper
with the official code hidden (see [benchmarks/README.md](../benchmarks/README.md)),
and the verified bundles live in [`benchmarks/studies/`](../benchmarks/studies/).

Result across the five (8 claims, every number from a verified evidence log):
**6 reproduced, 1 close, 1 not reproduced — 87.5% reproduced or close**, ~160s and
$0 of paid compute per paper. Reproduce the summary with:

    uv run python benchmarks/summarize.py benchmarks/studies

`agreement_with_official_code` is reported once each study's `official.json` (the
official code's own numbers) is added.

## Choosing showcase papers

- Famous enough that people search for it, with no official code.
- Runs on one GPU in under a day.
- A result people can see: generated images, a curve, a demo.
- One honest case that did not reproduce, published only after contacting the authors.
