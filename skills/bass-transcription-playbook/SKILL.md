---
name: bass-transcription-playbook
description: >-
  How bass transcription is actually done, and how to tell a good bass tab from a bad
  one. Use when checking or correcting a bass tab (auto-generated or hand-written),
  when a transcription looks wrong and you need to name which stage failed, when
  choosing between transcription tools or models (basic-pitch, Omnizart, MT3, CREPE,
  Songscription, klang.io, Songsterr), or when someone asks how to transcribe a bass
  line by ear. Also covers 扒譜 / 扒bass / 貝斯譜對不對 / 這譜怪怪的 / 要用哪個工具.
  Pairs with the youtube-bass-tab skill, which produces the tabs this one checks.
version: 1.0.0
author: sychen
---

# bass-transcription-playbook

Automatic bass transcription is around 80% right on a normal mix. This skill is about
the other 20%: which stage produced the error, how to check a tab before trusting it,
and what the alternatives are worth.

Read `references/methodology.md` for how humans do it and what each machine stage gets
wrong, `references/tools.md` for the tool and model landscape, `references/roadmap.md`
for what to change in this repo's pipeline next.

## Why bass is the hard instrument

Three things stack up, and they explain nearly every bad bass tab:

1. **Pitch detection is least reliable exactly where the bass lives.** E1 is 41 Hz, a
   24 ms period. Autocorrelation and CNN pitch models both tend to lock onto a
   subharmonic there, so the classic failure is an octave error — reported as an octave
   too low, or (on synth bass with a weak fundamental) an octave too high.
2. **The bass shares its register and its timing with the kick drum.** Separation
   leaks, and the onset you detect may be the kick, not the note.
3. **A tab is not a transcription.** Even with perfect pitches you still have to choose
   string and fret, and the same note has up to four positions. That is a separate
   optimization, and a wrong choice makes a correct tab unplayable.

## Checking a tab: run these six, in order

Each one is cheap and catches a different failure. Stop at the first that fails, fix
that, and re-check — later checks are meaningless on a tab that failed an earlier one.

| # | Check | How | If it fails |
|---|---|---|---|
| 1 | **Octave** | Play the tab against the isolated bass stem. Same notes, wrong register? | The whole line is off by 12. Re-run with `--transpose -12` (or `+12`). Do this first: it makes checks 2-6 look wrong for the wrong reason. |
| 2 | **Tuning** | Any note that would need a fret below 0 on the low string? | The song is down-tuned or on a 5-string. Re-run with `--tuning DADG` / `EbAbDbGb` / `BEADG`. |
| 3 | **Root on the downbeat** | Does the note on beat 1 of each bar match the chord being played? | Either the chord is being outlined from a passing tone (fine) or bar 1 is in the wrong place — go to check 4. |
| 4 | **Bar alignment** | Do the bar lines land on the kick/snare pattern? Count 1-2-3-4 along with the tab. | Tempo or downbeat is wrong. Force the tempo (`--bpm N`) before touching anything else; the downbeat is derived from it. |
| 5 | **Repeated notes** | Does the recording play the same note several times where the tab shows one long one? | The onset detector merged them. Lower the onset threshold (`--onset 0.4`). |
| 6 | **Ghost notes** | Is there junk between the real notes — very short notes, notes an octave or a fifth above a real one? | Harmonics or separation leakage got through. Raise the threshold (`--onset 0.7`), or raise the minimum note length. |

Checks 1, 2 and 6 are what the `youtube-bass-tab` renderer already tries to flag for you
in its `[warn]` lines. Treat those as a head start, not as the whole job — it can only
see the note list, not the recording.

## Reporting a check

Say which check failed, what the evidence was, and the one flag that addresses it. Do
not list every flag the tool has. If nothing failed, say the tab is consistent with the
stem and name the parts you could not verify (technique — slides, hammer-ons, ghost
notes, and dynamics — is not in the note list at all).

Never claim a tab is correct because the pipeline reported success. The pipeline
reports that it produced output, not that the output matches the recording.

## When someone wants to learn to do this by ear

The teaching consensus is consistent and worth passing on straight:

- Work one note at a time, slowly, and loop a bar until it is solid. Do not try to
  catch a whole phrase in one pass.
- Find the tonal centre first, then hear the line as scale degrees rather than as
  absolute pitches. This is what makes the skill transfer between songs.
- Get the rhythm before the pitches. A line with right pitches and wrong rhythm is
  unusable; the reverse is merely wrong in a fixable way.
- Match the level of detail to the purpose. Playing the part needs everything; working
  out the progression only needs the roots.
- An auto-generated tab is a scaffold to correct against the recording, not an answer.
  Using it as a starting point is fine; skipping the listening is what stops the ear
  from developing.
