"""Score a basstab.sh run against the synthetic ground truth.

    python scripts/bench/score.py <truth.json> ~/tabwork/<slug>/out <slug>

Reads <slug>.cleaned.mid (the quantized notes the tab was rendered from) and the
summary line from run.log, then reports pitch / octave / timing accuracy.
"""
import json, os, re, sys
import pretty_midi

truth_path, out_dir, slug = sys.argv[1:4]
truth = json.load(open(truth_path))
T = truth["notes"]

mid = os.path.join(out_dir, f"{slug}.cleaned.mid")
pm = pretty_midi.PrettyMIDI(mid)
got = sorted(((n.start, n.pitch) for i in pm.instruments for n in i.notes))

# The renderer walks bar 1 back to sit before the first note, so absolute times in
# cleaned.mid are grid-relative. Align by the first note of each list.
t_shift = T[0]["start"] - got[0][0] if got else 0.0

TOL = 0.09    # 90 ms: a 16th at 96 bpm is 156 ms, so this is "same slot"
matched = exact = pc_only = 0
unmatched_truth, extra = [], list(got)
for t in T:
    cand = [(abs(g[0] + t_shift - t["start"]), g) for g in extra if abs(g[0] + t_shift - t["start"]) <= TOL]
    if not cand:
        unmatched_truth.append(t); continue
    _, g = min(cand)
    extra.remove(g)
    matched += 1
    if g[1] == t["pitch"]: exact += 1
    elif (g[1] - t["pitch"]) % 12 == 0: pc_only += 1

n = len(T)
print(f"truth notes      {n}")
print(f"transcribed      {len(got)}")
print(f"matched in time  {matched}  ({100*matched/n:.0f}%)")
print(f"  exact pitch    {exact}  ({100*exact/n:.0f}%)")
print(f"  octave off     {pc_only}")
print(f"  wrong pitch    {matched-exact-pc_only}")
print(f"missed           {len(unmatched_truth)}")
print(f"extra (ghosts)   {len(extra)}")
if unmatched_truth[:5]:
    print("  first missed:", [(t['start'], t['pitch'], t['chord']) for t in unmatched_truth[:5]])
if extra[:5]:
    print("  first extra: ", [(round(g[0]+t_shift,2), g[1]) for g in extra[:5]])

log = os.path.join(os.path.dirname(out_dir.rstrip('/')), "run.log")
if os.path.exists(log):
    lines = [l for l in open(log) if l.startswith("[summary]") or l.startswith("[warn]")]
    for l in lines[-3:]: print("log:", l.rstrip()[:150])
    m = re.search(r"bpm=([\d.]+)\((\w[\w-]*)\)", "".join(lines))
    if m: print(f"bpm {m.group(1)} ({m.group(2)})   truth {truth['bpm']}")
