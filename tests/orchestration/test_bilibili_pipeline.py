"""Isolated Bilibili worker stages without real network or credentials."""

from pathlib import Path

from src.orchestration.bilibili_worker import BilibiliWorkPipeline
from src.orchestration.worker import WorkerContext


def test_bilibili_download_stage_uses_part_url_and_forwards_real_progress(tmp_path):
    received = []

    class Credential:
        sessdata = "private"
        bili_jct = "private"

    def cookies(credential, buvid3, destination):
        destination.write_text("cookie", "utf-8")
        return destination

    def download(bvid, destination, *, source_url, cookies_file, progress_callback, **kwargs):
        assert bvid == "BV18bLkztE7R"
        assert source_url.endswith("BV18bLkztE7R?p=7")
        assert cookies_file.exists()
        progress_callback(25, 100, 5)
        output = destination / "audio.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"audio")
        return output

    pipeline = BilibiliWorkPipeline(
        config=object(),
        credential_provider=lambda config: (Credential(), "buvid"),
        cookies_factory=cookies,
        download_fn=download,
    )
    context = WorkerContext(
        task_id="task_1",
        payload={"source": {"platform": "bilibili", "bvid": "BV18bLkztE7R", "part": 7}},
        work_dir=tmp_path,
        artifacts={},
        emit_transfer=lambda completed, total, speed: received.append((completed, total, speed)),
    )

    artifacts = pipeline.download(context)

    assert artifacts == {"audio": "media/audio.wav"}
    assert received == [(25, 100, 5)]


def test_bilibili_clean_stage_loads_the_transcript_from_the_asr_boundary(tmp_path):
    transcript = tmp_path / "artifacts" / "transcript.json"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"text": "transcript"}', "utf-8")

    class Processor:
        def process_transcript(self, document):
            assert document == {"text": "transcript"}
            return {"source_id": "p07", "content": "cleaned"}

    pipeline = BilibiliWorkPipeline(
        config=object(),
        credential_provider=lambda config: (object(), ""),
        cookies_factory=lambda credential, buvid, destination: destination,
        download_fn=lambda *args, **kwargs: None,
        text_processor_factory=Processor,
    )
    context = WorkerContext(
        task_id="task_1",
        payload={"source": {"platform": "bilibili", "bvid": "BV18bLkztE7R", "part": 7}},
        work_dir=tmp_path,
        artifacts={"transcript": "artifacts/transcript.json"},
        emit_transfer=lambda completed, total, speed: None,
    )

    artifacts = pipeline.clean(context)

    assert artifacts == {"cleaned": "artifacts/p07.json"}
