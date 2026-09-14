# youtube-bass-tab

丟一個 YouTube 連結，說「幫我扒這首的 bass」，它會回你：

- `<song>.tab.txt` — ASCII bass tab（含 BPM、調弦、小節線）
- `<song>.tab.png` — 排版過的譜，直接看
- `<song>.bass.mp3` — 分離出來的 bass 音軌（對照用）
- `<song>.backing_nobass.mp3` — 去掉 bass 的伴奏（練習跟著彈）
- `<song>.bass_slow75.mp3` / `<song>.song_slow75.mp3` — 0.75x 慢速版
- `<song>.cleaned.mid` — 清理過的 MIDI，可丟進 TuxGuitar / Guitar Pro 修

全部在你自己的機器上跑（yt-dlp → demucs → basic-pitch 或 torchcrepe → 自寫的出譜器）。
skill 只需要跑 shell，所以 Hermes 用哪個模型都無所謂。

## 需求

- Linux / macOS / WSL；有 GPU 更快（一首約 1 分鐘），沒有也行（CPU 約 2–5 分鐘）
- `ffmpeg`（`sudo apt install ffmpeg` 或 `brew install ffmpeg`）
- 約 4 GB 磁碟（PyTorch + TensorFlow；走 PyPI 退路的話約 7 GB）；Python 3.11 會由 uv 自動下載，不用自己裝

## 安裝（約 5–10 分鐘，大多在下載）

```bash
bash install.sh                       # Hermes：~/.hermes/skills/music/youtube-bass-tab
bash install.sh --target claude       # Claude Code，這個專案：./.claude/skills/...
bash install.sh --target claude-user  # Claude Code，所有專案：~/.claude/skills/...
bash install.sh /自己指定的/路徑
```

裝完會自動跑 self-test（用合成音訊，不需要網路下載影片），看到 `[selftest] PASS`
就表示整條 pipeline 是通的。Hermes 要重啟 gateway，Claude Code 開新 session。

- 只複製、稍後再裝環境：`SKIP_SETUP=1 bash install.sh`，之後跑 `scripts/setup.sh`
- 重跑完整 self-test：`~/.venvs/basstab/bin/python scripts/selftest.py`
- 重跑離線 self-test（不用 demucs / basic-pitch / torch，只要 numpy 那幾個）：
  `python scripts/selftest_offline.py`

Hermes 的 SKILL.md 裡寫的是絕對路徑，install.sh 會幫你蓋進去；Claude Code 那邊維持
`$SKILL_DIR`，由 Claude 自己解析。

## 使用

貼連結 + 一句話即可。譜不準的時候用人話叫它重跑：

| 你說 | 它會加的參數 |
|---|---|
| 連續同音被合併了 | `--onset 0.4` |
| 有雜音 / 同一個音連著出現兩次 | `--onset 0.7`，然後比對音數：它也會把低音弦上重複的音合併掉，掉的真音比幽靈音多就改用 `--engine crepe` |
| 整段高了八度（synth bass 常見） | `--transpose -12` |
| BPM 抓錯 / 差一倍 | `--bpm N` |
| 小節線對不上 | 先 `--bpm N`，downbeat 是從 BPM 推的 |
| 這首是降半音 / drop D / 五弦 | `--tuning EbAbDbGb` / `DADG` / `BEADG` |
| 是 swing / 三連音 | `--grid 12` |
| 譜上一堆重複觸發的音 | `--engine crepe` |

出譜器會自己印 `[warn]`，直接照著做就好：低於最低弦會建議調弦、重心太高會建議
`--transpose -12`。

下載跟分離結果會快取在 `~/tabwork/<slug>/`，重跑只花幾秒。
也可以自己在終端機跑：`bash scripts/basstab.sh "<URL>"`。

## 兩個引擎

| | basic-pitch（預設） | crepe |
|---|---|---|
| 複音 | 是 | 否（單音） |
| velocity | 有，幽靈音過濾靠它 | 沒有，用 periodicity 代替 |
| 低音弦 | 普通 | 較好（`pitch.py` 有升八度的處理） |
| 實測（96 個已知音） | 找到 97%，多 16 個幽靈音 | 找到 89%，零幽靈音、零錯音，但重複的音會合併 |
| 何時用 | 大部分情況、line 靠重複音撐 | 譜上一堆重複觸發的音時 |

兩條路都吐出同一種 MIDI，下游出譜器完全共用。crepe 的 velocity 是從音檔每個 onset 的
音量算的（periodicity 不含音量，拿來當 velocity 會全平，downbeat 就沒重音可看）。

## 期望值

自動扒譜的天花板是辨識準確度，不是管線。一般 mix 大約八成正確，bass 跟大鼓或 synth
糊在一起時會掉。把它當「草稿 + 對照 bass.mp3 用耳朵修」最實在。要判斷一份譜對不對，
用同一個 repo 裡的 `bass-transcription-playbook` skill，裡面有六步檢查。
僅供個人練習使用。

## 疑難排解

| 狀況 | 處理 |
|---|---|
| `venv not found` | `bash scripts/setup.sh` |
| setup.sh 在 `download.pytorch.org` 那步失敗 | 網路擋了那台主機：`TORCH_INDEX_URL= bash scripts/setup.sh` 改走 PyPI（Linux 上是 CUDA 版，約 7 GB） |
| `RESULT` 說 unreachable / network blocked | 不是參數問題：yt-dlp 或 demucs 權重下載出不去，看 run.log 裡是哪台主機 |
| `ModuleNotFoundError: pkg_resources` | `VIRTUAL_ENV=~/.venvs/basstab uv pip install "setuptools<81"` |
| pip 出現 `ImpImporter` 錯誤 | venv 不是 Python 3.11，刪掉 `~/.venvs/basstab` 重跑 setup.sh |
| demucs 報 CUDA / OOM | 加 `--cpu`，或先關掉佔 VRAM 的程式 |
| yt-dlp 失敗 | `VIRTUAL_ENV=~/.venvs/basstab uv pip install -U yt-dlp`；私人/年齡限制影片抓不到 |
| Telegram 沒收到附件 | 檔案得在 Hermes gateway 那台主機上；如果 Hermes 跑在 docker，要把 `~/tabwork` 掛進來 |

## 檔案

```
SKILL.md                      agent 讀的操作說明
install.sh                    裝到 Hermes 或 Claude Code
scripts/
  basstab.sh                  一鍵：下載 → 分離 → 轉譜 → 出譜 → 練習包
  midi_to_basstab.py          MIDI → tab（量化、小節、指板、警告）
  bass2tab.py                 torchcrepe 那條路的獨立入口
  selftest.py                 完整 pipeline 自我測試
  selftest_offline.py         不需要 demucs/basic-pitch/torch 的自我測試
  setup.sh                    建 venv
  lib/
    fretboard.py              調弦表、Viterbi 指板解算、ASCII 出譜
    pitch.py                  torchcrepe 音高追蹤（低音弦的升八度處理）
    tempo.py                  spectral flux onset envelope、自相關抓 BPM
    rhythm.py                 量化、從音符重量找 downbeat
    render_tab.py             matplotlib 排版 PNG
    crepe_to_midi.py          crepe events → basic-pitch 形狀的 MIDI
    make_test.py              產生已知答案的測試音檔
```
