"""On-demand spectrogram rendering — the visual proof of a transcode.

A genuine track's energy fades gradually toward Nyquist; a transcode shows a
hard horizontal ceiling (the encoder's low-pass) with black above it. We draw a
dashed reference line at the cutoff expected for the declared bitrate so the gap
is obvious at a glance.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # headless: render to PNG bytes, never open a window

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.signal import spectrogram  # noqa: E402

from .ffmpeg_tools import decode_mono_f32, probe  # noqa: E402

_BG = "#0b0e14"
_FG = "#c9d1d9"


def render_spectrogram_png(
    path: str,
    expected_khz: float | None = None,
    measured_khz: float | None = None,
    max_seconds: float = 90.0,
) -> bytes:
    pr = probe(path)
    x, sr = decode_mono_f32(path, pr.sample_rate, max_seconds)

    nperseg = 2048
    f, t, sxx = spectrogram(
        x, fs=sr, window="hann", nperseg=nperseg,
        noverlap=nperseg // 2, detrend=False, mode="psd",
    )
    sdb = 10.0 * np.log10(sxx + 1e-12)
    vmax = float(np.percentile(sdb, 99.5))
    vmin = vmax - 90.0

    fig, ax = plt.subplots(figsize=(9.5, 5.2), dpi=110)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    pcm = ax.pcolormesh(t, f / 1000.0, sdb, shading="auto", cmap="magma",
                        vmin=vmin, vmax=vmax)
    ax.set_ylim(0, sr / 2 / 1000.0)
    ax.set_xlim(0, t[-1] if len(t) else 1)

    if expected_khz:
        ax.axhline(expected_khz, color="#22d3ee", ls="--", lw=1.3,
                   label=f"expected ≥ {expected_khz:.1f} kHz")
    if measured_khz:
        ax.axhline(measured_khz, color="#f43f5e", ls="-", lw=1.1,
                   label=f"measured cutoff {measured_khz:.1f} kHz")

    ax.set_xlabel("seconds", color=_FG)
    ax.set_ylabel("frequency (kHz)", color=_FG)
    ax.tick_params(colors=_FG, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#30363d")

    if expected_khz or measured_khz:
        leg = ax.legend(loc="upper right", fontsize=8, framealpha=0.85,
                        facecolor="#161b22", edgecolor="#30363d")
        for txt in leg.get_texts():
            txt.set_color(_FG)

    cbar = fig.colorbar(pcm, ax=ax, pad=0.01)
    cbar.set_label("dB", color=_FG)
    cbar.ax.yaxis.set_tick_params(color=_FG, labelsize=7)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=_FG)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=_BG)
    plt.close(fig)
    return buf.getvalue()
