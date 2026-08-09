"""Production stage adapter for one Bilibili video part in one worker process."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from src.orchestration.worker import WorkerContext


class BilibiliWorkPipeline:
    """Execute download, ASR, clean, knowledge extraction, and episode output locally."""

    def __init__(
        self,
        *,
        config: Any,
        credential_provider: Callable | None = None,
        cookies_factory: Callable | None = None,
        download_fn: Callable | None = None,
        asr_factory: Callable | None = None,
        text_processor_factory: Callable | None = None,
        knowledge_extractor_factory: Callable | None = None,
    ) -> None:
        self.config = config
        if credential_provider is None or cookies_factory is None or download_fn is None:
            from src.crawl.audio_download import download_audio_with_progress, generate_cookies_file
            from src.crawl.auth import get_credential

            credential_provider = credential_provider or get_credential
            cookies_factory = cookies_factory or generate_cookies_file
            download_fn = download_fn or download_audio_with_progress
        self.credential_provider = credential_provider
        self.cookies_factory = cookies_factory
        self.download_fn = download_fn
        self.asr_factory = asr_factory
        self.text_processor_factory = text_processor_factory
        self.knowledge_extractor_factory = knowledge_extractor_factory
        self._asr = None
        self._processor = None
        self._extractor = None

    @classmethod
    def from_local_config(cls) -> "BilibiliWorkPipeline":
        from src.config import load_config

        return cls(config=load_config())

    def download(self, context: WorkerContext) -> Mapping[str, str]:
        bvid, part = _source(context)
        destination = context.work_dir / "media"
        destination.mkdir(parents=True, exist_ok=True)
        credential, buvid3 = self.credential_provider(self.config)
        with tempfile.TemporaryDirectory(prefix="distill_bili_worker_") as temporary:
            cookies = self.cookies_factory(credential, buvid3, Path(temporary) / "cookies.txt")
            audio_path = self.download_fn(
                bvid,
                destination,
                audio_format="wav",
                cookies_file=cookies,
                source_url=f"https://www.bilibili.com/video/{bvid}?p={part}",
                progress_callback=context.emit_transfer,
            )
        if audio_path is None:
            raise RuntimeError("Bilibili audio download failed")
        path = Path(audio_path)
        if not path.is_file() or not path.is_relative_to(context.work_dir):
            raise RuntimeError("Bilibili downloader did not produce worker-local audio")
        return {"audio": str(path.relative_to(context.work_dir)).replace("\\", "/")}

    def extract_audio(self, context: WorkerContext) -> Mapping[str, str]:
        """Bilibili downloader already produces WAV, so this durable boundary is a no-op."""

        if "audio" not in context.artifacts:
            raise RuntimeError("audio artifact is unavailable")
        return {}

    def transcribe(self, context: WorkerContext) -> Mapping[str, str]:
        from src.asr.funasr_engine import FunASREngine, save_transcript

        bvid, part = _source(context)
        audio = _artifact_path(context, "audio")
        source_id = f"bilibili_{bvid}_p{part:02d}"
        if self._asr is None:
            self._asr = self.asr_factory() if self.asr_factory else FunASREngine(
                model_name=self.config.funasr.model,
                vad_model=self.config.funasr.vad_model,
                punc_model=self.config.funasr.punc_model,
                model_dir=self.config.model_cache_dir,
            )
        result = self._asr.transcribe(audio, source_id)
        output_dir = context.work_dir / "artifacts"
        path = save_transcript(
            result,
            {
                "title": f"{bvid} P{part}",
                "platform": "bilibili",
                "item_type": "video",
                "source_url": f"https://www.bilibili.com/video/{bvid}?p={part}",
            },
            output_dir,
        )
        return {"transcript": str(path.relative_to(context.work_dir)).replace("\\", "/")}

    def clean(self, context: WorkerContext) -> Mapping[str, str]:
        from src.clean.text_processor import TextProcessor, create_llm_client, load_cleaned, load_transcript, save_cleaned

        del load_cleaned
        if self._processor is None:
            if self.text_processor_factory is not None:
                self._processor = self.text_processor_factory()
            else:
                client = create_llm_client(self.config.llm_provider, self.config)
                if client is None:
                    raise RuntimeError("no local LLM provider is configured")
                self._processor = TextProcessor(llm_client=client)
        cleaned = self._processor.process_transcript(load_transcript(_artifact_path(context, "transcript")))
        path = save_cleaned(cleaned, context.work_dir / "artifacts")
        return {"cleaned": str(path.relative_to(context.work_dir)).replace("\\", "/")}

    def summarize(self, context: WorkerContext) -> Mapping[str, str]:
        from src.clean.text_processor import create_llm_client, load_cleaned
        from src.model.knowledge_extractor import KnowledgeExtractor, save_video_knowledge

        if self._extractor is None:
            if self.knowledge_extractor_factory is not None:
                self._extractor = self.knowledge_extractor_factory()
            else:
                client = create_llm_client(self.config.llm_provider, self.config)
                if client is None:
                    raise RuntimeError("no local LLM provider is configured")
                self._extractor = KnowledgeExtractor(client)
        knowledge = self._extractor.extract_from_video(load_cleaned(_artifact_path(context, "cleaned")))
        path = save_video_knowledge(knowledge, context.work_dir / "artifacts")
        return {"knowledge": str(path.relative_to(context.work_dir)).replace("\\", "/")}

    def write(self, context: WorkerContext) -> Mapping[str, str]:
        bvid, part = _source(context)
        knowledge = json.loads(_artifact_path(context, "knowledge").read_text("utf-8"))
        output = context.work_dir / "artifacts" / "episode.md"
        title = str(knowledge.get("title") or f"{bvid} P{part}")
        summary = str(knowledge.get("summary") or "")
        output.write_text(
            "---\n"
            f"source_platform: bilibili\nsource_bvid: {bvid}\nsource_part: {part}\n"
            "---\n\n"
            f"# {title}\n\n{summary}\n",
            "utf-8",
        )
        return {"episode": "artifacts/episode.md"}


def _source(context: WorkerContext) -> tuple[str, int]:
    source = context.payload.get("source")
    if not isinstance(source, Mapping) or source.get("platform") != "bilibili":
        raise RuntimeError("worker payload is not a Bilibili work")
    bvid, part = source.get("bvid"), source.get("part")
    if not isinstance(bvid, str) or not bvid.startswith("BV") or not isinstance(part, int) or part < 1:
        raise RuntimeError("worker Bilibili source descriptor is invalid")
    return bvid, part


def _artifact_path(context: WorkerContext, name: str) -> Path:
    try:
        relative = context.artifacts[name]
    except KeyError as error:
        raise RuntimeError(f"{name} artifact is unavailable") from error
    path = context.work_dir / relative
    if not path.is_file() or not path.resolve().is_relative_to(context.work_dir.resolve()):
        raise RuntimeError(f"{name} artifact is invalid")
    return path
