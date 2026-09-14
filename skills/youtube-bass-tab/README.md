# youtube-bass-tab — Hermes Agent skill

在 Telegram 丟一個 YouTube 連結給你的 Hermes，說「幫我扒這首的 bass」，它會回你：

- `<song>.tab.txt` — ASCII bass tab（含 BPM、調弦、小節線）
- `<song>.bass.mp3` — 分離出來的 bass 音軌（對照用）
- `<song>.backing_nobass.mp3` — 去掉 bass 的伴奏（練習跟著彈）
- `<song>.bass_slow75.mp3` / `<song>.song_slow75.mp3` — 0.75x 慢速版
- `<song>.cleaned.mid` — 清理過的 MIDI，可丟進 TuxGuitar / Guitar Pro 修

全部在你自己的機器上跑（yt-dlp → demucs → basic-pitch → 自寫的出譜器）。
Hermes 用哪個模型（Claude API、OpenRouter、本機模型）都無所謂，skill 只需要跑 shell。

## 需求

- Linux / macOS / WSL；有 GPU 更快（一首約 1 分鐘），沒有也行（CPU 約 2–5 分鐘）
- `ffmpeg`（`sudo apt install ffmpeg` 或 `brew install ffmpeg`）
- 約 4 GB 磁碟（PyTorch + TensorFlow）；Python 3.11 會由 uv 自動下載，不用自己裝

## 安裝（約 5–10 分鐘，大多在下載）

```bash
unzip youtube-bass-tab-hermes.zip
bash youtube-bass-tab/install.sh
```

裝完會自動跑 self-test（用合成音訊，不需要網路下載影片），看到
`[selftest] PASS` 就表示整條 pipeline 是通的。然後重啟 Hermes gateway
（或開新 session），用 `hermes skills list | grep youtube-bass-tab` 確認。

- 用具名 profile：`bash youtube-bass-tab/install.sh ~/.hermes/profiles/<名字>/skills/music/youtube-bass-tab`
- 只複製、稍後再裝環境：`SKIP_SETUP=1 bash youtube-bass-tab/install.sh`，之後跑 `scripts/setup.sh`
- 重跑 self-test：`~/.venvs/basstab/bin/python ~/.hermes/skills/music/youtube-bass-tab/scripts/selftest.py`

## 使用

Telegram 直接貼連結 + 一句話即可。譜不準的時候用人話叫它重跑，例如：

| 你說 | 它會加的參數 |
|---|---|
| 連續同音被合併了 | `--onset 0.4` |
| 有雜音 / 幽靈音 | `--onset 0.7` |
| 整段高了八度（synth bass 常見） | `--transpose -12` |
| BPM 抓錯 / 差一倍 | `--bpm N` |
| 這首是降半音 / drop D / 五弦 | `--tuning EbAbDbGb` / `DADG` / `BEADG` |
| 是 swing / 三連音 | `--grid 12` |

下載跟分離結果會快取在 `~/tabwork/<slug>/`，重跑只花幾秒。
也可以自己在終端機跑：`bash ~/.hermes/skills/music/youtube-bass-tab/scripts/basstab.sh "<URL>"`。

## 期望值

自動扒譜的天花板是辨識準確度，不是管線。一般 mix 大約八成正確，
bass 跟大鼓或 synth 糊在一起時會掉；把它當「草稿 + 對照 bass.mp3 用耳朵修」最實在。
僅供個人練習使用。

## 疑難排解

| 狀況 | 處理 |
|---|---|
| `venv not found` | `bash ~/.hermes/skills/music/youtube-bass-tab/scripts/setup.sh` |
| `ModuleNotFoundError: pkg_resources` | `VIRTUAL_ENV=~/.venvs/basstab uv pip install "setuptools<81"` |
| pip 出現 `ImpImporter` 錯誤 | venv 不是 Python 3.11，刪掉 `~/.venvs/basstab` 重跑 setup.sh |
| demucs 報 CUDA / OOM | 叫 Hermes 加 `--cpu`，或先關掉佔 VRAM 的程式 |
| yt-dlp 失敗 | `VIRTUAL_ENV=~/.venvs/basstab uv pip install -U yt-dlp`；私人/年齡限制影片抓不到 |
| Telegram 沒收到附件 | 檔案得在 Hermes gateway 那台主機上；如果 Hermes 跑在 docker，要把 `~/tabwork` 掛進來 |
