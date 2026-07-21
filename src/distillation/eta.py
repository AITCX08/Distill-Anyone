"""Rolling-median stage estimates for total and active-slowest ETA."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import median
from typing import Mapping, Sequence


@dataclass(frozen=True)
class EtaEstimate:
    seconds: float
    provisional: bool = False


@dataclass(frozen=True)
class RemainingWork:
    platform: str
    stage_work: Mapping[str, float]
    concurrency: Mapping[str, int]
    provisional: bool = False


@dataclass(frozen=True)
class ActiveItemRemaining:
    source_id: str
    platform: str
    stage_work: Mapping[str, float]


class EtaEstimator:
    def __init__(self, *, min_samples: int = 3, window_size: int = 30):
        if min_samples <= 0 or window_size < min_samples:
            raise ValueError("ETA sample limits are invalid")
        self.min_samples = min_samples
        self.window_size = window_size
        self._rates: dict[tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

    def update(
        self,
        stage: str,
        *,
        work: float,
        elapsed: float,
        platform: str = "*",
    ) -> None:
        if work <= 0 or elapsed < 0:
            return
        self._rates[(platform, stage)].append(elapsed / work)

    def rate(self, stage: str, *, platform: str = "*") -> float | None:
        samples = self._rates.get((platform, stage))
        if (samples is None or len(samples) < self.min_samples) and platform != "*":
            samples = self._rates.get(("*", stage))
        if samples is None or len(samples) < self.min_samples:
            return None
        return float(median(samples))

    def estimate_total(self, remaining: RemainingWork) -> EtaEstimate | None:
        stage_seconds: list[float] = []
        for stage, work in remaining.stage_work.items():
            if work <= 0:
                continue
            rate = self.rate(stage, platform=remaining.platform)
            if rate is None:
                return None
            concurrency = max(1, int(remaining.concurrency.get(stage, 1)))
            stage_seconds.append(work * rate / concurrency)
        return EtaEstimate(
            seconds=max(stage_seconds, default=0.0),
            provisional=remaining.provisional,
        )

    def estimate_active_slowest(
        self,
        active_items: Sequence[ActiveItemRemaining],
    ) -> EtaEstimate | None:
        item_seconds: list[float] = []
        for item in active_items:
            total = 0.0
            for stage, work in item.stage_work.items():
                if work <= 0:
                    continue
                rate = self.rate(stage, platform=item.platform)
                if rate is None:
                    return None
                total += work * rate
            item_seconds.append(total)
        if not item_seconds:
            return None
        return EtaEstimate(max(item_seconds), provisional=False)

