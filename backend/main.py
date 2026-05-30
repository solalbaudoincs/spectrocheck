"""FastAPI app for the transcode detector.

Endpoints
  GET  /api/health
  GET  /api/rekordbox/playlists       list playlists from the desktop master.db
  GET  /api/rekordbox/usb-roots       auto-detected exported-USB Contents folders
  POST /api/scan                      start a scan (folder OR rekordbox playlist)
  GET  /api/scan/{id}                 full current results (polling fallback)
  GET  /api/scan/{id}/events          SSE stream of per-file results
  GET  /api/scan/{id}/export          download results as csv|json
  GET  /api/spectrogram               on-demand PNG spectrogram for one file
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import ffmpeg_tools, rekordbox_source, scanner, spectrogram

MAX_WORKERS = min(4, (os.cpu_count() or 4))
EXEC = ThreadPoolExecutor(max_workers=MAX_WORKERS + 2)

# Field order for CSV export.
CSV_FIELDS = [
    "name", "verdict", "confidence", "codec", "declaredKbps", "sampleRate",
    "cutoffKhz", "expectedCutoffKhz", "trueQuality", "shelfDetected",
    "durationSec", "artist", "title", "match", "file", "reason",
]


def _lifespan_check():
    ffmpeg_tools.check_binaries()


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    _lifespan_check()  # fail fast if ffmpeg/ffprobe are missing
    yield


app = FastAPI(title="Transcode Detector", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

SCANS: dict[str, "ScanJob"] = {}
_COVER_CACHE: dict[str, bytes | None] = {}


class ScanRequest(BaseModel):
    path: str | None = None          # folder scan
    playlist: str | None = None      # rekordbox playlist (name or id)
    contentsRoot: str | None = None  # USB Contents folder to map onto
    dbDir: str | None = None
    key: str | None = None


class ScanJob:
    def __init__(self, job_id: str, items: list[dict], mode: str):
        self.id = job_id
        self.items = items
        self.mode = mode
        self.total = len(items)
        self.results: list[dict] = []
        self.done = False
        self.error: str | None = None
        self.queue: asyncio.Queue = asyncio.Queue()


# --------------------------------------------------------------------------- #
# Resolving the scan target into a list of {path, extra} items.
# --------------------------------------------------------------------------- #
def _resolve_items(req: ScanRequest) -> tuple[list[dict], str]:
    if req.playlist:
        db = rekordbox_source.open_database(req.dbDir, req.key)
        contents = req.contentsRoot
        if not contents:
            roots = rekordbox_source.find_usb_contents_roots()
            contents = roots[0] if roots else None
        tracks = rekordbox_source.resolve_playlist(db, req.playlist, contents)
        items = []
        for t in tracks:
            extra = {
                "title": t.title, "artist": t.artist, "match": t.match,
                "usbPath": t.usb_path, "originalPath": t.original_path,
                "declaredKbpsRB": t.declared_kbps,
            }
            items.append({"path": t.analyze_path, "extra": extra})
        return items, "rekordbox"

    if req.path:
        if not os.path.isdir(req.path):
            raise HTTPException(400, f"Folder not found: {req.path}")
        paths = list(scanner.iter_audio_files(req.path))
        return [{"path": p, "extra": {}} for p in paths], "folder"

    raise HTTPException(400, "Provide either 'path' (folder) or 'playlist'.")


async def _run_job(job: ScanJob):
    loop = asyncio.get_running_loop()
    sem = asyncio.Semaphore(MAX_WORKERS)

    async def worker(item: dict):
        async with sem:
            if not item["path"]:
                rec = scanner.error_record(
                    item["extra"].get("originalPath") or item["extra"].get("title") or "?",
                    "File not found on USB or at its original location.",
                )
            else:
                rec = await loop.run_in_executor(EXEC, scanner.analyze_file, item["path"])
            rec.update(item["extra"])
            job.results.append(rec)
            await job.queue.put({"type": "result", "data": rec})

    try:
        await asyncio.gather(*(worker(it) for it in job.items))
    except Exception as exc:  # noqa: BLE001
        job.error = str(exc)
    job.done = True
    await job.queue.put({"type": "done", "data": {
        "total": job.total, "done": len(job.results), "error": job.error}})


# --------------------------------------------------------------------------- #
# Endpoints.
# --------------------------------------------------------------------------- #
@app.get("/api/health")
async def health():
    try:
        ffmpeg_tools.check_binaries()
        return {"ok": True, "ffmpeg": ffmpeg_tools.ffmpeg_version()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.get("/api/rekordbox/usb-roots")
async def usb_roots():
    return {"roots": rekordbox_source.find_usb_contents_roots()}


@app.get("/api/rekordbox/playlists")
async def playlists():
    """Playlists plus source metadata (Rekordbox version, db path, USB roots)."""
    loop = asyncio.get_running_loop()

    def work():
        info = rekordbox_source.rekordbox_info()
        roots = rekordbox_source.find_usb_contents_roots()
        library_count = 0
        if roots:
            try:
                library_count = sum(1 for _ in scanner.iter_audio_files(roots[0]))
            except Exception:  # noqa: BLE001
                library_count = 0
        try:
            db = rekordbox_source.open_database()
            pls = [asdict(p) for p in rekordbox_source.list_playlists(db)]
            return {"available": True, "playlists": pls, "usbRoots": roots,
                    "libraryCount": library_count, **info}
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "error": str(exc), "playlists": [],
                    "usbRoots": roots, "libraryCount": library_count, **info}

    return await loop.run_in_executor(EXEC, work)


@app.post("/api/scan")
async def start_scan(req: ScanRequest):
    loop = asyncio.get_running_loop()
    try:
        items, mode = await loop.run_in_executor(EXEC, _resolve_items, req)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not resolve scan target: {exc}")
    job = ScanJob(uuid.uuid4().hex, items, mode)
    SCANS[job.id] = job
    # Bound memory: keep only the most recent jobs (insertion order preserved).
    if len(SCANS) > 50:
        for old in list(SCANS)[:-50]:
            SCANS.pop(old, None)
    asyncio.create_task(_run_job(job))
    return {"scanId": job.id, "total": job.total, "mode": mode}


@app.get("/api/scan/{scan_id}")
async def scan_results(scan_id: str):
    job = SCANS.get(scan_id)
    if not job:
        raise HTTPException(404, "Unknown scan id")
    return {
        "scanId": job.id, "mode": job.mode, "total": job.total,
        "done": len(job.results), "finished": job.done, "error": job.error,
        "results": job.results,
    }


@app.get("/api/scan/{scan_id}/events")
async def scan_events(scan_id: str, request: Request):
    job = SCANS.get(scan_id)
    if not job:
        raise HTTPException(404, "Unknown scan id")

    async def gen():
        while True:
            if await request.is_disconnected():
                break
            try:
                evt = await asyncio.wait_for(job.queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": evt["type"], "data": json.dumps(evt["data"])}
            if evt["type"] == "done":
                break

    return EventSourceResponse(gen())


@app.get("/api/scan/{scan_id}/export")
async def export(scan_id: str, format: str = Query("json"), verdicts: str | None = None):
    job = SCANS.get(scan_id)
    if not job:
        raise HTTPException(404, "Unknown scan id")

    rows = job.results
    if verdicts:
        wanted = {v.strip().upper() for v in verdicts.split(",") if v.strip()}
        rows = [r for r in rows if (r.get("verdict") or "").upper() in wanted]

    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return Response(
            content=buf.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="scan_{scan_id}.csv"'},
        )

    return Response(
        content=json.dumps(rows, indent=2), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="scan_{scan_id}.json"'},
    )


@app.get("/api/cover")
async def cover(file: str):
    if not os.path.isfile(file):
        raise HTTPException(404, "File not found")
    if file not in _COVER_CACHE:
        if len(_COVER_CACHE) > 4000:
            _COVER_CACHE.clear()
        loop = asyncio.get_running_loop()
        _COVER_CACHE[file] = await loop.run_in_executor(EXEC, ffmpeg_tools.extract_cover, file)
    data = _COVER_CACHE[file]
    if not data:
        raise HTTPException(404, "No embedded cover")
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=3600"})


@app.get("/api/spectrogram")
async def spectrogram_ep(
    file: str,
    expected: float | None = None,
    measured: float | None = None,
):
    if not os.path.isfile(file):
        raise HTTPException(404, f"File not found: {file}")
    loop = asyncio.get_running_loop()
    try:
        png = await loop.run_in_executor(
            EXEC, spectrogram.render_spectrogram_png, file, expected, measured
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Spectrogram failed: {exc}")
    return Response(content=png, media_type="image/png")


# Optionally serve a built frontend (single-launcher milestone).
_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(_DIST):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="static")
