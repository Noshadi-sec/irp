"""Reproduce three scikit-learn baselines from the Fashion-MNIST paper (Table 3).

Downloads the canonical Fashion-MNIST train/test split (60k/10k) and reports
test accuracy for GaussianNB, DecisionTree and RandomForest with the exact
hyperparameters stated in the paper. Pixel scaling is irrelevant for these
three (monotonic per-feature scaling leaves their decisions unchanged), so no
preprocessing choice is needed.
"""

import gzip
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier

CACHE = Path(os.environ.get("FASHION_CACHE", "/tmp/fashion-mnist-cache"))
FILES = {
    "train_images": "train-images-idx3-ubyte.gz",
    "train_labels": "train-labels-idx1-ubyte.gz",
    "test_images": "t10k-images-idx3-ubyte.gz",
    "test_labels": "t10k-labels-idx1-ubyte.gz",
}
MIRRORS = [
    "https://github.com/zalandoresearch/fashion-mnist/raw/master/data/fashion/",
    "http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/",
]


def fetch(name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / name
    if target.is_file() and target.stat().st_size > 0:
        return target
    last = None
    for base in MIRRORS:
        try:
            urllib.request.urlretrieve(base + name, target)
            if target.stat().st_size > 0:
                return target
        except Exception as exc:  # try the next mirror
            last = exc
    raise RuntimeError(f"could not download {name}: {last}")


def read_images(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        magic, n, rows, cols = np.frombuffer(f.read(16), dtype=">i4")
        assert magic == 2051, magic
        data = np.frombuffer(f.read(), dtype=np.uint8)
    return data.reshape(n, rows * cols)


def read_labels(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        magic, n = np.frombuffer(f.read(8), dtype=">i4")
        assert magic == 2049, magic
        return np.frombuffer(f.read(), dtype=np.uint8)


def main() -> None:
    seed = int(os.environ["IRP_SEED"])
    x_train = read_images(fetch(FILES["train_images"]))
    y_train = read_labels(fetch(FILES["train_labels"]))
    x_test = read_images(fetch(FILES["test_images"]))
    y_test = read_labels(fetch(FILES["test_labels"]))
    print(f"train={x_train.shape} test={x_test.shape} seed={seed}", flush=True)

    models = {
        "gnb_acc": GaussianNB(priors=[0.1] * 10),
        "dtree_acc": DecisionTreeClassifier(
            criterion="entropy", max_depth=10, splitter="best", random_state=seed
        ),
        "rf_acc": RandomForestClassifier(
            n_estimators=100, criterion="gini", max_depth=100, random_state=seed, n_jobs=-1
        ),
    }
    results = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        acc = float(model.score(x_test, y_test))
        results[name] = acc
        print(f"{name}: {acc:.4f}", flush=True)
    Path("results.json").write_text(json.dumps(results))


if __name__ == "__main__":
    main()
