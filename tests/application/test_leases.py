from datetime import datetime, timedelta, timezone

import pytest

from src.application.leases import JobLeaseConflict, JobLeaseManager


def test_live_lease_cannot_be_stolen(tmp_path):
    manager = JobLeaseManager(tmp_path, pid_alive=lambda pid: True)
    lease = manager.acquire("job-1", owner="cli")

    with pytest.raises(JobLeaseConflict) as error:
        manager.acquire("job-1", owner="dashboard")

    assert error.value.owner == "cli"
    lease.release()


def test_dead_but_recent_lease_is_not_stolen(tmp_path):
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    manager = JobLeaseManager(
        tmp_path,
        pid_alive=lambda pid: False,
        now=lambda: now,
        stale_after=timedelta(seconds=30),
    )
    manager.acquire("job-1", owner="cli")

    with pytest.raises(JobLeaseConflict):
        manager.acquire("job-1", owner="dashboard")


def test_dead_and_expired_lease_can_be_recovered(tmp_path):
    clock = [datetime(2026, 7, 21, tzinfo=timezone.utc)]
    manager = JobLeaseManager(
        tmp_path,
        pid_alive=lambda pid: False,
        now=lambda: clock[0],
        stale_after=timedelta(seconds=30),
    )
    old = manager.acquire("job-1", owner="cli")
    clock[0] += timedelta(seconds=31)

    recovered = manager.acquire("job-1", owner="dashboard")

    assert recovered.token != old.token
    assert recovered.owner == "dashboard"
    recovered.heartbeat()
    recovered.release()
    assert not manager.lease_path("job-1").exists()

