"""Glue: walk a folder (or a supplied file list), decode, analyse, build records.

A record matches the API shape from the build brief plus a few extra fields the
side panel uses (reason, shelf info, duration, channels).
"""

from __future__ import annotations

import os
import traceback

from . import ffmpeg_tools
from .analysis import analyze_samples
from .ffmpeg_tools import AUDIO_EXTS

# Decode at most this many seconds; the analyser then keeps the loudest ~60s.
ANALYZE_MAX_SECONDS = 300.0


def iter_audio_files(root: str):
    """Yield every audio file under ``root`` (recursive)."""
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in AUDIO_EXTS:
                yield os.path.join(dirpath, name)


def build_record(path: str, pr: "ffmpeg_tools.ProbeResult", det) -> dict:
    return {
        "file": path,
        "name": os.path.basename(path),
        "codec": pr.codec,
        "declaredKbps": pr.declared_kbps,
        "sampleRate": pr.sample_rate,
        "channels": pr.channels,
        "durationSec": round(pr.duration, 1),
        "cutoffKhz": round(det.cutoff_khz, 2),
        "expectedCutoffKhz": det.expected_cutoff_khz,
        "trueQuality": det.true_quality,
        "verdict": det.verdict,
        "confidence": round(det.confidence, 3),
        "shelfDetected": det.shelf_detected,
        "shelfSlopeDb": round(det.shelf_slope_db, 1),
        "reason": det.reason,
        "error": None,
    }


def error_record(path: str, message: str) -> dict:
    return {
        "file": path,
        "name": os.path.basename(path),
        "codec": "", "declaredKbps": None, "sampleRate": 0, "channels": 0,
        "durationSec": 0.0, "cutoffKhz": 0.0, "expectedCutoffKhz": 0.0,
        "trueQuality": "", "verdict": "ERROR", "confidence": 0.0,
        "shelfDetected": False, "shelfSlopeDb": 0.0,
        "reason": message, "error": message,
    }


def analyze_file(path: str) -> dict:
    """Probe + decode + analyse a single file into a record. Never raises."""
    try:
        pr = ffmpeg_tools.probe(path)
        if pr.sample_rate <= 0:
            return error_record(path, "Could not determine sample rate.")
        samples, sr = ffmpeg_tools.decode_mono_f32(path, pr.sample_rate, ANALYZE_MAX_SECONDS)
        det = analyze_samples(
            samples, sr, pr.declared_kbps, container=pr.container, codec=pr.codec
        )
        return build_record(path, pr, det)
    except Exception as exc:  # noqa: BLE001 - one bad file must not kill the scan
        return error_record(path, f"{type(exc).__name__}: {exc}".strip())
