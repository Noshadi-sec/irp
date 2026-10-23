"""Reproduce fastText's AG News test accuracy (Table 1: fastText h=10 bigram = 92.5).

fastText's classifier is a linear model over a bag of word + n-gram features.
Here it's reimplemented with scikit-learn: TF-IDF over unigrams+bigrams feeding a
linear SVM -- the library-independent stand-in for fastText's hashed n-gram linear
model. Accuracy is reported in percent to match the paper's table.
"""

import json
from pathlib import Path

from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.svm import LinearSVC

def main() -> None:
    ds = load_dataset("fancyzhx/ag_news")
    xtr, ytr = ds["train"]["text"], ds["train"]["label"]
    xte, yte = ds["test"]["text"], ds["test"]["label"]
    print(f"sizes: train {len(xtr)} test {len(xte)}", flush=True)
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2, max_features=1_000_000)
    xtr_v = vec.fit_transform(xtr)
    xte_v = vec.transform(xte)
    clf = LinearSVC(C=1.0)
    clf.fit(xtr_v, ytr)
    acc = 100.0 * float(accuracy_score(yte, clf.predict(xte_v)))
    print(f"ag_acc: {acc:.2f}", flush=True)
    Path("results.json").write_text(json.dumps({"ag_acc": acc}))

if __name__ == "__main__":
    main()
