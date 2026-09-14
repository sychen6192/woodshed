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

## 還沒驗證的

- **`--engine crepe` 沒有真的跑過。** 接縫測了，但 `pitch.py` 要 torch ＋ torchcrepe，
  這次的環境沒有。第一次真跑要拿同一首歌比兩個引擎。
- **`selftest.py`（完整版）改完之後沒重跑**，它要 demucs 跟 basic-pitch。它斷言的是
  summary 裡的 `notes=N`，那個欄位沒動，所以理論上會過——但這是推論不是測試。
- **tempo / downbeat 只在合成音訊上驗過**，格線是死的。真鼓、rubato、swing 都還沒試。

接下來要做什麼寫在
[`skills/bass-transcription-playbook/references/roadmap.md`](../skills/bass-transcription-playbook/references/roadmap.md)，
第一順位是 Guitar Pro 匯出——ASCII 改起來太痛苦，而 MIDI 會丟掉剛算完的指板選擇。
