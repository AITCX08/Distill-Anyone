# Multi-Platform Distillation Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a publishable Bilibili/Douyin creator distillation engine with platform adapters, episodes/Skill outputs, staged concurrency, atomic recovery, Rich progress, and dual ETA.

**Architecture:** Explicit platform and output registries feed a shared `DistillationEngine`. A presentation-neutral `DistillationService` exposes commands, queries, immutable events, and job leases to both Click and the later Dashboard without duplicating pipeline logic.

**Tech Stack:** Python 3.10+, Click, Pydantic 2, Playwright `~=1.59.0`, FunASR, Rich, pytest.

## Global Constraints

- Work only on `codex/douyin-source-adapter`, based on `origin/main@5cda109`; never rewrite local `main` or its 26 commits.
- Scout Agent is read-only reference. Do not import `scout.*`, copy private session/data paths, or modify that project.
- No PowerShell runtime dependency, `mcporter`, `npx -y`, hard-coded user path, Cookie/API key in source/log/state, or real user artifact in Git.
- Common identifiers are `platform`, `item_id`, `creator_id`, and `source_id`; `bvid`, `aweme_id`, and `sec_uid` remain adapter details.
- Defaults are download workers 3, ASR workers 1, LLM workers 3, max active items 3, max attempts 3, `keep_media=false`, and `emit=both` for `source creator`.
- Notes are enumerated as `unsupported_note` in v0.4 and count against coverage; unknown types are `unsupported_item_type`.
- Every state/artifact write uses same-directory temp file, flush, fsync, validation, and `os.replace`.
- Delete temporary media only after the final transcript is reopened and passes integrity validation.
- Tests use fixtures/mocks and never require live Bilibili, Douyin, LLM, or browser sessions.
- Run repository tests with an environment containing the declared dependencies via `python -m pytest -q`.

---

### Task 1: Platform Contracts and Registry

**Files:**
- Create: `src/platforms/__init__.py`
- Create: `src/platforms/models.py`
- Create: `src/platforms/base.py`
- Create: `src/platforms/errors.py`
- Create: `src/platforms/registry.py`
- Create: `src/platforms/manager.py`
- Test: `tests/platforms/test_registry.py`
- Test: `tests/platforms/test_models.py`

**Interfaces:**
- Produces: `SourceAsset`, `SourceCreator`, `SourceItem`, `PlatformDescriptor`, `ResolvedTarget`, `EnumerationCheckpoint`, `EnumerationPage`, `DownloadedAssets`, `PlatformAdapter`, `PlatformRegistry`, `PlatformManager`.
- `SourceItem.source_id` returns `f"{platform}_{item_id}"`.
- `PlatformRegistry.detect(target)` returns exactly one adapter or raises `PlatformNotDetectedError`/`AmbiguousPlatformError`.

- [x] **Step 1: Write failing model and registry tests**

```python
def test_source_id_is_platform_qualified():
    item = make_item(platform="douyin", item_id="123")
    assert item.source_id == "douyin_123"

def test_duplicate_platform_registration_is_rejected():
    registry = PlatformRegistry()
    registry.register(FakeAdapter("douyin", matches=True))
    with pytest.raises(DuplicatePlatformError):
        registry.register(FakeAdapter("douyin", matches=True))

def test_auto_detect_requires_exactly_one_match():
    registry = PlatformRegistry([FakeAdapter("a", True), FakeAdapter("b", True)])
    with pytest.raises(AmbiguousPlatformError):
        registry.detect("https://example.test")
```

- [x] **Step 2: Run tests and verify missing modules fail**

Run: `python -m pytest tests/platforms/test_models.py tests/platforms/test_registry.py -q`

Expected: collection fails because `src.platforms` is not implemented.

- [x] **Step 3: Implement immutable models, protocol, registry, and manager**

```python
@dataclass(frozen=True)
class SourceItem:
    platform: str
    item_id: str
    creator_id: str
    item_type: ItemType
    title: str
    description: str
    canonical_url: str
    published_at: datetime | None = None
    duration_seconds: float | None = None
    statistics: Mapping[str, int] = field(default_factory=dict)
    cover_url: str | None = None
    tags: Sequence[str] = ()
    assets: Sequence[SourceAsset] = ()
    raw_metadata: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def source_id(self) -> str:
        return f"{self.platform}_{self.item_id}"

class PlatformRegistry:
    def __init__(self, adapters: Iterable[PlatformAdapter] = ()):
        self._adapters: dict[str, PlatformAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: PlatformAdapter) -> None:
        name = adapter.descriptor.name
        if name in self._adapters:
            raise DuplicatePlatformError(name)
        self._adapters[name] = adapter

    def get(self, name: str) -> PlatformAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise UnknownPlatformError(name) from exc

    def detect(self, target: str) -> PlatformAdapter:
        matches = [adapter for adapter in self._adapters.values() if adapter.matches(target)]
        if not matches:
            raise PlatformNotDetectedError(target)
        if len(matches) > 1:
            raise AmbiguousPlatformError(target, [x.descriptor.name for x in matches])
        return matches[0]

    def list_descriptors(self) -> Sequence[PlatformDescriptor]:
        return tuple(x.descriptor for x in self._adapters.values())
```

- [x] **Step 4: Run focused tests**

Run: `python -m pytest tests/platforms/test_models.py tests/platforms/test_registry.py -q`

Expected: all focused tests pass.

- [x] **Step 5: Commit**

```bash
git add src/platforms tests/platforms
git commit -m "feat: add platform adapter contracts"
```

### Task 2: Bilibili Adapter and Legacy Mapping

**Files:**
- Create: `src/platforms/bilibili/__init__.py`
- Create: `src/platforms/bilibili/adapter.py`
- Modify: `src/crawl/video_list.py`
- Modify: `src/crawl/audio_download.py`
- Test: `tests/platforms/test_bilibili_adapter.py`

**Interfaces:**
- Consumes: Task 1 platform contracts.
- Produces: `BilibiliAdapter.matches/resolve/get_creator/iter_items/refresh_item/download_assets`.
- Maps `uid → creator_id`, `bvid → item_id`, and legacy artifacts to `bilibili_<bvid>` without changing old file names.

- [x] **Step 1: Write failing mapping and delegation tests**

```python
def test_bilibili_video_maps_to_source_item():
    adapter = BilibiliAdapter(config=make_config(), crawl_fn=Mock())
    item = adapter.map_video({"bvid": "BV1abc", "title": "T", "duration": "01:30"}, "42")
    assert (item.platform, item.item_id, item.creator_id) == ("bilibili", "BV1abc", "42")
    assert item.source_id == "bilibili_BV1abc"
    assert item.duration_seconds == 90

def test_download_assets_delegates_to_existing_audio_download(tmp_path):
    download = Mock(return_value=tmp_path / "BV1abc.m4a")
    adapter = BilibiliAdapter(make_config(), download_fn=download)
    result = adapter.download_assets(make_bili_item(), tmp_path, progress=Mock())
    assert result.audio_path.name == "BV1abc.m4a"
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/platforms/test_bilibili_adapter.py -q`

Expected: import or attribute failure for `BilibiliAdapter`.

- [x] **Step 3: Implement a thin adapter over existing crawl functions**

```python
class BilibiliAdapter:
    descriptor = PlatformDescriptor(name="bilibili", item_types=frozenset({ItemType.VIDEO}))

    def map_video(self, raw: Mapping[str, Any], creator_id: str) -> SourceItem:
        bvid = str(raw["bvid"])
        return SourceItem(
            platform="bilibili",
            item_id=bvid,
            creator_id=creator_id,
            item_type=ItemType.VIDEO,
            title=str(raw.get("title") or bvid),
            description=str(raw.get("description") or ""),
            canonical_url=f"https://www.bilibili.com/video/{bvid}",
            duration_seconds=parse_duration_str(str(raw.get("duration") or "0")),
            raw_metadata=dict(raw),
        )
```

- [x] **Step 4: Run adapter and existing crawl tests**

Run: `python -m pytest tests/platforms/test_bilibili_adapter.py tests/test_audio_download.py -q`

Expected: all selected tests pass.

- [x] **Step 5: Commit**

```bash
git add src/platforms/bilibili src/crawl tests/platforms/test_bilibili_adapter.py
git commit -m "feat: adapt bilibili to platform interface"
```

### Task 3: Output Registry and Episode Markdown

**Files:**
- Create: `src/outputs/__init__.py`
- Create: `src/outputs/base.py`
- Create: `src/outputs/errors.py`
- Create: `src/outputs/registry.py`
- Create: `src/outputs/manager.py`
- Create: `src/outputs/files.py`
- Create: `src/outputs/episodes.py`
- Test: `tests/outputs/test_registry.py`
- Test: `tests/outputs/test_episodes.py`

**Interfaces:**
- Produces: `ArtifactKind`, `ItemOutputContext`, `CorpusOutputContext`, `OutputReceipt`, `OutputTarget`, `OutputRegistry`, `OutputManager`, `EpisodeMarkdownTarget`.
- Episode path is `output/<safe-name>-<platform>-<creator-id>/episodes/<item-id>.md`.

- [x] **Step 1: Write failing output tests**

```python
def test_episode_uses_stable_item_id_filename(tmp_path):
    receipt = EpisodeMarkdownTarget(tmp_path).consume_item(make_output_context(title='A/B:*?'))
    assert receipt.path.name == "123.md"
    text = receipt.path.read_text("utf-8")
    assert "作品 ID: 123" in text
    assert "转写正文" in text and "清洗正文" in text and "知识点" in text

def test_output_manager_unions_required_artifacts():
    manager = OutputManager([FakeTarget({ArtifactKind.CLEANED}), FakeTarget({ArtifactKind.KNOWLEDGE})])
    assert manager.required_artifacts() == {ArtifactKind.CLEANED, ArtifactKind.KNOWLEDGE}
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/outputs/test_registry.py tests/outputs/test_episodes.py -q`

Expected: missing output modules.

- [x] **Step 3: Implement output contracts and atomic episode rendering**

```python
class EpisodeMarkdownTarget:
    name = "episodes"

    def required_artifacts(self) -> frozenset[ArtifactKind]:
        return frozenset({ArtifactKind.TRANSCRIPT, ArtifactKind.CLEANED, ArtifactKind.KNOWLEDGE})

    def consume_item(self, context: ItemOutputContext) -> OutputReceipt:
        path = context.creator_output_dir / "episodes" / f"{context.item.item_id}.md"
        content = render_episode(context)
        atomic_write_text(path, content, validator=validate_episode_markdown)
        return OutputReceipt(self.name, context.item.source_id, path, sha256_text(content))
```

- [x] **Step 4: Run focused tests**

Run: `python -m pytest tests/outputs -q`

Expected: output tests pass.

- [x] **Step 5: Commit**

```bash
git add src/outputs tests/outputs
git commit -m "feat: add composable episode output"
```

### Task 4: Skill and RAG Output Targets

**Files:**
- Create: `src/outputs/skill.py`
- Create: `src/outputs/rag.py`
- Modify: `src/model/knowledge_extractor.py`
- Modify: `src/generate/skill_generator.py`
- Modify: `src/rag/chunker.py`
- Test: `tests/outputs/test_skill.py`
- Test: `tests/outputs/test_rag.py`
- Modify: `tests/test_knowledge_extractor.py`
- Modify: `tests/test_chunker.py`

**Interfaces:**
- Consumes: Task 3 output protocol and existing `merge_knowledge`, `SkillGenerator`, `build_chunks`.
- Produces: `SkillTarget`, `RagTarget`, `corpus_fingerprint(items)`.
- Fingerprint is SHA-256 of sorted `(source_id, knowledge_sha256)` pairs.

- [x] **Step 1: Write failing fingerprint, partial, and source-id tests**

```python
def test_skill_skips_when_corpus_fingerprint_matches(tmp_path):
    target = SkillTarget(tmp_path, merge_fn=Mock(), generator=Mock())
    context = make_corpus_context(previous_fingerprint="abc", fingerprint="abc")
    receipt = target.finalize(context)
    assert receipt.skipped is True
    target.merge_fn.assert_not_called()

def test_partial_skill_records_coverage(tmp_path):
    receipt = make_skill_target(tmp_path).finalize(make_corpus_context(total=10, completed=8, unsupported=2))
    assert receipt.metadata["partial"] is True
    assert receipt.metadata["coverage"] == 0.8
```

- [x] **Step 2: Run selected tests and verify failure**

Run: `python -m pytest tests/outputs/test_skill.py tests/outputs/test_rag.py tests/test_chunker.py -q`

Expected: new target imports fail.

- [x] **Step 3: Implement wrappers and platform-neutral metadata**

```python
def corpus_fingerprint(items: Iterable[KnowledgeArtifact]) -> str:
    canonical = "\n".join(f"{x.source_id}:{x.sha256}" for x in sorted(items, key=lambda x: x.source_id))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

class SkillTarget:
    name = "skill"
    def required_artifacts(self) -> frozenset[ArtifactKind]:
        return frozenset({ArtifactKind.KNOWLEDGE})
    def finalize(self, context: CorpusOutputContext) -> OutputReceipt:
        fingerprint = corpus_fingerprint(context.knowledge_artifacts)
        if fingerprint == context.previous_fingerprint and context.skill_path.exists():
            return OutputReceipt(self.name, "corpus", context.skill_path, fingerprint, skipped=True)
        profile = self.merge_fn([artifact.knowledge for artifact in context.knowledge_artifacts])
        content = self.generator.generate(profile)
        atomic_write_text(context.skill_path, content, validator=validate_skill_markdown)
        return OutputReceipt(self.name, "corpus", context.skill_path, fingerprint, skipped=False)
```

- [x] **Step 4: Run output/model/RAG tests**

Run: `python -m pytest tests/outputs tests/test_knowledge_extractor.py tests/test_chunker.py -q`

Expected: all selected tests pass, including legacy Bilibili fixtures.

- [ ] **Step 5: Commit**

```bash
git add src/outputs src/model/knowledge_extractor.py src/generate/skill_generator.py src/rag/chunker.py tests
git commit -m "feat: add skill and rag output targets"
```

### Task 5: Atomic Artifact and Job State Stores

**Files:**
- Create: `src/distillation/__init__.py`
- Create: `src/distillation/artifacts.py`
- Create: `src/distillation/store.py`
- Create: `src/distillation/state.py`
- Test: `tests/distillation/test_store.py`
- Test: `tests/distillation/test_state.py`

**Interfaces:**
- Produces: `atomic_write_bytes`, `atomic_write_json`, `ArtifactRecord`, `ItemState`, `JobState`, `JobStateStore.load/save/recover_item`.
- Every successful `save` increments `JobState.revision`.

- [x] **Step 1: Write failing atomicity, corruption, and recovery tests**

```python
def test_atomic_json_fsyncs_then_replaces(tmp_path, monkeypatch):
    replace = Mock(wraps=os.replace)
    monkeypatch.setattr(os, "replace", replace)
    atomic_write_json(tmp_path / "state.json", {"schema_version": 1})
    assert json.loads((tmp_path / "state.json").read_text("utf-8"))["schema_version"] == 1
    replace.assert_called_once()

def test_corrupt_state_is_not_treated_as_new_job(tmp_path):
    path = tmp_path / "job_state.json"
    path.write_text("{broken", "utf-8")
    with pytest.raises(StateCorruptionError):
        JobStateStore(path).load()

def test_completed_item_with_invalid_transcript_recovers_to_transcribing():
    state = make_completed_item(transcript_valid=False)
    assert recover_item(state).processing_status == ProcessingStatus.TRANSCRIBING
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/distillation/test_store.py tests/distillation/test_state.py -q`

Expected: missing store/state modules.

- [x] **Step 3: Implement atomic writes, schema migration, integrity records, and recovery**

```python
def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    atomic_write_bytes(path, payload, validator=lambda p: json.loads(p.read_text("utf-8")))

class JobStateStore:
    def load(self) -> JobState:
        try:
            return migrate_state(json.loads(self.path.read_text("utf-8")))
        except (OSError, ValueError, ValidationError) as exc:
            raise StateCorruptionError(self.path) from exc

    def save(self, state: JobState, *, expected_revision: int | None = None) -> JobState:
        current = self.load() if self.path.exists() else None
        if expected_revision is not None and (current is None or current.revision != expected_revision):
            raise RevisionConflict(expected_revision, None if current is None else current.revision)
        updated = replace(state, revision=(0 if current is None else current.revision) + 1)
        atomic_write_json(self.path, asdict(updated))
        return updated
```

- [x] **Step 4: Run state tests**

Run: `python -m pytest tests/distillation/test_store.py tests/distillation/test_state.py -q`

Expected: all selected tests pass on Windows; POSIX directory fsync is conditionally exercised.

- [ ] **Step 5: Commit**

```bash
git add src/distillation tests/distillation
git commit -m "feat: add atomic distillation state store"
```

### Task 6: Application Service, Events, and Job Leases

**Files:**
- Create: `src/application/__init__.py`
- Create: `src/application/errors.py`
- Create: `src/application/events.py`
- Create: `src/application/leases.py`
- Create: `src/application/commands.py`
- Create: `src/application/queries.py`
- Create: `src/application/service.py`
- Test: `tests/application/test_events.py`
- Test: `tests/application/test_leases.py`
- Test: `tests/application/test_service.py`

**Interfaces:**
- Consumes: Task 5 state store.
- Produces: `ApplicationEvent`, `EventHub.publish/subscribe/snapshot`, `JobLeaseManager.acquire/heartbeat/release`, `DistillationService.preview/create/pause/resume/retry_failed/retry_item`.

- [x] **Step 1: Write failing lease, event, and revision tests**

```python
def test_live_lease_cannot_be_stolen(tmp_path):
    manager = JobLeaseManager(tmp_path, pid_alive=lambda pid: True)
    lease = manager.acquire("job-1", owner="cli")
    with pytest.raises(JobLeaseConflict):
        manager.acquire("job-1", owner="dashboard")
    lease.release()

def test_event_hub_uses_monotonic_ids():
    hub = EventHub(capacity=3)
    assert hub.publish("job.updated", {"job_id": "1"}).event_id == 1
    assert hub.publish("job.updated", {"job_id": "1"}).event_id == 2

def test_pause_rejects_stale_revision():
    with pytest.raises(RevisionConflict):
        make_service(revision=3).pause("job-1", expected_revision=2)
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/application -q`

Expected: missing application modules.

- [x] **Step 3: Implement presentation-neutral commands, queries, events, and leases**

```python
@dataclass(frozen=True)
class ApplicationEvent:
    event_id: int
    event_type: str
    timestamp: datetime
    payload: Mapping[str, Any]

class DistillationService:
    def preview(self, request: PreviewRequest) -> PreviewResult:
        return self.commands.preview(request)

    def create(self, request: CreateJobRequest) -> JobView:
        return self.commands.create(request)

    def pause(self, job_id: str, expected_revision: int) -> JobView:
        return self.commands.pause(job_id, expected_revision)

    def resume(self, job_id: str, expected_revision: int) -> JobView:
        return self.commands.resume(job_id, expected_revision)
```

- [x] **Step 4: Run application and state tests**

Run: `python -m pytest tests/application tests/distillation/test_state.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/application tests/application
git commit -m "feat: add shared distillation application service"
```

### Task 7: Douyin Session and Share-Link Resolver

**Files:**
- Create: `src/platforms/douyin/__init__.py`
- Create: `src/platforms/douyin/session.py`
- Create: `src/platforms/douyin/resolver.py`
- Create: `src/platforms/douyin/adapter.py`
- Test: `tests/platforms/douyin/test_session.py`
- Test: `tests/platforms/douyin/test_resolver.py`

**Interfaces:**
- Consumes: Task 1 platform protocol and Task 6 lease concepts.
- Produces: `DouyinSession`, `DouyinResolver.resolve_share_url`, `DouyinAdapter.resolve/auth_status/authenticate`.
- Browser profile lives below configured `data_dir/browser/douyin`.

- [x] **Step 1: Write failing session and resolver tests**

```python
def test_share_url_resolves_final_url_and_sec_uid():
    page = FakePage(final_url="https://www.douyin.com/user/SEC_UID", sec_uid="SEC_UID")
    result = DouyinResolver(page).resolve_share_url("https://v.douyin.com/abc/")
    assert result.creator_id == "SEC_UID"
    assert result.canonical_url.startswith("https://www.douyin.com/user/")

def test_expired_auth_returns_actionable_status(tmp_path):
    session = DouyinSession(tmp_path, browser_factory=expired_browser)
    assert session.auth_status().status == "expired"
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/platforms/douyin/test_session.py tests/platforms/douyin/test_resolver.py -q`

Expected: missing Douyin modules.

- [x] **Step 3: Implement persistent profile, exclusive lock, login, expiry, and resolver**

```python
class DouyinResolver:
    def resolve_share_url(self, target: str) -> ResolvedTarget:
        self.page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)
        final_url = self.page.url
        creator_id = extract_sec_uid(final_url) or self._capture_sec_uid_from_api()
        if not creator_id:
            raise TargetResolutionError("无法从分享链接解析 sec_uid")
        return ResolvedTarget("douyin", creator_id, final_url)
```

- [x] **Step 4: Run tests without a real browser**

Run: `python -m pytest tests/platforms/douyin/test_session.py tests/platforms/douyin/test_resolver.py -q`

Expected: all tests pass with fake Playwright objects.

- [ ] **Step 5: Commit**

```bash
git add src/platforms/douyin tests/platforms/douyin
git commit -m "feat: add douyin session and resolver"
```

### Task 8: Douyin Account Enumeration

**Files:**
- Create: `src/platforms/douyin/enumerator.py`
- Modify: `src/platforms/douyin/adapter.py`
- Test: `tests/platforms/douyin/test_enumerator.py`

**Interfaces:**
- Consumes: Task 7 session and resolver.
- Produces: `DouyinEnumerator.iter_pages(creator, checkpoint)` and raw aweme-to-`SourceItem` mapping.

- [x] **Step 1: Write failing pagination, dedup, resume, and incremental tests**

```python
def test_pages_stop_on_has_more_false_and_deduplicate():
    responses = [page(cursor=0, ids=["1", "2"], has_more=True), page(cursor=2, ids=["2", "3"], has_more=False)]
    pages = list(DouyinEnumerator(fake_route(responses)).iter_pages(make_creator(), None))
    assert [i.item_id for p in pages for i in p.items] == ["1", "2", "3"]
    assert pages[-1].checkpoint.complete is True

def test_resume_starts_from_saved_cursor():
    enum = DouyinEnumerator(fake_route([page(cursor=20, ids=["9"], has_more=False)]))
    list(enum.iter_pages(make_creator(), EnumerationCheckpoint(cursor="20", seen_ids=frozenset({"1"}))))
    assert enum.requested_cursors == ["20"]
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/platforms/douyin/test_enumerator.py -q`

Expected: missing enumerator.

- [x] **Step 3: Implement API-response-only mapping and checkpoint pages**

```python
def map_aweme(raw: Mapping[str, Any], creator_id: str) -> SourceItem:
    kind = {2: ItemType.GALLERY, 4: ItemType.VIDEO}.get(raw.get("aweme_type"), ItemType.UNKNOWN)
    return SourceItem(
        platform="douyin",
        item_id=str(raw["aweme_id"]),
        creator_id=creator_id,
        item_type=kind,
        title=derive_title(raw),
        description=str(raw.get("desc") or ""),
        canonical_url=f"https://www.douyin.com/video/{raw['aweme_id']}",
        assets=map_assets(raw, kind),
        raw_metadata=sanitize_raw_metadata(raw),
    )
```

- [x] **Step 4: Run enumerator tests**

Run: `python -m pytest tests/platforms/douyin/test_enumerator.py -q`

Expected: pagination, dedup, has_more, resume, and incremental boundary tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/platforms/douyin tests/platforms/douyin/test_enumerator.py
git commit -m "feat: enumerate douyin creator works"
```

### Task 9: Douyin Download and Content Processing

**Files:**
- Create: `src/platforms/douyin/downloader.py`
- Create: `src/distillation/processors.py`
- Modify: `src/platforms/douyin/adapter.py`
- Modify: `src/asr/funasr_engine.py`
- Test: `tests/platforms/douyin/test_downloader.py`
- Test: `tests/distillation/test_processors.py`
- Test: `tests/distillation/test_media_cleanup.py`

**Interfaces:**
- Produces: `DouyinDownloader.download`, `VideoContentProcessor.prepare`, `VideoContentProcessor.transcribe`, `VideoContentProcessor.enrich`, `UnsupportedProcessor.process`, `safe_cleanup_media`.
- Progress callback is `Callable[[TransferProgress], None]` with bytes completed/total, bytes per second, and timestamp.

- [x] **Step 1: Write failing download, unsupported, and cleanup tests**

```python
def test_downloader_reports_real_bytes(tmp_path):
    progress = []
    result = DouyinDownloader(fake_http([b"abc", b"def"])).download(make_item(), tmp_path, progress.append)
    assert result.video_path.read_bytes() == b"abcdef"
    assert progress[-1].completed_bytes == 6

def test_expired_media_url_is_refreshed_once(tmp_path):
    refresh = Mock(return_value=make_item(media_url="https://fresh.example/video"))
    downloader = DouyinDownloader(fake_http_statuses([403, 200]), refresh_item=refresh)
    downloader.download(make_item(media_url="https://expired.example/video"), tmp_path, Mock())
    refresh.assert_called_once()

def test_gallery_is_explicitly_unsupported():
    result = UnsupportedProcessor().process(make_item(item_type=ItemType.GALLERY))
    assert result.status == ProcessingStatus.UNSUPPORTED
    assert result.error_code == "unsupported_note"

def test_media_is_not_deleted_until_transcript_reopens_valid(tmp_path):
    media = write_media(tmp_path)
    assert safe_cleanup_media(media, transcript_path=write_invalid_transcript(tmp_path)) is False
    assert media.exists()
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/platforms/douyin/test_downloader.py tests/distillation/test_processors.py tests/distillation/test_media_cleanup.py -q`

Expected: missing downloader/processors.

- [x] **Step 3: Implement streaming download, separate stage methods, existing ASR/clean/model calls, and verified cleanup**

```python
class VideoContentProcessor:
    def prepare(self, item: SourceItem, assets: DownloadedAssets) -> PreparedMedia:
        audio = self.audio_extractor.extract(assets.video_path)
        return PreparedMedia(item=item, audio_path=audio, assets=assets)

    def transcribe(self, prepared: PreparedMedia) -> TranscriptArtifact:
        transcript = self.asr.transcribe(prepared.audio_path)
        transcript_path = self.artifacts.save_transcript(prepared.item, transcript)
        if not self.artifacts.verify_transcript(transcript_path):
            raise ArtifactIntegrityError(prepared.item.source_id, "transcript")
        return TranscriptArtifact(item=prepared.item, path=transcript_path, transcript=transcript)

    def enrich(self, artifact: TranscriptArtifact) -> EnrichedArtifacts:
        cleaned = self.cleaner.process(artifact.transcript.text)
        knowledge = self.extractor.extract(cleaned, source_id=artifact.item.source_id)
        return EnrichedArtifacts(transcript=artifact, cleaned=cleaned, knowledge=knowledge)
```

- [x] **Step 4: Run processor and existing ASR tests**

Run: `python -m pytest tests/platforms/douyin/test_downloader.py tests/distillation/test_processors.py tests/distillation/test_media_cleanup.py tests/test_asr_pipeline.py -q`

Expected: all selected tests pass and ASR fixtures retain compatibility.

- [ ] **Step 5: Commit**

```bash
git add src/platforms/douyin src/distillation/processors.py src/asr/funasr_engine.py tests
git commit -m "feat: process douyin video artifacts"
```

### Task 10: Staged Engine and Supervisor

**Files:**
- Create: `src/distillation/request.py`
- Create: `src/distillation/engine.py`
- Create: `src/distillation/supervisor.py`
- Test: `tests/distillation/test_engine.py`
- Test: `tests/distillation/test_supervisor.py`

**Interfaces:**
- Consumes: platform/output managers, state store, processors, events.
- Produces: `DistillationRequest`, `DistillationEngine.run`, cooperative pause, bounded stage queues, `WorkerSupervisor`.

- [ ] **Step 1: Write failing concurrency and failure-isolation tests**

```python
@pytest.mark.asyncio
async def test_stage_limits_and_single_asr_initialization():
    probes = StageProbes()
    engine = make_engine(probes, download_workers=3, asr_workers=1, llm_workers=3, max_active=3)
    await engine.run(make_items(8))
    assert probes.max_download <= 3
    assert probes.max_asr == 1
    assert probes.max_llm <= 3
    assert probes.max_active <= 3
    assert probes.asr_initializations == 1

@pytest.mark.asyncio
async def test_one_item_failure_does_not_stop_batch():
    result = await make_engine(fail_source_id="douyin_2").run(make_items(3))
    assert result.completed == 2 and result.failed == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/distillation/test_engine.py tests/distillation/test_supervisor.py -q`

Expected: missing engine/supervisor.

- [ ] **Step 3: Implement bounded queues, one ASR consumer, retry policy, pause safe points, and worker restart budget**

```python
class DistillationEngine:
    async def run(self, request: DistillationRequest) -> JobResult:
        self._download_q = asyncio.Queue(maxsize=request.download_workers * 2)
        self._asr_q = asyncio.Queue(maxsize=max(2, request.max_active_items))
        self._llm_q = asyncio.Queue(maxsize=request.llm_workers * 2)
        async with self.supervisor.worker_group():
            await self._enumerate_and_feed(request)
        return self._finalize_result()
```

- [ ] **Step 4: Run engine/state/application tests**

Run: `python -m pytest tests/distillation/test_engine.py tests/distillation/test_supervisor.py tests/application -q`

Expected: all selected tests pass, including interrupted-item recovery.

- [ ] **Step 5: Commit**

```bash
git add src/distillation src/application tests/distillation
git commit -m "feat: add recoverable staged distillation engine"
```

### Task 11: Shared Progress, Rich Live, and Dual ETA

**Files:**
- Create: `src/distillation/progress.py`
- Create: `src/distillation/eta.py`
- Test: `tests/distillation/test_progress.py`
- Test: `tests/distillation/test_eta.py`

**Interfaces:**
- Produces: `ProgressSnapshot`, `ItemProgress`, `TransferProgress`, `EtaEstimate`, `ProgressTracker.snapshot`, `EtaEstimator.update/estimate_total/estimate_active_slowest`, `RichProgressView`.

- [ ] **Step 1: Write failing fixed-row, coverage, and ETA tests**

```python
def test_same_source_id_keeps_same_active_row():
    tracker = ProgressTracker(max_active=3)
    first = tracker.update("douyin_1", stage="downloading", stage_progress=.2).row_id
    second = tracker.update("douyin_1", stage="transcribing", stage_progress=.1).row_id
    assert first == second

def test_unsupported_item_prevents_full_completion():
    snapshot = make_snapshot(completed=9, unsupported=1, total=10)
    assert snapshot.coverage == 0.9
    assert snapshot.is_complete is False

def test_eta_requires_three_samples():
    estimator = EtaEstimator(min_samples=3)
    estimator.update("asr", work=60, elapsed=20)
    assert estimator.estimate_total(make_remaining()) is None
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/distillation/test_progress.py tests/distillation/test_eta.py -q`

Expected: missing progress/ETA modules.

- [ ] **Step 3: Implement weighted progress, real transfer metrics, rolling medians, provisional total ETA, and Rich rendering**

```python
@dataclass(frozen=True)
class ProgressSnapshot:
    job_id: str
    revision: int
    overall_progress: float
    coverage: float
    active_items: Sequence[ItemProgress]
    counts: ProgressCounts
    eta_total_seconds: float | None
    eta_active_slowest_seconds: float | None
    provisional_eta: bool
```

- [ ] **Step 4: Run progress/ETA and engine tests**

Run: `python -m pytest tests/distillation/test_progress.py tests/distillation/test_eta.py tests/distillation/test_engine.py -q`

Expected: all selected tests pass and sample-poor ETA is `None`/estimating.

- [ ] **Step 5: Commit**

```bash
git add src/distillation/progress.py src/distillation/eta.py tests/distillation
git commit -m "feat: add shared progress and dual eta"
```

### Task 12: CLI, Configuration, Documentation, and Release Baseline

**Files:**
- Modify: `main.py`
- Modify: `src/config.py`
- Modify: `config.example.env`
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Modify: `tests/test_auth.py`
- Create: `tests/test_source_cli.py`
- Modify: `README.md`
- Modify: `DEVELOPMENT.md`

**Interfaces:**
- Consumes: all previous core tasks.
- Produces: `source platforms/status/login/creator` commands and legacy `run --uid` delegation.

- [ ] **Step 1: Write failing CLI/default/permission tests**

```python
def test_source_creator_defaults_to_both_and_three_one_three(runner):
    result = runner.invoke(cli, ["source", "creator", "https://v.douyin.com/x/", "--dry-run"])
    assert result.exit_code == 0
    request = captured_request()
    assert request.emit == ("episodes", "skill")
    assert (request.download_workers, request.asr_workers, request.llm_workers) == (3, 1, 3)

@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits are not enforced by Windows")
def test_file_permission_is_600(tmp_path):
    cache = tmp_path / "cache.json"
    save_credential(make_credential(), "", cache)
    assert cache.stat().st_mode & 0o777 == 0o600
```

- [ ] **Step 2: Run CLI/auth tests and verify the new CLI test fails**

Run: `python -m pytest tests/test_source_cli.py tests/test_auth.py -q`

Expected: source command missing; Windows permission test is skipped rather than failed.

- [ ] **Step 3: Implement Click group, config defaults, dependency pin, ignore rules, and compatibility delegation**

```python
@cli.group()
def source():
    """管理内容平台并蒸馏创作者作品。"""

@source.command("creator")
@click.argument("target")
@click.option("--platform", default="auto")
@click.option("--emit", type=click.Choice(["episodes", "skill", "both"]), default="both")
@click.option("--download-workers", default=3, type=click.IntRange(min=1))
@click.option("--asr-workers", default=1, type=click.IntRange(min=1))
@click.option("--llm-workers", default=3, type=click.IntRange(min=1))
def source_creator(target, platform, emit, download_workers, asr_workers, llm_workers, **options):
    request = build_distillation_request(
        target=target,
        platform=platform,
        emit=emit,
        download_workers=download_workers,
        asr_workers=asr_workers,
        llm_workers=llm_workers,
        options=options,
    )
    result = get_distillation_service().run(request)
    raise SystemExit(result.exit_code)
```

- [ ] **Step 4: Run full tests and CLI smoke checks**

Run: `python -m pytest -q`

Expected: all tests pass; the old Windows-only permission failure is skipped with an explicit reason.

Run: `python main.py source --help`

Expected: platforms, status, login, and creator commands are listed.

Run: `python main.py source creator --help`

Expected: concurrency, resume, retry, keep-media, headful, dry-run, emit, and RAG options are documented.

- [ ] **Step 5: Review secrets and commit**

Run: `git diff --check && git grep -n -I -E "(SESSDATA=|Authorization:|sk-[A-Za-z0-9]|C:\\\\Users\\\\)" -- . ':!docs/superpowers'`

Expected: no sensitive value or hard-coded user path is found.

```bash
git add main.py src/config.py config.example.env requirements.txt .gitignore tests README.md DEVELOPMENT.md
git commit -m "feat: expose multi-platform creator distillation"
```

## Core Plan Completion Gate

- [ ] Run `python -m pytest -q` and record exact pass/skip counts.
- [ ] Run all new CLI help and dry-run fixture checks.
- [ ] Inspect `git diff origin/main..HEAD --stat` and ensure only scoped source, tests, docs, and lock/config files appear.
- [ ] Confirm no Scout source, `.superpowers`, profile, Cookie, media, state, real output, model, or machine path is tracked.
- [ ] Request code review before beginning the Dashboard plan.
