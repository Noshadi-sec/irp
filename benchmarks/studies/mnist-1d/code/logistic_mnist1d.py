"""Reproduce the MNIST-1D paper's linear-classifier (logistic regression) claim.

The paper (content.tex:120) reports 32% test accuracy for logistic regression,
the lower bound of its model zoo, reported here in percent to match the paper.
The paper trained a linear model in PyTorch with Adam + early stopping; a
converged scikit-learn multinomial logistic regression is the library-
independent stand-in for the same linear hypothesis class, so the accuracy
ceiling should match. The dataset is the fixed public release
(mnist1d_data.pkl), so the result is deterministic -- one run suffices.
"""

import json
import os
import pickle
import urllib.request
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

CACHE = Path(os.environ.get("DATA_CACHE", "/tmp/mnist1d-cache"))
URL = "https://github.com/greydanus/mnist1d/raw/master/mnist1d_data.pkl"


def load_dataset() -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    pkl = CACHE / "mnist1d_data.pkl"
    if not (pkl.is_file() and pkl.stat().st_size > 0):
        urllib.request.urlretrieve(URL, pkl)
    with pkl.open("rb") as f:
        return pickle.load(f)


def main() -> None:
    data = load_dataset()
    xtr, ytr = np.asarray(data["x"]), np.asarray(data["y"])
    xte, yte = np.asarray(data["x_test"]), np.asarray(data["y_test"])
    print(f"shapes: train {xtr.shape} test {xte.shape}", flush=True)
    # Standardise features (fit on train only): aids solver convergence and does
    # not change the linear hypothesis class. Documented as a guess.
    scaler = StandardScaler().fit(xtr)
    xtr, xte = scaler.transform(xtr), scaler.transform(xte)
    model = LogisticRegression(max_iter=5000)
    model.fit(xtr, ytr)
    print(f"logreg_train_acc: {100.0 * float(model.score(xtr, ytr)):.2f}", flush=True)
    test_acc = 100.0 * float(model.score(xte, yte))
    print(f"logreg_acc: {test_acc:.2f}", flush=True)
    Path("results.json").write_text(json.dumps({"logreg_acc": test_acc}))


if __name__ == "__main__":
    main()
