# How bass transcription is done, stage by stage

A transcription pipeline is four decisions, not one. Errors at each stage look
different, and fixing the wrong stage is the usual reason a tab stays wrong.

```
audio ──► separation ──► pitch/note detection ──► rhythm & bar grid ──► string/fret
          (demucs)       (basic-pitch, CREPE)     (tempo, downbeat)      (DP solver)
```

## 1. Separation

Isolating the bass stem first is the common approach — demucs `--two-stems=bass` is
what most open-source pipelines use, and it is what klang.io's bass workflow and
gp-workbench both do. It helps because pitch detection on a full mix has to contend
with everything else in the same low register.

Two things to know:

- **The kick drum is the problem case.** It shares both the register and, usually, the
  onset with the bass note. Leakage into the bass stem shows up as extra short notes on
  beats 1 and 3, and as onsets that are a few milliseconds early.
- **Separation is not required.** Songscription trains models to transcribe bass
  directly from a full mix and skips stem splitting entirely. That trades one error
  source (separation artefacts) for another (everything else in the mix). For a local
  pipeline, separating is still the pragmatic choice — the bass stem is also what the
  user needs for checking by ear.

## 2. Pitch and note detection

Two families, and the choice matters more than any parameter:

**Monophonic f0 trackers** (CREPE/torchcrepe, pYIN, SWIPE'). One pitch at a time,
frame by frame, then segmented into notes. Good fit for bass, which is nearly always
monophonic. Their failure is the **subharmonic (octave) error**: at 41 Hz a 1024-sample
window at 16 kHz holds only ~2.6 periods, which is not enough for the model to be
confident, and it collapses onto a lower bin. Known mitigations:

- Resample so the bass lands in the model's reliable range and divide the result back
  down. (This is what `pitch.py` in the youtube-bass-tab skill does — resample to
  `CREPE_SR/4`, declare it as `CREPE_SR`, which transposes up two octaves.)
- Score only the first and prime harmonics rather than all of them — the trick behind
  SWIPE', specifically to suppress subharmonic errors.
- Median-filter the f0 track before segmenting, so single-frame drops do not split a
  note.

**Polyphonic note detectors** (basic-pitch, Omnizart, MT3). Output note events with
velocities, which downstream filters need. They will happily report a second voice that
is really a harmonic — hence a harmonic-interval filter (drop a near-simultaneous note
+12, +19, +24, +28 or +31 semitones above a louder one) is worth having.

A practical detail: basic-pitch's onset threshold is the single most useful knob.
Low (~0.4) splits repeated notes that were merged; high (~0.7) suppresses ghost notes.
gp-workbench runs basic-pitch at **two thresholds and merges the results**, which gets
both without choosing.

## 3. Rhythm and the bar grid

Two separate problems that get conflated:

- **Tempo.** Autocorrelation of an onset envelope is standard and reliable. The usual
  failure is octave-of-tempo (half or double), which is why estimates are folded into a
  60-190 BPM range.
- **Downbeat.** A beat grid fitted to a waveform locks to *the beat*, not to *the bar* —
  it cannot tell beat 1 from beat 3. On a steady stream of eighth notes it may not even
  find the beat, since every subdivision looks like every other. Onset mass alone does
  not resolve it.

  What does resolve it is note content: a bass line lands the root on beat 1, holds it
  longer, and hits it harder. Weighting candidate phases by velocity, duration and
  lowness picks the bar out where raw onset energy cannot. If the bar phase is wrong,
  every bar line in the tab is wrong, so this is worth getting right before anything
  cosmetic.

One more trap: attributing a spectral-flux frame's energy to the frame's *start* makes
every onset read early by half the FFT window (~23 ms at 1024/22050), and that bias
drags the beat phase with it. Use the frame centre.

## 4. String and fret

Given the pitches, choosing positions is a shortest-path problem, and it has a
well-established answer: **Sayegh's Optimum Path Paradigm** (1989) — assign a cost to
each transition between hand positions and run dynamic programming (Viterbi) over the
weighted graph. It is still the classical benchmark for tablature inference.

Cost terms that matter in practice: fret distance moved, strings crossed, a bonus for
open strings, a penalty for the upper register. Variants worth knowing: Hori et al.
use a **minimax** Viterbi to minimise the *hardest* single move rather than the total;
genetic algorithms have been used for the same objective; recent work treats it as
masked language modelling over tab tokens, or as a diffusion process with playability
constraints.

For bass specifically the search is small — four strings, and most lines sit in the
first five frets — so a plain Viterbi with hand-tuned weights is enough. The thing to
get right is not the algorithm but the **range folding**: a note outside what the tuning
can reach has to go somewhere, and shifting it by whole octaves keeps the pitch class,
which is what a tab needs. Count those folds and report them — a high fold rate is the
strongest available signal that stage 2 made octave errors.

## How people do it by ear

Worth knowing because it says which errors matter. The consistent advice across
teaching sources:

- Slowly, one note at a time, looping a short passage. Not a phrase per pass.
- Find the tonal centre, then hear scale degrees rather than absolute pitches.
- Diversity of material develops the ear faster than volume of it.
- Detail should match purpose: the full part, or just the roots for a progression.

Two implications for automatic output. First, **scale degrees are the human's error
check** — a note that is not in the key is heard immediately, which is why octave errors
(which preserve pitch class) slip past listeners but rhythm errors do not. Second,
**rhythm is what a player notices first**, so a tab with a misplaced bar line reads as
broken even when every pitch is right.

## Sources

- [Best Tools for Transcribing Bass Lines in 2026 — Songscription](https://www.songscription.ai/blog/best-bass-line-transcription-tools)
- [How to Quickly Get Bass Tabs for Any Song — klang.io](https://klang.io/blog/bass-audio-separation/)
- [gp-workbench](https://github.com/hchia93/gp-workbench) — demucs + basic-pitch dual-threshold + grid fit + fret mapping + `.gp`
- [An Algorithm for Optimal Guitar Fingering (DP / Sayegh's Optimum Path Paradigm)](https://www.diva-portal.org/smash/get/diva2:668903/FULLTEXT01.pdf)
- [MIDI-to-Tab: Guitar Tablature Inference via Masked Language Modeling](https://arxiv.org/html/2408.05024)
- [YIN, a fundamental frequency estimator for speech and music](http://audition.ens.fr/adc/pdf/2002_JASA_YIN.pdf) — subharmonic ("octave") errors
- [CREPE: A Convolutional Representation for Pitch Estimation](https://www.researchgate.net/publication/323276357_CREPE_A_Convolutional_Representation_for_Pitch_Estimation)
- [Transcribing Bass Lines — Foundations of Aural Skills](https://uen.pressbooks.pub/auralskills/chapter/transcribing-bass-lines/)
- [Beginner Transcription Tips — TalkingBass](https://www.talkingbass.net/beginner-transcription-tips/)
