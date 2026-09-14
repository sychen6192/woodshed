"""Audio-domain tempo & beat tracking (spectral flux + autocorrelation).

Deriving tempo from pitch-segmentation onsets fails because the segmenter only
splits on pitch CHANGE -- repeated notes merge and the onset series is
incomplete. Working from the waveform recovers every attack.
"""
import numpy as np
import soundfile as sf

SR = 22050
HOP = 256                      # ~11.6 ms
NFFT = 1024
FRAME_LAG = NFFT / 2 / SR      # a frame's flux belongs to its centre, not its start


def _load(path):
    a, sr = sf.read(str(path), dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if sr != SR:
        n = int(len(a) * SR / sr)
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    return a.astype(np.float32)


def onset_envelope(path):
    """Half-wave-rectified spectral flux, normalised."""
    a = _load(path)
    win = np.hanning(NFFT).astype(np.float32)
    n_frames = 1 + (len(a) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = a[idx] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    mag = np.log1p(mag * 10.0)                 # log compression
    flux = np.diff(mag, axis=0)
    flux = np.maximum(flux, 0).sum(axis=1)     # half-wave rectify
    flux = np.concatenate([[0.0], flux])
    # subtract local mean to flatten dynamics
    k = 16
    kern = np.ones(k) / k
    flux = flux - np.convolve(flux, kern, mode="same")
    flux = np.maximum(flux, 0)
    if flux.max() > 0:
        flux /= flux.max()
    # A frame starting at i*HOP spans NFFT samples, so its flux reports an onset
    # that happened anywhere in that window. Attributing it to the frame start
    # makes every onset read ~NFFT/2 early, which drags the beat phase with it.
    times = np.arange(len(flux)) * HOP / SR + FRAME_LAG
    return times, flux


def tempo_from_envelope(flux, lo=60.0, hi=180.0):
    """Autocorrelation of the onset envelope, scored over a tempo range."""
    f = flux - flux.mean()
    ac = np.correlate(f, f, mode="full")[len(f) - 1:]
    ac[0] = 0
    if ac.max() > 0:
        ac /= ac.max()

    fps = SR / HOP
    cands = []
    for bpm in np.arange(lo, hi, 0.1):
        lag = 60.0 / bpm * fps
        # sum autocorrelation at the beat lag and its multiples
        score = 0.0
        for mult, w in [(1, 1.0), (2, 0.8), (4, 0.5), (0.5, 0.6)]:
            L = lag * mult
            i = int(round(L))
            if 0 < i < len(ac):
                score += w * ac[i]
        cands.append((score, float(bpm)))
    cands.sort(reverse=True)
    best_score, best_bpm = cands[0]
    return best_bpm, best_score, ac


def track_beats(times, flux, bpm, tol=0.12):
    """Phase-lock a fixed-tempo beat grid to the onset envelope."""
    period = 60.0 / bpm
    fps = SR / HOP
    plen = period * fps
    best_phase, best_score = 0.0, -1.0
    for ph in np.linspace(0, period, 96, endpoint=False):
        pos = (np.arange(ph, times[-1], period) - FRAME_LAG) * fps
        pos = pos[(pos >= 0) & (pos < len(flux))].astype(int)
        if len(pos) == 0:
            continue
        # sample a small window around each predicted beat
        w = max(1, int(plen * tol))
        score = float(np.mean([flux[max(0, p - w):p + w + 1].max()
                               for p in pos]))
        if score > best_score:
            best_score, best_phase = score, ph
    beats = np.arange(best_phase, times[-1], period)
    return beats, best_phase, best_score


def analyse_audio(path, lo=60.0, hi=180.0, bpm=None):
    """Estimate tempo and lock a beat grid to the audio.

    Pass `bpm` to skip estimation and phase-lock at a tempo you already know;
    the phase is only meaningful for the tempo it was fitted at.
    """
    t, flux = onset_envelope(path)
    if bpm is None:
        bpm, score, _ = tempo_from_envelope(flux, lo, hi)
    else:
        bpm, score = float(bpm), float("nan")
    beats, phase, lock = track_beats(t, flux, bpm)
    return {"bpm": bpm, "ac_score": score, "phase": phase,
            "beat_lock": lock, "beats": beats, "times": t, "flux": flux}
