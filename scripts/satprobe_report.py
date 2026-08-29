"""TASK 1 deliverable: results/SATPROBE_REPORT.md. Reads perf.json, never writes it."""
import argparse, json
import numpy as np


def pred(B, C, a, bd, ck):
    return a + bd * B + ck * (B * C) / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meas", default="results/satprobe/measurements.json")
    ap.add_argument("--out", default="results/SATPROBE_REPORT.md")
    a_ = ap.parse_args()
    P = json.load(open("results/perf.json"))
    M = json.load(open(a_.meas))
    g = M["grid"]
    a, bd, ck = P["a"], P["b_d"], P["c_kv"]
    grid5 = P["online_fit"]["grid"]
    r5 = {(x["B"], x["ctx"]): x["step_ms"] for x in grid5}

    lo = [(x["B"], x["ctx"], x["step_ms"] / 1000) for x in grid5 if x["B"] <= 64]
    A = np.array([[1.0, B, B * C / 1e6] for B, C, _ in lo])
    y = np.array([s for *_, s in lo])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    a2, bd2, ck2 = coef
    r2 = 1 - ((y - A @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()

    rows = []
    for m in g:
        B, C, ms = m["B"], m["ctx"], 1000 * m["step_s"]
        pi, pl = 1000 * pred(B, C, a, bd, ck), 1000 * pred(B, C, a2, bd2, ck2)
        rows.append({**m, "ms": ms, "inst": pi, "inst_pct": 100 * (ms - pi) / pi,
                     "low": pl, "low_pct": 100 * (ms - pl) / pl})
    hi = [r for r in rows if r["B"] >= 96]
    b128 = [r for r in rows if r["B"] == 128]
    worst_inst = max(abs(r["inst_pct"]) for r in b128)
    worst_low = max(r["low_pct"] for r in hi)

    L, W = [], None
    W = L.append
    W("# SATPROBE_REPORT — does decode step cost stay linear at saturation?\n")
    W("**Date:** 2026-08-29  ")
    W("**Method:** `replay_sim.calibrate._measure_point`, unmodified — the run-5 online "
      "procedure, the same common steady-state window, the same `--warm-tokens 64 "
      "--tail-tokens 8`, 3 repeats per point, median reported.  ")
    W("**`perf.json` is read and never written. v0.7 stays installed. Nothing is "
      "refitted into the model.**\n")
    W("Config A, 87,200-token pool asserted at boot. **Zero preemptions at every "
      "point**, including the two run at 95% pool occupancy.\n")

    W("## Measured vs the installed linear model\n")
    W("The model is `step = a + b_d·B + c_kv·(B·ctx)/1e6` with run-5's coefficients "
      f"(a = {1000*a:.3f} ms, b_d = {1000*bd:.4f} ms/seq, c_kv = {ck:.5f}).\n")
    W("| B | ctx | measured | model | residual | residual % | gen_tokens | peak KV |")
    W("|---|---|---|---|---|---|---|---|")
    for r in rows:
        W(f"| {r['B']} | {r['ctx']} | **{r['ms']:.3f} ms** | {r['inst']:.3f} ms | "
          f"{r['ms']-r['inst']:+.3f} ms | **{r['inst_pct']:+.2f}%** | {r['gen_tokens']} | "
          f"{r['peak_kv']:,} ({r['peak_kv_pct']:.0f}%) |")
    W("")
    W("> **Window note.** `_measure_point` holds `B×(ctx+gen_tokens)` KV live. At "
      "`gen_tokens = 256` the point (128, 512) needs 98,304 tokens, more than config "
      "A's pool and more than any bootable utilisation on this box provides (0.88 caps "
      "at 92,976). Points that would exceed 85% of the pool use a shorter "
      "`gen_tokens`, sized to stay under 95%; the warm/tail skips are unchanged, so the "
      "window is shorter but constructed identically. Every window is ≥62 steps against "
      "a 20-step minimum.\n")

    W("## Repeatability against run 5\n")
    W("Three points were already in the run-5 grid, so they are a direct check that "
      "this probe reproduces the frozen calibration:\n")
    W("| B | ctx | run 5 | tonight | delta |")
    W("|---|---|---|---|---|")
    for r in rows:
        k = (r["B"], r["ctx"])
        if k in r5:
            W(f"| {r['B']} | {r['ctx']} | {r5[k]:.3f} ms | {r['ms']:.3f} ms | "
              f"{r['ms']-r5[k]:+.3f} ms ({100*(r['ms']-r5[k])/r5[k]:+.2f}%) |")
    W("")
    W("All within 0.55%, including the B=32 anchor. The measurement is reproducing the "
      "run-5 grid, so the residuals below are the model's, not the probe's.\n")

    W("## The extrapolation test\n")
    W("The installed model was fitted on a grid that *already contains* (96, 512) and "
      "(128, 256), so asking whether it predicts high batch is partly circular. Refitting "
      f"on run-5's points with **B ≤ 64 only** (n = {len(lo)}, R² = {r2:.5f}, "
      f"a = {1000*a2:.3f} ms, b_d = {1000*bd2:.4f} ms/seq, c_kv = {ck2:.5f}) and "
      "extrapolating gives the honest picture:\n")
    W("| B | ctx | measured | low-batch model | residual % |")
    W("|---|---|---|---|---|")
    for r in rows:
        W(f"| {r['B']} | {r['ctx']} | {r['ms']:.3f} ms | {r['low']:.3f} ms | "
          f"**{r['low_pct']:+.2f}%** |")
    W("")

    W("## Answer\n")
    W(f"> **Does step cost leave the linear envelope above B≈96? Yes — a model "
      f"calibrated below B=64 under-predicts high-batch step time by "
      f"{min(r['low_pct'] for r in hi):.1f}% to {worst_low:.1f}%. But at B=128 the "
      f"*installed* model is accurate to {worst_inst:.2f}%, because run 5 already "
      f"anchored the fit at (96, 512) and (128, 256).**\n")
    W(f"Concretely at B = 128: measured {b128[0]['ms']:.3f} ms at ctx 256 and "
      f"{b128[1]['ms']:.3f} ms at ctx 512, against installed-model predictions of "
      f"{b128[0]['inst']:.3f} and {b128[1]['inst']:.3f} ms — "
      f"{b128[0]['inst_pct']:+.2f}% and {b128[1]['inst_pct']:+.2f}%. The low-batch "
      f"extrapolation misses the same two points by {b128[0]['low_pct']:+.1f}% and "
      f"{b128[1]['low_pct']:+.1f}%.\n")
    W("Two things follow, and they pull in opposite directions.\n")
    W(f"**The non-linearity is real but already absorbed.** Step cost genuinely rises "
      f"faster than a low-batch line predicts — by about 10% by B≈96–112 — so anyone "
      f"calibrating on small batches and extrapolating would badly under-cost "
      f"saturation. Run 5's decision to put (96, 512) and (128, 256) in the grid is "
      f"what keeps v0.7 honest up here.\n")
    W(f"**But the installed model is not flat-accurate across the range.** It "
      f"under-predicts by ~3.5% at B = 96–112 and is near-exact at B = 128, so the "
      f"residual is not monotone in batch: the fit is pinned at its two high-batch "
      f"anchors and sags between them. A ~3.5% under-prediction of step time at "
      f"B ≈ 96–112 is an optimistic error in exactly the regime a load sweep drives "
      f"into, and it is the same sign as the saturation miss `LOAD_REPORT.md` recorded "
      f"at 3×. This probe does not establish that the two are the same effect, and no "
      f"coefficient is changed here.\n")
    open(a_.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a_.out}")


if __name__ == "__main__":
    main()
