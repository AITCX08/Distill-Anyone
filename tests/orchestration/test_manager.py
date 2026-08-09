"""Lifecycle tests for the process-owning task manager."""

from src.orchestration.manager import TaskManager
from src.orchestration.store import OrchestrationStore
import json


class FakeProcess:
    pid = 4242

    def poll(self):
        return None


class FakeProcessFactory:
    def __call__(self, task, payload_path):
        self.pid = FakeProcess.pid
        self.task_id = task.task_id
        self.payload_path = payload_path
        return FakeProcess()


def test_start_records_one_lease_and_reads_worker_events(tmp_path):
    factory = FakeProcessFactory()
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    manager = TaskManager(store=store, worker_root=tmp_path / "workers", process_factory=factory)
    task = manager.enqueue(job.job_id, "p01")

    manager.tick()

    assert store.get_lease(task.task_id).pid == factory.pid
    assert store.get_task(task.task_id).status == "running"
    assert factory.payload_path.exists()


def test_tick_persists_valid_worker_jsonl_events(tmp_path):
    class EventProcessFactory(FakeProcessFactory):
        def __call__(self, task, payload_path):
            result = super().__call__(task, payload_path)
            (payload_path.parent / "events.jsonl").write_text(
                '{"v":1,"type":"stage","task_id":"' + task.task_id + '","stage":"downloading"}\n',
                "utf-8",
            )
            return result

    factory = EventProcessFactory()
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    manager = TaskManager(store=store, worker_root=tmp_path / "workers", process_factory=factory)
    task = manager.enqueue(job.job_id, "p01")

    manager.tick()

    event = store.list_events(task.task_id)[0]
    assert event.kind == "stage"
    assert event.payload["stage"] == "downloading"


def test_tick_reads_events_appended_after_worker_launch(tmp_path):
    factory = FakeProcessFactory()
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    manager = TaskManager(store=store, worker_root=tmp_path / "workers", process_factory=factory)
    task = manager.enqueue(job.job_id, "p01")
    manager.tick()
    events_path = tmp_path / "workers" / task.task_id / "events.jsonl"
    events_path.write_text(
        '{"v":1,"type":"stage","task_id":"' + task.task_id + '","stage":"transcribing"}\n',
        "utf-8",
    )

    manager.tick()

    assert store.get_task(task.task_id).stage == "transcribing"


def test_bilibili_task_payload_keeps_only_stable_video_and_part_identifiers(tmp_path):
    factory = FakeProcessFactory()
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://www.bilibili.com/video/BV18bLkztE7R")
    task = store.create_tasks(job.job_id, ["bilibili_BV18bLkztE7R_p07"])[0]
    manager = TaskManager(store=store, worker_root=tmp_path / "workers", process_factory=factory)

    manager.start(task.task_id)

    payload = json.loads(factory.payload_path.read_text("utf-8"))
    assert payload["source"] == {"platform": "bilibili", "bvid": "BV18bLkztE7R", "part": 7}
    assert "command" not in payload
    assert "cookie" not in json.dumps(payload).lower()


def test_tick_releases_a_completed_worker_slot_after_its_terminal_event(tmp_path):
    class FinishedProcess:
        pid = 4242

        def poll(self):
            return 0

    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    task = store.create_tasks(job.job_id, ["p01"])[0]
    manager = TaskManager(
        store=store,
        worker_root=tmp_path / "workers",
        process_factory=lambda task, payload: FinishedProcess(),
    )
    manager.start(task.task_id)
    (tmp_path / "workers" / task.task_id / "events.jsonl").write_text(
        '{"v":1,"type":"terminal","task_id":"' + task.task_id + '","status":"completed"}\n',
        "utf-8",
    )

    manager.tick()

    assert store.get_task(task.task_id).status == "completed"
    try:
        store.get_lease(task.task_id)
    except KeyError:
        pass
    else:
        raise AssertionError("completed worker lease was not released")


def test_manager_grants_only_one_asr_stage_to_two_worker_processes(tmp_path):
    factory = FakeProcessFactory()
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    first, second = store.create_tasks(job.job_id, ["p01", "p02"])
    manager = TaskManager(store=store, worker_root=tmp_path / "workers", process_factory=factory)
    manager.start(first.task_id)
    manager.start(second.task_id)
    for task in (first, second):
        (tmp_path / "workers" / task.task_id / "resource-request.json").write_text(
            '{"stage":"transcribing"}', "utf-8"
        )

    manager.tick()

    grants = [
        (tmp_path / "workers" / task.task_id / "resource-grant.json").exists()
        for task in (first, second)
    ]
    assert grants.count(True) == 1
