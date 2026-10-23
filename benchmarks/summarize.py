"""Summarize benchmark studies into the numbers each release publishes.

Usage: python benchmarks/summarize.py STUDIES_DIR [--spot-check FILE.csv] [--json]

Each subdirectory with a report.json is one study. Studies whose evidence log
fails verification are excluded and listed.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from irp.application.report_ops import verify_study  # noqa: E402
from irp.application.study import open_study  # noqa: E402
from irp.domain.claims import SuccessBar  # noqa: E402
from irp.domain.verdicts import VERDICTS, judge  # noqa: E402


def load_studies(root: Path) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    studies, excluded = [], []
    for report_path in sorted(root.glob("*/report.json")):
        study_dir = report_path.parent
        verification = verify_study(open_study(str(study_dir)))
        if not verification["chain_ok"] or verification["file_problems"]:
            excluded.append(study_dir.name)
            continue
        studies.append((study_dir, json.loads(report_path.read_text(encoding="utf-8"))))
    return studies, excluded


def summarize(root: Path, spot_check: Path | None) -> dict[str, Any]:
    studies, excluded = load_studies(root)
    counts = dict.fromkeys(VERDICTS, 0)
    durations, costs = [], []
    official_agree = official_total = 0
    for study_dir, report in studies:
        for claim in report["claims"]:
            if claim["verdict"]:
                counts[claim["verdict"]] += 1
        durations.append(sum(run.get("duration_s") or 0 for run in report["runs"]))
        costs.append(report["provenance"].get("spent_usd") or 0.0)
        official_path = study_dir / "official.json"
        if official_path.is_file():
            official = json.loads(official_path.read_text(encoding="utf-8"))
            for claim in report["claims"]:
                ours = (claim.get("ours") or {}).get("value")
                if claim["id"] in official and ours is not None:
                    official_total += 1
                    bar = SuccessBar.from_dict(claim["success_bar"])
                    if judge(float(official[claim["id"]]), ours, bar).verdict in (
                        "reproduced",
                        "close",
                    ):
                        official_agree += 1
    judged = sum(counts.values())
    summary: dict[str, Any] = {
        "studies": len(studies),
        "excluded_unverified": excluded,
        "claims_with_verdict": judged,
        "verdicts": counts,
        "reproduced_or_close_share": (counts["reproduced"] + counts["close"]) / judged
        if judged
        else None,
        "median_run_seconds_per_paper": statistics.median(durations) if durations else None,
        "median_paid_compute_usd_per_paper": statistics.median(costs) if costs else None,
        "agreement_with_official_code": official_agree / official_total if official_total else None,
    }
    if spot_check is not None:
        verdict_by_key = {
            (study_dir.name, claim["id"]): claim["verdict"]
            for study_dir, report in studies
            for claim in report["claims"]
        }
        agree = total = 0
        with spot_check.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                key = (row["study"], row["claim_id"])
                if key in verdict_by_key:
                    total += 1
                    agree += int(verdict_by_key[key] == row["human_verdict"])
        summary["spot_check"] = {"claims": total, "agreement": agree / total if total else None}
    return summary


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    spot = Path(argv[argv.index("--spot-check") + 1]).resolve() if "--spot-check" in argv else None
    summary = summarize(Path(argv[0]).resolve(), spot)
    if "--json" in argv:
        print(json.dumps(summary, indent=2))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
