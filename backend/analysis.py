"""Transcode detection — the core DSP.

This module is intentionally pure: it depends only on numpy + scipy and knows
nothing about ffmpeg, files or HTTP.  The single entry point you care about is
:func:`analyze_samples`, which takes a mono float32 signal at its *native* sample
rate and returns a :class:`Detection`.  Everything is unit-tested against
synthetic signals in ``backend/tests/test_analysis.py`` before it is ever wired
to a real decoder.

The detection signal is the high-frequency cutoff.  Lossy encoders low-pass the
audio; a file re-encoded from a low-bitrate source can never recreate the
frequencies the original already threw away.  So a 320 kbps-tagged MP3 whose
spectrum dies at 16 kHz is a re-encode of something worse.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.signal import welch

# --------------------------------------------------------------------------- #
# Tunables (all documented in the build brief).
# --------------------------------------------------------------------------- #
WINDOW_SEC = 5.0          # length of each analysis window
MAX_WINDOWS = 12          # cap analysis at the loudest ~60s (12 * 5s)
LOUD_FRACTION = 0.25      # keep the loudest 25% of windows
NPERSEG = 8192            # Welch segment length (Hann)

REF_BAND_HZ = (1000.0, 10000.0)   # band used for the reference level
FLOOR_DROP_DB = 50.0              # floor = reference - 50 dB
GAP_KHZ = 1.0                     # measured must be >1 kHz below expected to flag

# Shelf (brick-wall) test.
SHELF_SLOPE_DB = 30.0             # a "cliff" drops >30 dB ...
SHELF_SPAN_HZ = 500.0            # ... over <500 Hz
# The cliff must sit on real signal, not noise-floor wiggle. We require the level
# just below the cliff (the "plateau") to be in the upper 30 dB of the 50 dB
# reference window (i.e. well above the floor). Music's HF naturally sits
# ~10-18 dB below the 1-10 kHz mid-band, so a tighter margin would miss genuine
# brick-wall transcodes whose pre-cliff plateau is simply rolled-off treble.
SHELF_PLATEAU_MARGIN_DB = 30.0

# Containers whose *wrapper* claims lossless. A lossy spectrum inside one of
# these means a lossy original was re-wrapped as "lossless".
LOSSLESS_CONTAINERS = {"flac", "alac", "wav", "wave", "aiff", "aif", "ape", "wv", "tak"}

# Lossless codecs (a .m4a may carry lossy AAC or lossless ALAC, so the extension
# is not enough — the decoded codec name is the reliable signal).
LOSSLESS_CODECS = {
    "flac", "alac", "wavpack", "ape", "tak", "truehd", "mlp", "tta",
    "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_s16be",
    "pcm_s24be", "pcm_u8", "pcm_f64le",
}

# Declared bitrate (kbps) -> expected HF cutoff floor (kHz). Nearest tier wins.
EXPECTED_CUTOFF_KHZ = {128: 15.5, 160: 16.0, 192: 18.5, 256: 19.5, 320: 20.0}

VERDICT_OK = "OK"
VERDICT_SUSPECT = "SUSPECT"
VERDICT_TRANSCODE = "TRANSCODE"
VERDICT_LOSSY_SOURCE = "LOSSY SOURCE"


@dataclass
class Detection:
    """Result of analysing a signal. Frequencies are in kHz, levels in dB."""

    cutoff_khz: float
    expected_cutoff_khz: float
    ref_db: float
    floor_db: float
    plateau_db: float
    shelf_detected: bool
    shelf_slope_db: float
    verdict: str
    confidence: float
    true_quality: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Step 3 — segment selection.
# --------------------------------------------------------------------------- #
def select_loud_windows(x: np.ndarray, sr: int) -> list[np.ndarray]:
    """Split into ~5s windows, keep the loudest 25% (capped to ~60s of audio).

    Quiet intros and breakdowns have little HF content and would produce false
    "fake" verdicts, so we only analyse the loud windows.
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    win = int(round(WINDOW_SEC * sr))
    if win <= 0 or len(x) < win:
        return [x] if len(x) else [np.zeros(1)]

    n = len(x) // win
    windows = [x[i * win:(i + 1) * win] for i in range(n)]
    rms = np.array([float(np.sqrt(np.mean(w * w)) + 1e-12) for w in windows])

    order = np.argsort(rms)[::-1]  # loudest first
    keep_n = max(1, int(np.ceil(n * LOUD_FRACTION)))
    keep_n = min(keep_n, MAX_WINDOWS, n)
    return [windows[i] for i in order[:keep_n]]


# --------------------------------------------------------------------------- #
# Step 4 — averaged Welch PSD.
# --------------------------------------------------------------------------- #
def average_psd(windows: list[np.ndarray], sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Welch PSD (Hann, nperseg=8192) per window, averaged. Returns (freqs, psd_db)."""
    psds = []
    freqs = None
    for w in windows:
        nperseg = int(min(NPERSEG, len(w)))
        if nperseg < 16:
            continue
        f, pxx = welch(w, fs=sr, window="hann", nperseg=nperseg, detrend=False)
        freqs = f
        psds.append(pxx)
    if not psds:  # degenerate (empty / tiny signal)
        f, pxx = welch(np.zeros(NPERSEG), fs=sr, window="hann", nperseg=NPERSEG)
        return f, 10.0 * np.log10(pxx + 1e-20)
    psd = np.mean(np.vstack(psds), axis=0)
    psd_db = 10.0 * np.log10(psd + 1e-20)
    return freqs, psd_db


# --------------------------------------------------------------------------- #
# Step 5 — cutoff detection.
# --------------------------------------------------------------------------- #
def detect_cutoff(freqs: np.ndarray, psd_db: np.ndarray) -> tuple[float, float, float]:
    """Returns (ref_db, floor_db, cutoff_hz).

    reference = median PSD in 1-10 kHz; floor = reference - 50 dB; walk down from
    Nyquist and the cutoff is the first (highest) frequency back above the floor.
    """
    band = (freqs >= REF_BAND_HZ[0]) & (freqs <= REF_BAND_HZ[1])
    ref = float(np.median(psd_db[band])) if band.any() else float(np.median(psd_db))
    floor = ref - FLOOR_DROP_DB

    cutoff = float(freqs[-1])
    for i in range(len(freqs) - 1, -1, -1):
        if psd_db[i] > floor:
            cutoff = float(freqs[i])
            break
    return ref, floor, cutoff


# --------------------------------------------------------------------------- #
# Step 6 — shelf (transcode signature) test.
# --------------------------------------------------------------------------- #
def detect_shelf(
    freqs: np.ndarray, psd_db: np.ndarray, cutoff_hz: float, ref_db: float
) -> tuple[bool, float, float]:
    """Detect a flat-shelf-then-vertical-cliff.

    A genuine recording rolls off gradually. A transcode keeps a full, flat
    spectrum and then drops vertically at the encoder's low-pass. We look for a
    >30 dB drop across any 500 Hz window just below the cutoff, sitting on top of
    an otherwise-full spectrum.

    Returns (shelf_detected, max_drop_db_per_500hz, plateau_db).
    """
    # Plateau level just below the cutoff (the "otherwise-full" part).
    pmask = (freqs >= cutoff_hz - 2000.0) & (freqs <= cutoff_hz - 500.0)
    plateau = float(np.median(psd_db[pmask])) if pmask.any() else ref_db

    # Steepest drop over any 500 Hz window straddling the cutoff.
    bmask = (freqs >= cutoff_hz - 2500.0) & (freqs <= cutoff_hz + 500.0)
    fb, pb = freqs[bmask], psd_db[bmask]
    max_drop = 0.0
    for i in range(len(fb)):
        j = int(np.searchsorted(fb, fb[i] + SHELF_SPAN_HZ))
        if j < len(fb):
            drop = float(pb[i] - pb[j])
            if drop > max_drop:
                max_drop = drop

    sharp = (max_drop > SHELF_SLOPE_DB) and (plateau >= ref_db - SHELF_PLATEAU_MARGIN_DB)
    return sharp, max_drop, plateau


# --------------------------------------------------------------------------- #
# Helpers.
# --------------------------------------------------------------------------- #
def expected_cutoff_for(declared_kbps: int | None) -> float:
    """Expected HF cutoff floor for a declared bitrate (nearest tier)."""
    if not declared_kbps:
        return 20.0
    tier = min(EXPECTED_CUTOFF_KHZ, key=lambda b: abs(b - declared_kbps))
    return EXPECTED_CUTOFF_KHZ[tier]


def quality_label(cutoff_khz: float, nyq_khz: float) -> str:
    """A human estimate of the real quality implied by the measured cutoff."""
    # Reaching the file's own Nyquist means it is full-band for its sample rate.
    if cutoff_khz >= nyq_khz - 0.5:
        return "lossless / 320" if nyq_khz >= 21.0 else f"full-band @ {nyq_khz * 2:.0f}kHz SR"
    if cutoff_khz >= 20.0:
        return "lossless / 320"
    if cutoff_khz >= 19.5:
        return "~256-320 kbps"
    if cutoff_khz >= 18.5:
        return "~192 kbps"
    if cutoff_khz >= 16.0:
        return "~160 kbps"
    if cutoff_khz >= 15.0:
        return "~128 kbps"
    if cutoff_khz >= 11.0:
        return "<=128 kbps"
    return "very low / heavily band-limited"


def _clamp01(x: float) -> float:
    return float(max(0.0, min(0.99, x)))


# --------------------------------------------------------------------------- #
# Step 7 — verdict + confidence.
# --------------------------------------------------------------------------- #
def analyze_samples(
    samples: np.ndarray,
    sr: int,
    declared_kbps: int | None,
    container: str = "",
    codec: str = "",
) -> Detection:
    """Analyse a mono float32 signal at its native sample rate.

    ``container`` is the file extension / format name (e.g. ``flac``, ``mp3``);
    ``declared_kbps`` is the tagged bitrate (``None`` for lossless).
    """
    windows = select_loud_windows(samples, sr)
    freqs, psd_db = average_psd(windows, sr)
    ref_db, floor_db, cutoff_hz = detect_cutoff(freqs, psd_db)
    sharp, slope_db, plateau_db = detect_shelf(freqs, psd_db, cutoff_hz, ref_db)

    nyq_khz = sr / 2000.0
    cutoff_khz = cutoff_hz / 1000.0

    # Near-silent / degenerate input: every PSD bin sits on the log-epsilon floor,
    # so the cutoff would spuriously read as Nyquist and a dead file pass as OK.
    peak_rms = float(np.sqrt(np.mean(windows[0] ** 2))) if len(windows) else 0.0
    if peak_rms < 1e-5 or ref_db < -120.0:
        return Detection(
            cutoff_khz, nyq_khz, ref_db, floor_db, plateau_db, False, slope_db,
            VERDICT_SUSPECT, 0.1, "inconclusive (near-silent)",
            "Near-silent or no measurable signal in the loud windows — cannot assess "
            "high-frequency content; review manually.",
        )

    # The expected cutoff can never exceed the file's own Nyquist: a genuine
    # 32 kHz / 22.05 kHz file is full-band at sr/2, not a transcode.
    expected_khz = min(expected_cutoff_for(declared_kbps), nyq_khz - 0.2)
    gap = expected_khz - cutoff_khz
    is_lossless = (
        container.lower().lstrip(".") in LOSSLESS_CONTAINERS
        or codec.lower() in LOSSLESS_CODECS
    )

    true_quality = quality_label(cutoff_khz, nyq_khz)

    # --- Lossless wrapper around a lossy original. ------------------------- #
    if is_lossless:
        if cutoff_khz < min(19.0, nyq_khz - 0.5):
            verdict = VERDICT_LOSSY_SOURCE
            if sharp:
                conf = _clamp01(0.6 + 0.06 * min(19.0 - cutoff_khz, 5.0)
                                + min(max(slope_db - 30.0, 0.0), 40.0) / 200.0)
                reason = (
                    f"Lossless {container.upper()} container but the spectrum "
                    f"brick-walls at {cutoff_khz:.1f} kHz ({slope_db:.0f} dB cliff) "
                    f"— a lossy original re-wrapped as lossless."
                )
            else:
                conf = _clamp01(0.4 + 0.05 * min(19.0 - cutoff_khz, 5.0))
                reason = (
                    f"Lossless {container.upper()} container but HF only reaches "
                    f"{cutoff_khz:.1f} kHz — likely a lossy source, no hard shelf; review."
                )
            return Detection(cutoff_khz, expected_khz, ref_db, floor_db, plateau_db,
                             sharp, slope_db, verdict, conf, true_quality, reason)
        verdict = VERDICT_OK
        conf = _clamp01(0.75 + 0.04 * min(cutoff_khz - 19.0, 5.0))
        reason = (
            f"Lossless {container.upper()} with full-band spectrum to "
            f"{cutoff_khz:.1f} kHz — consistent with a genuine lossless source."
        )
        return Detection(cutoff_khz, expected_khz, ref_db, floor_db, plateau_db,
                         sharp, slope_db, verdict, conf, true_quality, reason)

    # --- Lossy container. -------------------------------------------------- #
    if gap > GAP_KHZ and sharp:
        verdict = VERDICT_TRANSCODE
        conf = _clamp01(0.6 + 0.07 * min(gap, 5.0)
                        + min(max(slope_db - 30.0, 0.0), 50.0) / 200.0)
        reason = (
            f"Cutoff {cutoff_khz:.1f} kHz is {gap:.1f} kHz below the "
            f"{expected_khz:.1f} kHz floor expected for the declared bitrate, with a "
            f"sharp {slope_db:.0f} dB brick-wall shelf — re-encoded from a lossy source."
        )
    elif gap > GAP_KHZ:
        verdict = VERDICT_SUSPECT
        conf = _clamp01(0.2 + 0.06 * min(gap, 5.0))
        reason = (
            f"Cutoff {cutoff_khz:.1f} kHz is below the expected {expected_khz:.1f} kHz "
            f"but the roll-off is gradual (no brick-wall) — could be genuinely "
            f"low-HF / acoustic material; flagged for manual review."
        )
    else:
        verdict = VERDICT_OK
        conf = _clamp01(0.7 + 0.06 * min(max(cutoff_khz - expected_khz, 0.0), 5.0))
        reason = (
            f"Cutoff {cutoff_khz:.1f} kHz is consistent with the declared bitrate "
            f"(expected >= {expected_khz:.1f} kHz)."
        )

    return Detection(cutoff_khz, expected_khz, ref_db, floor_db, plateau_db,
                     sharp, slope_db, verdict, conf, true_quality, reason)
