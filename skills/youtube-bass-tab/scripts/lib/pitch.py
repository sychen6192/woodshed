"""Stage 3: monophonic pitch tracking via torchcrepe -> discrete note events.

CREPE's receptive field is 1024 samples @16kHz (64 ms). At bass frequencies
(E1 = 41 Hz, period 24 ms) only ~2.6 periods fit in the window and the model
collapses onto its fmin bin. Fix: resample the audio to CREPE_SR/SHIFT and
declare it as CREPE_SR, which transposes everything up by SHIFT (2 octaves for
SHIFT=4) into CREPE's reliable range, then divide the reported f0 back down.
"""
import numpy as np
import torch
import torchcrepe
import soundfile as sf
from scipy.ndimage import median_filter

CREPE_SR = 16000
SHIFT = 4                      # transpose up 2 octaves for the model
HOP = 40                       # declared hop -> 40/16000*SHIFT = 10 ms real
FMIN, FMAX = 30.0, 450.0       # real-world bass register


def _load_shifted(path):
    """Mono audio resampled to CREPE_SR/SHIFT (to be declared as CREPE_SR)."""
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    target = CREPE_SR / SHIFT
    n = int(len(audio) * target / sr)
    return np.interp(
        np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio
    ).astype(np.float32)


def track(path, device="cuda", conf_threshold=0.55, model="full"):
    """Return (times_sec, midi_float_or_nan, confidence) per 10 ms frame."""
    audio = _load_shifted(path)
    tensor = torch.from_numpy(audio)[None]

    f0, conf = torchcrepe.predict(
        tensor, CREPE_SR, HOP,
        FMIN * SHIFT, FMAX * SHIFT, model,
        batch_size=2048, device=device, return_periodicity=True,
    )
    f0 = f0[0].cpu().numpy() / SHIFT          # back to real frequency
    conf = conf[0].cpu().numpy()

    # NOTE: torchcrepe.filter.median emits NaN on these tensors -- use scipy.
    f0 = median_filter(f0, size=5, mode="nearest")
    conf = median_filter(conf, size=5, mode="nearest")

    midi = np.full(len(f0), np.nan)
    ok = (conf >= conf_threshold) & (f0 > 0)
    midi[ok] = 69 + 12 * np.log2(f0[ok] / 440.0)
    times = np.arange(len(f0)) * (HOP / CREPE_SR) * SHIFT
    return times, midi, conf


def segment(times, midi, conf, min_dur=0.07, split_cents=80):
    """Group frames into note events; split when pitch jumps > split_cents."""
    events, cur = [], None

    for i, m in enumerate(midi):
        if np.isnan(m):
            if cur:
                cur["end"] = times[i]
                events.append(cur)
                cur = None
            continue
        if cur is None:
            cur = {"start": times[i], "frames": [m], "conf": [conf[i]]}
        elif abs(m - np.median(cur["frames"])) * 100 > split_cents:
            cur["end"] = times[i]
            events.append(cur)
            cur = {"start": times[i], "frames": [m], "conf": [conf[i]]}
        else:
            cur["frames"].append(m)
            cur["conf"].append(conf[i])
    if cur:
        cur["end"] = times[-1]
        events.append(cur)

    out = []
    for e in events:
        if e.get("end", e["start"]) - e["start"] < min_dur:
            continue
        p = np.array(e["frames"])
        core = p[2:] if len(p) > 4 else p      # trim attack transient
        out.append({
            "start": round(float(e["start"]), 3),
            "end": round(float(e["end"]), 3),
            "pitch": int(round(float(np.median(core)))),
            "amp": float(np.mean(e["conf"])),
        })
    return out


def transcribe(path, device="cuda", conf_threshold=0.55):
    t, m, c = track(path, device, conf_threshold)
    return segment(t, m, c)
