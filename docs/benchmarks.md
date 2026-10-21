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

The v0.1 gate needs three small papers with official code that run on a CPU in
under 30 minutes. Choose them by:

- official code exists, so the hidden reference can be compared afterward;
- a CPU run under 30 minutes on a laptop;
- at least one numeric claim in a table;
- a license that allows running the code.

Record the selection in `benchmarks/golden/papers.json`, then build each paper
with the official code hidden, as described in
[benchmarks/README.md](../benchmarks/README.md).

## Choosing showcase papers

- Famous enough that people search for it, with no official code.
- Runs on one GPU in under a day.
- A result people can see: generated images, a curve, a demo.
- One honest case that did not reproduce, published only after contacting the authors.
