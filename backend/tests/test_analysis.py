"""Gating tests for the transcode detector.

The three cases from the build brief decide whether the core logic is sound:

  1. full-band white noise            -> OK
  2. the same noise low-passed @16kHz -> TRANSCODE  (brick-wall shelf present)
  3. naturally band-limited material  -> SUSPECT     (gradual roll-off, no shelf)

We synthesise signals directly in the frequency domain so the spectral shape is
exact and the tests are deterministic (seeded RNG, no ffmpeg involved).
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.analysis import (
    VERDICT_LOSSY_SOURCE,
    VERDICT_OK,
    VERDICT_SUSPECT,
    VERDICT_TRANSCODE,
    analyze_samples,
)

SR = 44100
DURATION = 20.0  # seconds -> several 5s windows


def _noise(seconds=DURATION, seed=0, sr=SR):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(int(seconds * sr)).astype(np.float64)


def _shape(x, gain_db_of_f, sr=SR):
    """Apply an arbitrary dB(frequency) gain curve in the frequency domain."""
    spectrum = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    gain = 10.0 ** (gain_db_of_f(f) / 20.0)
    return np.fft.irfft(spectrum * gain, n=len(x))


def brickwall(x, fc, sr=SR):
    """Perfect low-pass: full spectrum below fc, nothing above -> vertical cliff."""
    return _shape(x, lambda f: np.where(f <= fc, 0.0, -200.0), sr)


def gradual(x, f_start=12000.0, f_end=16000.0, depth_db=60.0, sr=SR):
    """Full below f_start, then a gentle linear-in-dB ramp down to the floor."""
    def gain(f):
        return -depth_db * np.clip((f - f_start) / (f_end - f_start), 0.0, 1.0)
    return _shape(x, gain, sr)


# --------------------------------------------------------------------------- #
# The three gating cases.
# --------------------------------------------------------------------------- #
def test_full_band_noise_is_ok():
    det = analyze_samples(_noise(), SR, declared_kbps=320, container="mp3")
    assert det.verdict == VERDICT_OK
    assert det.cutoff_khz > 19.5
    assert not det.shelf_detected


def test_lowpassed_then_tagged_high_is_transcode():
    sig = brickwall(_noise(), fc=16000.0)
    det = analyze_samples(sig, SR, declared_kbps=320, container="mp3")
    assert det.verdict == VERDICT_TRANSCODE
    assert det.shelf_detected
    assert 15.0 < det.cutoff_khz < 17.0
    assert det.confidence > 0.8


def test_natural_bandlimited_is_suspect_not_transcode():
    sig = gradual(_noise())
    det = analyze_samples(sig, SR, declared_kbps=320, container="mp3")
    assert det.verdict == VERDICT_SUSPECT
    assert not det.shelf_detected
    assert det.cutoff_khz < 18.5
    assert det.confidence < 0.5


# --------------------------------------------------------------------------- #
# Bitrate-tier logic must not punish a genuine low-bitrate file.
# --------------------------------------------------------------------------- #
def test_genuine_128_with_shelf_is_ok():
    # A real 128 kbps MP3 brick-walls ~16 kHz; tagged 128, that is expected.
    sig = brickwall(_noise(), fc=16000.0)
    det = analyze_samples(sig, SR, declared_kbps=128, container="mp3")
    assert det.verdict == VERDICT_OK


def test_deep_lowpass_tagged_320_is_transcode():
    # 11 kHz cutoff under a 320 tag is an unambiguous re-encode.
    sig = brickwall(_noise(), fc=11000.0)
    det = analyze_samples(sig, SR, declared_kbps=320, container="mp3")
    assert det.verdict == VERDICT_TRANSCODE
    assert det.true_quality.startswith("<=128") or "very low" in det.true_quality


# --------------------------------------------------------------------------- #
# Lossless container wrapping a lossy original.
# --------------------------------------------------------------------------- #
def test_lossless_wrapper_around_lossy_is_flagged():
    sig = brickwall(_noise(), fc=16000.0)
    det = analyze_samples(sig, SR, declared_kbps=None, container="flac")
    assert det.verdict == VERDICT_LOSSY_SOURCE


def test_genuine_lossless_is_ok():
    det = analyze_samples(_noise(), SR, declared_kbps=None, container="flac")
    assert det.verdict == VERDICT_OK
    assert det.cutoff_khz > 19.0


# --------------------------------------------------------------------------- #
# Robustness: quiet windows must not drag the verdict around.
# --------------------------------------------------------------------------- #
def test_quiet_intro_does_not_cause_false_transcode():
    loud = _noise(seconds=10.0, seed=1)
    quiet = _noise(seconds=10.0, seed=2) * 1e-3  # near-silent breakdown
    sig = np.concatenate([quiet, loud])
    det = analyze_samples(sig, SR, declared_kbps=320, container="mp3")
    assert det.verdict == VERDICT_OK


# --------------------------------------------------------------------------- #
# Sub-44.1 kHz audio: the expected cutoff must be clamped to the file's Nyquist,
# or genuine full-band low-sample-rate files get falsely flagged.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sr", [32000, 22050])
def test_low_samplerate_fullband_lossy_is_ok(sr):
    sig = _noise(sr=sr)
    det = analyze_samples(sig, sr, declared_kbps=320, container="mp3")
    assert det.verdict == VERDICT_OK, (sr, det.verdict, det.cutoff_khz)


@pytest.mark.parametrize("sr", [32000, 22050])
def test_low_samplerate_fullband_lossless_is_ok(sr):
    sig = _noise(sr=sr)
    det = analyze_samples(sig, sr, declared_kbps=None, container="flac")
    assert det.verdict == VERDICT_OK, (sr, det.verdict, det.cutoff_khz)


def test_low_samplerate_with_real_lowpass_still_flagged():
    # A 32 kHz file low-passed at 10 kHz (well below its 16 kHz Nyquist) under a
    # 320 tag is still an unambiguous transcode.
    sr = 32000
    sig = brickwall(_noise(sr=sr), fc=10000.0, sr=sr)
    det = analyze_samples(sig, sr, declared_kbps=320, container="mp3")
    assert det.verdict == VERDICT_TRANSCODE, (det.verdict, det.cutoff_khz)


def test_silent_input_is_not_ok():
    sig = np.zeros(int(20 * SR), dtype=np.float64)
    det = analyze_samples(sig, SR, declared_kbps=None, container="flac")
    assert det.verdict != VERDICT_OK
    assert det.confidence < 0.3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
