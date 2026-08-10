"""SSE endpoint for redacted Dashboard progress events."""

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from src.dashboard.security import require_local_session
from src.dashboard.sse import event_stream

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.get("/events", dependencies=[Depends(require_local_session)])
async def events(
    request: Request,
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID"),
    job_id: str | None = Query(default=None, max_length=256),
):
    return StreamingResponse(
        event_stream(
            request.app.state.service,
            last_event_id,
            job_id,
            task_manager=getattr(request.app.state, "task_manager", None),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
