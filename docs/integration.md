# 從兩套程式碼變成兩個 skill

這個 repo 原本有兩套各自完整、但沒有共用一行程式碼的東西：根目錄的研究用管線
（torchcrepe）跟 `skills/youtube-bass-tab`（basic-pitch）。現在合併完了，這份是紀錄。

## 動了什麼

**根目錄清空。** `fretboard.py` `pitch.py` `tempo.py` `rhythm.py` `render_tab.py`
`make_test.py` 全部搬到 `skills/youtube-bass-tab/scripts/lib/`，`bass2tab.py` 搬到
`scripts/`。之前 `tempo.py` / `rhythm.py` / `render_tab.py` 是孤兒（沒有進入點會呼叫
它們），現在三個都真的在管線上了。committed 的範例輸出搬到 `examples/`。

**調弦表合成一張。** `standard4` 跟 `EADG` 現在是同一個東西，兩種寫法都吃，
`EbAbDbGb` 跟 `28,33,38,43` 也吃。順手修掉降半音調弦被印成 `C# / F#` 的問題——
降弦的貝斯習慣寫 `Db / Gb`。

**`--png`。** `render_tab.py` 接進出譜器，接點就一行：
`placed = [(e[0], e[4]) for e in events]`，格線定義本來就對得上。

**tempo 換成自己的。** 不再呼叫 librosa，改用 `tempo.py` 的 spectral flux ＋ 自相關。
（basic-pitch 自己還是會把 librosa 裝進來，只是我們的程式不碰它了。）

**downbeat 真的去找了。** 之前 `--offset` 固定 0，等於假設音檔第 0 秒就是第一小節正拍，
有 intro 的歌整段小節線會歪。現在從音符的重量去找：velocity × 時值 × 音高低，
因為 bass 的根音落在第一拍、彈得比較長也比較重。

**警告會講人話。** 低於最低弦 → 建議調弦；重心太高 → 建議 `--transpose -12`；
超過最高格 → 建議 `--frets`。之前只有一句籠統的 octave folds。

**crepe 變成第二個引擎。** `--engine crepe` 走 `lib/crepe_to_midi.py`，吐出跟
basic-pitch 同形狀的 MIDI，下游完全共用。

**`install.sh` 支援兩個 runtime。** Hermes 會把絕對路徑蓋進 SKILL.md，
Claude Code 維持 `$SKILL_DIR` 讓 Claude 自己解析。

**第二個 skill：`bass-transcription-playbook`。** 查了別人怎麼做（Songscription、
klang.io、Songsterr、gp-workbench、Omnizart、MT3、Sayegh 的最佳路徑法）之後整理的，
內容是：六步檢查一份譜對不對、各家工具跟模型的比較、還有這條管線接下來該改什麼。

## 過程中找到的兩個真 bug

**1. onset envelope 比真實 onset 早 61 ms。** `tempo.py` 把一個 frame 的 flux 歸給
frame 的「起點」，但 frame 橫跨 NFFT 個 sample，裡面任何位置的 onset 都算它頭上。
結果每個 onset 都讀早了大約半個窗，beat phase 被整個拖走。改成歸給 frame 中心。

**2. 波形只能鎖到拍，鎖不到小節。** 這不是實作錯，是方法的天花板：一串平均的八分音符，
每個細分看起來都一樣，onset 能量分不出第 1 拍跟第 3 拍。所以 downbeat 改成從音符內容
去判斷，不從波形。

兩個都是先寫了測試（已知 BPM 100、已知 downbeat 0.85 秒、還故意加一個 pickup）才看出來的。

## 怎麼驗的

`scripts/selftest_offline.py`，18 項檢查，只需要 numpy / scipy / soundfile /
matplotlib / pretty_midi，不用 demucs、basic-pitch、torch：

```
fretboard         調弦別名一致、降半音拼字、解算不亂跑、五弦有印出來
tempo + downbeat  BPM 100.10（真值 100）、downbeat 0.862s（真值 0.85）
renderer          音數不掉、bar 1 退一個小節、pickup 落在第 14 格、PNG 有出、乾淨的譜不亂警告
register warnings drop D / 降半音 / 五弦 / 高八度 synth bass，各自剛好一條正確警告
crepe engine glue crepe 形狀的 events 進出譜器，結果跟 basic-pitch 那條一致
```

## 從安裝到產出，實際跑過一次

環境：一台沒有 GPU 的 Linux 容器，網路經過代理，`download.pytorch.org`、
`dl.fbaipublicfiles.com`、YouTube 都被擋，PyPI 通。

**安裝。** 原版 `install.sh` 在 torch 那步直接死，吐的是 uv 的原始錯誤、沒有指引。加了
`TORCH_INDEX_URL` 退路（設成空字串就改走 PyPI），`TORCH_INDEX_URL= bash install.sh`
之後整條裝完：torch 2.14（cu130，CPU 模式）、demucs、basic-pitch、torchcrepe。venv 7.5 GB
——PyPI 上 Linux 的 torch 是 CUDA 版，這是代價。最後乾淨重跑一次 `install.sh`：exit 0，
`[selftest] PASS`，12 秒（venv 沒重建，safe to re-run 成立）。

**產出。** 合成一首 32 秒的歌（bass ＋ 大鼓 ＋ hi-hat ＋ pad，I–vi–IV–V，96 BPM，
downbeat 故意放在 1.10 秒，onset 加 ±8 ms 抖動），96 個已知音。丟給裝好的 skill：

| | 找到 | 音高全對 | 八度錯 | 幽靈音 | BPM | bar 1 | 時間 |
|---|---|---|---|---|---|---|---|
| basic-pitch（預設） | 93/96 | 92 | 0 | 16 | 96.1 | 1.09s | 14 秒 |
| basic-pitch `--onset 0.7` | 82/96 | 80 | 1 | 7 | 96.1 | 0.82s（錯） | 14 秒 |
| crepe | 85/96 | 85 | 0 | 0 | 96.1 | 1.09s | 1 分 44 秒 |

六個輸出檔（tab.txt、tab.png、bass.mp3、bass_slow75.mp3、song_slow75.mp3、cleaned.mid）
都有，`RESULT` 一行 JSON 照合約。

**跑出來才看到的問題，都修了：**

- crepe 的 bar 1 一開始是 0.78s，差半拍。音符時間其實對到 10 ms 內，是 downbeat 選錯相位：
  這條 line 根音同時落在第 1 拍跟第 1 拍後半，兩個相位打平要靠重音分勝負，而 crepe 的
  periodicity 不含音量，velocity 全平（114–117）。改成從音檔算每個 onset 的 RMS 當
  velocity，bar 1 就回到 1.09s。
- 8 ms 的抖動讓第 1 小節整個空掉：downbeat 找對了，但第一個音比小節線早 8 ms，walk-back
  就退了一整個小節。加半格容差。
- demucs 權重下載被擋，錯誤訊息說「retry with --cpu」；yt-dlp 被擋，說「連結壞了」。
  現在會看 run.log 裡有沒有代理／DNS 的特徵，直接講是哪台主機出不去。兩個都實際重現過。
- `--onset 0.7`——playbook 原本對幽靈音的處方——在這份素材上是淨虧損：幽靈音 16→7，
  但真音 3→14 也跟著掉（低音弦上重複的根音被合併），downbeat 還跟著歪。處方改成
  「先比音數，掉得比幽靈音多就改用 crepe」，數字寫進 playbook。

**還是沒驗到的：** demucs 分軌本身（權重抓不到，只驗到失敗路徑）、YouTube 下載（同理）、
真鼓／rubato／swing（兩組測試都是死格線）。這幾項寫在 roadmap 的 Still unverified。
重現用 `scripts/bench/make_mix.py` ＋ `scripts/bench/score.py`。

過程中一個教訓：背景的 bash 正在執行 `setup.sh` 時，我改了那個檔案一行註解，bash 讀到
一半檔案位移，噴 syntax error、exit 2。self-test 其實已經 PASS，但那次安裝的 exit code
不能算，所以才有最後那次乾淨重跑。
