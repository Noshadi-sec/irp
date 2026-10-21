# Toy paper: an offline end-to-end example

A small synthetic paper, "Least Squares Recovers a Linear Trend in Ten Thousand
Samples", with a hidden reference implementation. It runs in seconds on any
CPU and needs no network, which makes it IRP's golden test and a quick way
to see the whole loop.

- `paper/`: the LaTeX source (`main.tex` inputs `sections/method.tex`), with
  sections, a table, three equations, an algorithm and an appendix.
- `reference/fit.py`: the "official code", hidden from the agent. Use it only
  to compare after the study is finished.

## Try it

Ask your agent:

```text
Build the paper in examples/toy-paper/paper with IRP in ~/studies/toy and check Table 1.
```

Or from the terminal (uv on PATH):

```bash
S=~/studies/toy
irp fetch examples/toy-paper/paper --study $S
irp section tab:main --study $S
irp claim add --study $S --statement "Slope estimate" --metric slope --value "2.00" \
  --where "Table 1, row 1" --source-file main.tex --source-line 41 --tol-abs 0.01 --seeds-in-paper 3
irp claim add --study $S --statement "Test MSE" --metric test_mse --value "0.0100" \
  --where "Table 1, row 1" --source-file main.tex --source-line 41 --tol-rel 0.02 --seeds-in-paper 3
```

Write `$S/code/ols.py` from the paper's method (draw training then test samples
from `random.Random(IRP_SEED)`, fit with Eq. 3, print `slope:` and
`test_mse:`), then:

```bash
irp env create --study $S
for seed in 0 1 2; do irp run --study $S --seed $seed -- python ols.py; done
for run in r1 r2 r3; do irp metrics $run --study $S --specs-json \
  '[{"name":"slope","key":"slope"},{"name":"test_mse","key":"test_mse"}]'; done
irp compare c1 --study $S -m m1 -m m3 -m m5
irp compare c2 --study $S -m m2 -m m4 -m m6
irp report --study $S && irp verify --study $S
```

Finally compare with the hidden code:

```bash
REF="$PWD/examples/toy-paper/reference/fit.py"
(cd "$(mktemp -d)" && for seed in 0 1 2; do IRP_SEED=$seed python "$REF"; done)
```
