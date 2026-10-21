"""Reference implementation of the toy paper (the "hidden official code").

The golden test rebuilds the paper from its text and compares against this.
Standard library only, so it runs in any environment.
"""

import json
import os
import random
import statistics


def make_data(rng: random.Random, n: int) -> tuple[list[float], list[float]]:
    xs = [rng.random() for _ in range(n)]
    ys = [2.0 * x + 1.0 + rng.gauss(0.0, 0.1) for x in xs]
    return xs, ys


def fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = numerator / denominator
    return slope, mean_y - slope * mean_x


def main() -> None:
    seed = int(os.environ.get("IRP_SEED", "0"))
    n = int(os.environ.get("TOY_SAMPLES", "10000"))
    rng = random.Random(seed)
    train_x, train_y = make_data(rng, n)
    test_x, test_y = make_data(rng, n)
    slope, intercept = fit(train_x, train_y)
    mse = statistics.fmean((y - (slope * x + intercept)) ** 2 for x, y in zip(test_x, test_y))
    print(f"seed: {seed}")
    print(f"slope: {slope:.6f}")
    print(f"intercept: {intercept:.6f}")
    print(f"test_mse: {mse:.6f}")
    with open("results.json", "w", encoding="utf-8") as handle:
        json.dump({"slope": slope, "intercept": intercept, "test_mse": mse, "seed": seed}, handle)


if __name__ == "__main__":
    main()
