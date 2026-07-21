from src.distillation.eta import (
    ActiveItemRemaining,
    EtaEstimator,
    RemainingWork,
)


def remaining(*, provisional=False):
    return RemainingWork(
        platform="douyin",
        stage_work={"download": 30.0, "asr": 60.0},
        concurrency={"download": 3, "asr": 1},
        provisional=provisional,
    )


def test_eta_requires_three_samples():
    estimator = EtaEstimator(min_samples=3)
    estimator.update("asr", work=60, elapsed=20, platform="douyin")

    assert estimator.estimate_total(remaining()) is None


def test_eta_uses_rolling_median_and_stage_concurrency():
    estimator = EtaEstimator(min_samples=3)
    for elapsed in (10, 20, 90):
        estimator.update("download", work=10, elapsed=elapsed, platform="douyin")
    for elapsed in (30, 60, 300):
        estimator.update("asr", work=60, elapsed=elapsed, platform="douyin")

    estimate = estimator.estimate_total(remaining(provisional=True))

    # download median rate: 2 s/unit -> 30*2/3 = 20s
    # ASR median rate: 1 s/unit -> 60*1/1 = 60s; bottleneck wins.
    assert estimate.seconds == 60
    assert estimate.provisional is True


def test_active_slowest_is_distinct_from_total_eta():
    estimator = EtaEstimator(min_samples=3)
    for _ in range(3):
        estimator.update("download", work=10, elapsed=10, platform="douyin")
        estimator.update("asr", work=10, elapsed=20, platform="douyin")

    estimate = estimator.estimate_active_slowest(
        (
            ActiveItemRemaining("douyin_1", "douyin", {"download": 2, "asr": 3}),
            ActiveItemRemaining("douyin_2", "douyin", {"asr": 5}),
        )
    )

    assert estimate.seconds == 10
    assert estimate.provisional is False

