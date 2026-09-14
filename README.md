# woodshed

Agent skills for getting a bass line out of a recording. Two of them, meant to be used
together: one produces the tab, the other tells you whether to believe it.

| Skill | What it does |
| --- | --- |
| [`skills/youtube-bass-tab`](skills/youtube-bass-tab) | YouTube link or audio file → ASCII tab, typeset PNG, isolated bass, bass-less backing track, slowed versions, cleaned MIDI. Runs locally: yt-dlp → demucs → basic-pitch or torchcrepe → tab renderer. |
| [`skills/bass-transcription-playbook`](skills/bass-transcription-playbook) | How bass transcription is actually done, a six-step check for spotting which stage failed, and what the alternative tools and models are worth. No code, no dependencies. |

Both install into Hermes or into Claude Code.

```bash
bash skills/youtube-bass-tab/install.sh                       # ~/.hermes/skills/music/...
bash skills/youtube-bass-tab/install.sh --target claude        # ./.claude/skills/...
bash skills/youtube-bass-tab/install.sh --target claude-user   # ~/.claude/skills/...
```

`bass-transcription-playbook` is plain Markdown — copy the directory to the same place,
or point your agent at it where it sits.

## Layout

```
skills/
  youtube-bass-tab/            the pipeline; see its README for flags and troubleshooting
    SKILL.md  install.sh  scripts/{basstab.sh,midi_to_basstab.py,...}  scripts/lib/
  bass-transcription-playbook/ the craft; methodology, tool landscape, roadmap
    SKILL.md  references/{methodology,tools,roadmap}.md
examples/                      sample output kept for reference
docs/integration.md            how this repo got to two skills, in Chinese
```

Everything that used to sit loose at the repo root — the fret solver, the tempo and
rhythm code, the PNG renderer, the torchcrepe pitch tracker — now lives in
`skills/youtube-bass-tab/scripts/lib/` and is reachable from the pipeline. Nothing is
orphaned any more.

## Checking it works

The pipeline ships two self-tests. The offline one needs only numpy, scipy, soundfile,
matplotlib and pretty_midi, and covers everything downstream of the transcription
engine — tempo, downbeat, quantization, the fret solver, both renderers, the register
warnings — against synthesized audio with a known answer:

```bash
python skills/youtube-bass-tab/scripts/selftest_offline.py
```

The full one additionally exercises demucs and basic-pitch, so it needs the venv that
`scripts/setup.sh` builds:

```bash
~/.venvs/basstab/bin/python skills/youtube-bass-tab/scripts/selftest.py
```

## Expectations

Automatic transcription tops out around 80% correct on a normal mix and drops where the
bass shares space with the kick or a synth. Treat the output as a draft to correct by
ear against the isolated stem — that is what the playbook skill is for. Personal
practice use.
