from queue import Empty

import pytest

from src.application.events import EventHub


def test_event_hub_uses_monotonic_ids_and_bounded_snapshot():
    hub = EventHub(capacity=2)

    first = hub.publish("job.updated", {"job_id": "1", "revision": 1})
    second = hub.publish("job.updated", {"job_id": "1", "revision": 2})
    third = hub.publish("job.updated", {"job_id": "2", "revision": 1})

    assert first.event_id == 1
    assert second.event_id == 2
    assert third.event_id == 3
    assert [event.event_id for event in hub.snapshot()] == [2, 3]
    assert [event.event_id for event in hub.snapshot(after_id=2)] == [3]
    assert [event.event_id for event in hub.snapshot(job_id="1")] == [2]


def test_subscription_receives_events_and_can_close():
    hub = EventHub()
    subscription = hub.subscribe()

    expected = hub.publish("progress.updated", {"job_id": "job-1"})

    assert subscription.get(timeout=0.1) == expected
    subscription.close()
    assert subscription.closed is True


def test_slow_subscriber_requests_a_snapshot_instead_of_unbounded_queueing():
    hub = EventHub()
    subscription = hub.subscribe(queue_size=1)

    hub.publish("item.updated", {"job_id": "job-1"})
    hub.publish("item.updated", {"job_id": "job-1"})

    assert subscription.needs_snapshot is True
    with pytest.raises(Empty):
        subscription.get(timeout=0.01)
