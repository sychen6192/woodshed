# 兩條管線怎麼混在一起

repo 裡現在有兩套東西，各自都跑得起來，但沒有共用任何一行程式碼：

- **根目錄的 `*.py`** — 研究用的管線，torchcrepe 抓音高，自己寫的指板解算跟出譜。
- **`skills/youtube-bass-tab/`** — 打包好的 agent skill，basic-pitch 抓音高，附練習包。

這份筆記整理兩邊實際重疊到什麼程度，以及要合的話從哪裡下手。

## 逐段對照

| 階段 | 根目錄 | skill | 誰的比較好 |
| --- | --- | --- | --- |
| 抓音訊 | `bass2tab.fetch()`，yt-dlp / ffmpeg，寫進 `TemporaryDirectory`，跑完就刪 | `basstab.sh`，快取在 `~/tabwork/<slug>/song.wav` | **skill**：重跑不用重抓 |
| 分軌 | demucs `--two-stems bass`，只留 bass | demucs `--two-stems=bass`，bass 跟 no_bass 都留 | **skill**：no_bass 直接就是伴奏練習檔 |
| 轉譜 | `pitch.py`，torchcrepe ＋ 升八度騙過感受野的技巧 | `basic-pitch` CLI → MIDI | 各有長處，見下面 Step 4 |
| 抓 BPM | `tempo.py`（spectral flux ＋ 自相關）、`rhythm.py`（IOI 梳狀濾波） | `midi_to_basstab.detect_bpm()`，librosa `beat_track`，失敗退回 IOI 中位數 | **根目錄**：`tempo.py` 順便給 beat phase |
| 找小節起點 | `rhythm.find_downbeat()`、`tempo.track_beats()` | 沒有，`--offset` 固定 0 | **根目錄**：skill 的小節線可能整段偏移 |
| 指板解算 | `fretboard.solve()`，Viterbi，`MAX_FRET = 24` | `midi_to_basstab.map_frets()`，也是 Viterbi，`--frets` 預設 20 | 打平，權重配方不同而已 |
| ASCII 出譜 | `fretboard.render()`，一個音一欄 | `midi_to_basstab.render()`，照格線排，有小節線跟小節編號 | **skill**：時間軸是對的 |
| 圖檔出譜 | `render_tab.py`，matplotlib PNG | 沒有 | **根目錄**：唯一的圖形輸出 |
| 練習包 | 沒有 | mp3 ×3～4 ＋ 清過的 MIDI | **skill** |
| 自我測試 | `make_test.py` 只生音檔跟 ground truth，不驗證 | `selftest.py` 端到端跑完並檢查音數落在 12～20 | **skill** |

## 三件先知道比較好的事

**1. 根目錄有三個模組是孤兒。** `bass2tab.py` 只 import 了 `fretboard`。`tempo.py`、
`rhythm.py`、`render_tab.py` 都能用，但沒有任何進入點會呼叫它們 —— 現在要用只能自己
import。所以「合併」不是把兩套等量的東西對接，比較像是把根目錄閒置的零件插到 skill 上。

**2. 兩邊的 ASCII 出譜器不是同一種東西。** `fretboard.render()` 是一個音一欄，欄寬只看
數字長度，所以譜上看不出節奏 —— 除非傳 `labels`，而那也只是在上面加一排 `q e s`。
skill 那邊是先量化到格線、再照 slot 排，空的 slot 就是 `-`，還會畫小節線。要留的是後者。

**3. skill 沒有 downbeat detection。** `quantize()` 的 `offset` 預設 0，`basstab.sh` 也從來
沒傳過，等於假設音檔第 0 秒就是第一小節的正拍。前面有 intro 或 fade-in 的歌，小節線會整段
對不上。根目錄剛好有兩個現成的解（`rhythm.find_downbeat()` 吃 note events，
`tempo.track_beats()` 吃波形）。

## 調弦表其實是同一張表，只是名字不同

```
standard4  == EADG      [28, 33, 38, 43]
drop_d4    == DADG      [26, 33, 38, 43]
standard5  == BEADG     [23, 28, 33, 38, 43]
              EbAbDbGb  [27, 32, 37, 42]   ← 只有 skill 有（降半音）
```

## 建議的收斂路徑

方向：**skill 當產品端**（它有快取、自我測試、練習包、`RESULT` 合約），
**根目錄當演算法庫**。由小到大、由低風險到高風險：

### Step 1 — 把調弦表合成一張（最小，純加法）

`fretboard.TUNINGS` 補上 `EADG` / `DADG` / `BEADG` / `EbAbDbGb`，
`midi_to_basstab.TUNINGS` 補上 `standard4` / `drop_d4` / `standard5`。
兩邊的 CLI 從此吃同一組名字。`bass2tab.py` 的 `--tuning` 是 `choices=TUNINGS`，
所以加進去就自動出現在說明裡。

順手要補的：`render_tab.STR_NAMES` 沒有 27 / 32 / 37 / 42，降半音調弦會印成 `?`。

### Step 2 — 讓 skill 也能出 PNG（接點很乾淨）

`midi_to_basstab` 跑完 `map_frets()` 之後，每個 event 是
`[slot, pitch, dur, velocity, (string, fret)]`；而 `render_tab.render_png()` 要的
`placed` 就是 `[(slot, (string, fret))]`。等於：

```python
placed = [(e[0], e[4]) for e in events]
render_png(placed, out_png, tuning=tuning_name, div=grid // 4, bpb=meter)
```

格線定義本來就對得上（`slots_bar = grid * meter // 4` 就是 `div * bpb`），
不用改任何一邊的量化邏輯。前提是 Step 1 —— `render_png` 是用調弦名字去查
`fretboard.TUNINGS` 的。加一個 `--png` 參數，`basstab.sh` 再把檔名塞進 `RESULT` 的
`files` 就好。

### Step 3 — 用 `tempo.py` 換掉 librosa

`basstab.sh` 現在傳 `--audio "$W/song.wav"` 給 `detect_bpm()` 去跑 librosa。
`tempo.analyse_audio()` 吃同一個 wav，只靠 numpy ＋ soundfile，回傳 `bpm` 之外還有
`phase`。換過去有兩個好處：skill 的依賴少一個 librosa，而且 `phase` 正好補上第 3 點
缺的 downbeat（接到 `quantize()` 的 `offset`）。

這步要實測，兩邊的 BPM 估法本來就會給出不同答案，得拿幾首已知 BPM 的歌對過再說。

### Step 4 — torchcrepe 當第二個轉譜引擎

加 `--engine basic-pitch|crepe`。兩者解的問題一樣但性質不同：basic-pitch 是複音、
會給 velocity；torchcrepe 是單音、沒有 velocity，但 `pitch.py` 那個升八度的技巧對低音
弦的處理是這個 repo 真正的原創部分。風險最高的一步，見下面。

## 不建議做的事

- **不要把 skill 拆散塞進根目錄。** `install.sh` 是靠「複製自己所在的整個資料夾」運作的
  （`cp -R "$SRC" "$DEST"`），拆掉就不能裝了。要嘛整包留著，要嘛改寫安裝方式。
- **不要直接拿 torchcrepe 換掉 basic-pitch。** `midi_to_basstab` 的 `load_notes()`
  velocity floor 跟 `suppress_harmonics()` 都是吃 velocity 的，torchcrepe 只有
  periodicity（`pitch.py` 存成 `amp`），語意不一樣。真要換得先決定這兩個過濾器怎麼辦。
- **不要把 skill 放到 `.claude/skills/`。** `SKILL.md` 裡寫的是
  `~/.hermes/skills/music/youtube-bass-tab/...` 的絕對路徑，當成 Claude Code skill 讀會
  指到不存在的地方。要支援的話得另外寫一份。

## 還沒驗證的部分

這次的環境沒有 numpy / torch / pretty_midi / librosa / ffmpeg，兩條管線都跑不起來，
所以上面的對照是讀程式碼得到的，不是實測。實際跑過的只有 `python fretboard.py`
的 self-test（純標準庫）跟兩邊 source 的 `py_compile`。Step 1～4 都還沒動手。
