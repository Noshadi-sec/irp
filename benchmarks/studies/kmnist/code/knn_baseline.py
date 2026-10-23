"""Reproduce the KMNIST paper's 4-Nearest-Neighbour baseline (Table 1).

Accuracy is the mean of per-class accuracies (balanced accuracy), as the paper
states, and is reported in percent to match the paper's table. 4-NN is
deterministic, so a single run suffices. Pixel data is on one common 0-255
scale, so no per-feature preprocessing is needed for Euclidean kNN.
"""

import gzip
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score
from sklearn.neighbors import KNeighborsClassifier

CACHE = Path(os.environ.get("DATA_CACHE", "/tmp/knn-data-cache"))
MNIST = "https://ossci-datasets.s3.amazonaws.com/mnist/"
KMNIST = "http://codh.rois.ac.jp/kmnist/dataset/kmnist/"


def get(url: str, name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / name
    if not (target.is_file() and target.stat().st_size > 0):
        urllib.request.urlretrieve(url + name, target)
    return target


def read_idx_images(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        _magic, n, r, c = np.frombuffer(f.read(16), dtype=">i4")
        return np.frombuffer(f.read(), dtype=np.uint8).reshape(n, r * c)


def read_idx_labels(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        _magic, _n = np.frombuffer(f.read(8), dtype=">i4")
        return np.frombuffer(f.read(), dtype=np.uint8)


def knn_percent(xtr, ytr, xte, yte) -> float:
    model = KNeighborsClassifier(n_neighbors=4, n_jobs=-1)
    model.fit(xtr, ytr)
    return 100.0 * float(balanced_accuracy_score(yte, model.predict(xte)))


def main() -> None:
    mtr = read_idx_images(get(MNIST, "train-images-idx3-ubyte.gz"))
    mtr_y = read_idx_labels(get(MNIST, "train-labels-idx1-ubyte.gz"))
    mte = read_idx_images(get(MNIST, "t10k-images-idx3-ubyte.gz"))
    mte_y = read_idx_labels(get(MNIST, "t10k-labels-idx1-ubyte.gz"))
    print(f"knn_mnist: {knn_percent(mtr, mtr_y, mte, mte_y):.2f}", flush=True)
    ktr = np.load(get(KMNIST, "kmnist-train-imgs.npz"))["arr_0"].reshape(-1, 784)
    ktr_y = np.load(get(KMNIST, "kmnist-train-labels.npz"))["arr_0"]
    kte = np.load(get(KMNIST, "kmnist-test-imgs.npz"))["arr_0"].reshape(-1, 784)
    kte_y = np.load(get(KMNIST, "kmnist-test-labels.npz"))["arr_0"]
    print(f"knn_kmnist: {knn_percent(ktr, ktr_y, kte, kte_y):.2f}", flush=True)
    Path("results.json").write_text(json.dumps({"done": True}))


if __name__ == "__main__":
    main()
