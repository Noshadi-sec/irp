"""Cost estimates for paid compute, from prices a person entered.

IRP ships no price list: GPU prices change, and a stale built-in number
would make every estimate wrong. A person records the provider's current price
with `irp budget price`, and the run's time limit is set to the estimated
hours so the estimate is also a ceiling on billed GPU time.
"""

from __future__ import annotations

from typing import Any

PRICING_PAGES = {
    "modal": "https://modal.com/pricing",
    "runpod": "https://www.runpod.io/pricing",
    "hf_jobs": "https://huggingface.co/pricing",
}


def estimate(
    *, provider: str, gpu: str, gpu_count: int, hours: float, price: dict[str, Any]
) -> dict[str, Any]:
    usd = round(float(price["usd_per_hour"]) * gpu_count * hours, 4)
    return {
        "provider": provider,
        "gpu": gpu,
        "gpu_count": gpu_count,
        "hours": hours,
        "usd_per_gpu_hour": float(price["usd_per_hour"]),
        "usd": usd,
        "price_recorded_seq": price.get("seq"),
        "basis": "price per GPU-hour x GPUs x hours; the run is stopped at the time limit, "
        "so GPU time cannot exceed this estimate. Image builds, storage and provider "
        "minimums are billed by the provider separately.",
    }
