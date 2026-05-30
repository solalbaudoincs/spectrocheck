"""Thin wrappers around ffprobe / ffmpeg.

ffmpeg + ffprobe are a hard dependency. :func:`check_binaries` is called at
startup and fails loudly with an actionable message if either is missing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE_BIN", "ffprobe")

# Audio extensions we are willing to scan.
AUDIO_EXTS = {
    ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg",
    ".opus", ".wma", ".aiff", ".aif", ".alac", ".ape", ".wv",
}

# Hide the console window ffmpeg/ffprobe would otherwise flash on Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class FFmpegMissingError(RuntimeError):
    pass


class DecodeError(RuntimeError):
    pass


@dataclass
class ProbeResult:
    codec: str
    container: str          # file extension without the dot, e.g. "mp3", "flac"
    sample_rate: int
    channels: int
    duration: float         # seconds
    declared_kbps: int | None


def check_binaries() -> None:
    """Raise :class:`FFmpegMissingError` if ffmpeg/ffprobe are not on PATH."""
    missing = [b for b in (FFMPEG, FFPROBE) if shutil.which(b) is None]
    if missing:
        raise FFmpegMissingError(
            f"Required binaries not found on PATH: {', '.join(missing)}. "
            "Install ffmpeg (which includes ffprobe) and make sure it is on your "
            "PATH — e.g. `winget install Gyan.FFmpeg`, `brew install ffmpeg`, or "
            "`apt install ffmpeg`."
        )


def ffmpeg_version() -> str:
    out = subprocess.run(
        [FFMPEG, "-version"], capture_output=True, text=True, creationflags=_NO_WINDOW
    )
    return (out.stdout or "").splitlines()[0] if out.stdout else "unknown"


def probe(path: str) -> ProbeResult:
    """Run ffprobe and extract codec, sample rate, channels, duration, bitrate."""
    cmd = [
        FFPROBE, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW
    )
    if proc.returncode != 0 or not proc.stdout:
        raise DecodeError(f"ffprobe failed for {path}: {proc.stderr.strip()[:200]}")

    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise DecodeError(f"No audio stream in {path}")

    fmt = data.get("format", {})
    codec = str(audio.get("codec_name", "")).lower()
    sample_rate = int(audio.get("sample_rate", 0) or 0)
    channels = int(audio.get("channels", 0) or 0)

    duration_raw = audio.get("duration") or fmt.get("duration") or 0
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError):
        duration = 0.0

    bitrate_raw = audio.get("bit_rate") or fmt.get("bit_rate")
    try:
        declared_kbps: int | None = round(int(bitrate_raw) / 1000) if bitrate_raw else None
    except (TypeError, ValueError):
        declared_kbps = None

    container = os.path.splitext(path)[1].lower().lstrip(".")
    return ProbeResult(codec, container, sample_rate, channels, duration, declared_kbps)


def decode_mono_f32(path: str, sample_rate: int, max_seconds: float | None = None):
    """Decode to mono float32 at the file's *native* sample rate.

    We deliberately do NOT resample: upsampling would invent a Nyquist ceiling
    and hide the very cutoff we are trying to measure. Returns a numpy float32
    array (importing numpy lazily so the pure-DSP tests need not import this).
    """
    import numpy as np

    cmd = [FFMPEG, "-v", "error", "-i", path, "-map", "a:0", "-ac", "1"]
    if max_seconds:
        cmd += ["-t", f"{max_seconds:g}"]
    cmd += ["-f", "f32le", "-acodec", "pcm_f32le", "-"]

    proc = subprocess.run(
        cmd, capture_output=True, timeout=300, creationflags=_NO_WINDOW
    )
    if proc.returncode != 0:
        raise DecodeError(
            f"ffmpeg decode failed for {path}: {proc.stderr.decode('utf-8', 'ignore')[:200]}"
        )
    samples = np.frombuffer(proc.stdout, dtype=np.float32)
    if samples.size == 0:
        raise DecodeError(f"ffmpeg produced no samples for {path}")
    return samples, sample_rate
