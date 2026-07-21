"""Stage-separated content processors shared by all source platforms."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.asr.funasr_engine import (
    TranscriptResult,
    check_transcript_integrity,
    load_transcript,
    save_transcript,
)
from src.clean.text_processor import check_cleaned_integrity, save_cleaned
from src.model.knowledge_extractor import (
    VideoKnowledge,
    check_knowledge_integrity,
    save_video_knowledge,
)
from src.platforms.models import DownloadedAssets, ItemType, SourceItem
from src.distillation.state import ProcessingStatus


class ArtifactIntegrityError(RuntimeError):
    def __init__(self, source_id: str, artifact: str, reason: str):
        super().__init__(f"Invalid {artifact} artifact for {source_id}: {reason}")
        self.source_id = source_id
        self.artifact = artifact
        self.reason = reason


@dataclass(frozen=True)
class PreparedMedia:
    item: SourceItem
    audio_path: Path
    assets: DownloadedAssets


@dataclass(frozen=True)
class TranscriptArtifact:
    item: SourceItem
    path: Path
    document: dict[str, Any]
    result: TranscriptResult


@dataclass(frozen=True)
class EnrichedArtifacts:
    transcript: TranscriptArtifact
    cleaned: dict[str, Any]
    cleaned_path: Path
    knowledge: VideoKnowledge
    knowledge_path: Path


@dataclass(frozen=True)
class UnsupportedResult:
    source_id: str
    status: ProcessingStatus
    error_code: str
    reason: str


class FfmpegAudioExtractor:
    def extract(self, video_path: Path, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(destination),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not destination.exists():
            raise RuntimeError(f"ffmpeg audio extraction failed: {completed.stderr[-500:]}")
        return destination


class VideoContentProcessor:
    def __init__(
        self,
        *,
        output_root: Path,
        asr: Any,
        cleaner: Any,
        knowledge_extractor: Any,
        audio_extractor: Any | None = None,
    ) -> None:
        self.output_root = output_root
        self.asr = asr
        self.cleaner = cleaner
        self.knowledge_extractor = knowledge_extractor
        self.audio_extractor = audio_extractor or FfmpegAudioExtractor()

    def prepare(self, item: SourceItem, assets: DownloadedAssets) -> PreparedMedia:
        if item.item_type is not ItemType.VIDEO:
            raise ValueError(f"Video processor cannot process {item.item_type.value}")
        if assets.audio_path is not None:
            audio_path = assets.audio_path
        elif assets.video_path is not None:
            audio_destination = self.output_root / "audio" / f"{item.source_id}.wav"
            audio_destination.parent.mkdir(parents=True, exist_ok=True)
            audio_path = self.audio_extractor.extract(
                assets.video_path,
                audio_destination,
            )
        else:
            raise ValueError(f"No video or audio asset for {item.source_id}")
        return PreparedMedia(item=item, audio_path=Path(audio_path), assets=assets)

    def transcribe(self, prepared: PreparedMedia) -> TranscriptArtifact:
        item = prepared.item
        result = self.asr.transcribe(prepared.audio_path, item.source_id)
        result.source_id = item.source_id
        if not result.bvid:
            result.bvid = item.source_id
        video_meta = {
            "title": item.title,
            "description": item.description,
            "duration": item.duration_seconds,
            "platform": item.platform,
            "item_type": item.item_type.value,
            "source_url": item.canonical_url,
            "pubdate": item.published_at.timestamp() if item.published_at else 0,
            "view_count": item.statistics.get("views", 0),
            "comment_count": item.statistics.get("comments", 0),
        }
        path = save_transcript(result, video_meta, self.output_root / "transcripts")
        valid, reason = check_transcript_integrity(path, audio_path=prepared.audio_path)
        if not valid:
            raise ArtifactIntegrityError(item.source_id, "transcript", reason)
        return TranscriptArtifact(item, path, load_transcript(path), result)

    def enrich(self, transcript: TranscriptArtifact) -> EnrichedArtifacts:
        item = transcript.item
        cleaned = self.cleaner.process_transcript(dict(transcript.document))
        metadata = dict(cleaned.get("metadata") or {})
        metadata.update(
            {
                "platform": item.platform,
                "item_type": item.item_type.value,
                "source_url": item.canonical_url,
            }
        )
        cleaned["metadata"] = metadata
        cleaned["source_id"] = item.source_id
        cleaned_path = save_cleaned(cleaned, self.output_root / "cleaned")
        valid, reason = check_cleaned_integrity(cleaned_path)
        if not valid:
            raise ArtifactIntegrityError(item.source_id, "cleaned", reason)

        knowledge = self.knowledge_extractor.extract_from_video(cleaned)
        knowledge.source_id = item.source_id
        knowledge.platform = item.platform
        knowledge.source_type = item.item_type.value
        knowledge.source_url = item.canonical_url
        knowledge_path = save_video_knowledge(knowledge, self.output_root / "knowledge")
        valid, reason = check_knowledge_integrity(knowledge_path)
        if not valid:
            raise ArtifactIntegrityError(item.source_id, "knowledge", reason)
        return EnrichedArtifacts(
            transcript,
            cleaned,
            cleaned_path,
            knowledge,
            knowledge_path,
        )


class UnsupportedProcessor:
    def process(self, item: SourceItem) -> UnsupportedResult:
        code = "unsupported_note" if item.item_type is ItemType.GALLERY else "unsupported_type"
        reason = (
            "Gallery OCR is not enabled in this release"
            if item.item_type is ItemType.GALLERY
            else f"Unsupported item type: {item.item_type.value}"
        )
        return UnsupportedResult(
            source_id=item.source_id,
            status=ProcessingStatus.UNSUPPORTED,
            error_code=code,
            reason=reason,
        )


def safe_cleanup_media(media_path: Path, *, transcript_path: Path) -> bool:
    valid, _ = check_transcript_integrity(transcript_path)
    if not valid:
        return False
    try:
        media_path.unlink(missing_ok=True)
    except OSError:
        return False
    return not media_path.exists()
