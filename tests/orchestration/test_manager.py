"""Lifecycle tests for the process-owning task manager."""

from src.orchestration.manager import TaskManager
from src.orchestration.store import OrchestrationStore


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
