"""Reproduce QMNIST's best-KNN (k=3) MNIST error rate (Table tbl:KNN3 = 2.95%).

The paper's KNN baseline is k=3 nearest neighbours on the MNIST training set; the
'Train on MNIST / Test on MNIST' cell is 2.95% misclassification. Deterministic,
CPU-only, needs only the standard MNIST data. Reported as error % to match the table.
"""

import gzip
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score
from sklearn.neighbors import KNeighborsClassifier

CACHE = Path(os.environ.get("DATA_CACHE", "/tmp/knn-data-cache"))
MNIST = "https://ossci-datasets.s3.amazonaws.com/mnist/"


def get(name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    t = CACHE / name
    if not (t.is_file() and t.stat().st_size > 0):
        urllib.request.urlretrieve(MNIST + name, t)
    return t


def imgs(p: Path) -> np.ndarray:
    with gzip.open(p, "rb") as f:
        _m, n, r, c = np.frombuffer(f.read(16), dtype=">i4")
        return np.frombuffer(f.read(), dtype=np.uint8).reshape(n, r * c)


def labs(p: Path) -> np.ndarray:
    with gzip.open(p, "rb") as f:
        _ = np.frombuffer(f.read(8), dtype=">i4")
        return np.frombuffer(f.read(), dtype=np.uint8)


def main() -> None:
    xtr = imgs(get("train-images-idx3-ubyte.gz"))
    ytr = labs(get("train-labels-idx1-ubyte.gz"))
    xte = imgs(get("t10k-images-idx3-ubyte.gz"))
    yte = labs(get("t10k-labels-idx1-ubyte.gz"))
    model = KNeighborsClassifier(n_neighbors=3, n_jobs=-1)
    model.fit(xtr, ytr)
    err = 100.0 * (1.0 - float(accuracy_score(yte, model.predict(xte))))
    print(f"knn_err: {err:.2f}", flush=True)
    Path("results.json").write_text(json.dumps({"knn_err": err}))


if __name__ == "__main__":
    main()
