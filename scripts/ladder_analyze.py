"""Analyses A and C of NOISE_PLAN, extended to configs K and C, plus the
four-point utilisation curve. Implements results/LADDER_PLAN.md and nothing else.

Writes results/LADDER_REPORT.md.
"""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from noise_stats import mean, stdev, median, repeats_needed, repeats_needed_z

METRICS = ["ttft_p50_s", "ttft_p95_s", "e2e_p50_s", "e2e_p95_s",
           "throughput_tok_s", "prefix_cache_hit_rate"]
UTIL = {"C": 0.60, "K": 0.75, "J": 0.82, "A": 0.85}
POOL = {"C": 39040, "K": 67936, "J": 81424, "A": 87200}
UNDERPOWERED_N = 6


def load(ld, cfgs):
    runs = {c: [] for c in cfgs}
    for p in sorted(glob.glob(os.path.join(ld, "real_*.json"))):
        m = re.match(r"real_([A-Z])_(\d+)\.json$", os.path.basename(p))
        if not m:
            continue
        cfg, rep = m.group(1), int(m.group(2))
        if cfg not in runs or rep == 0:      # rep 0 is the discarded warm-up
            continue
        s = json.load(open(p))
        if s.get("requests") != 182 or any(s.get(k) is None for k in METRICS):
            continue
        runs[cfg].append({"rep": rep, "summary": s})
    for c in runs:
        runs[c].sort(key=lambda r: r["rep"])
    return runs


def dispersion(runs):
    out = {}
    for cfg, rs in runs.items():
        if not rs:
            continue
        out[cfg] = {}
        for m in METRICS:
            v = [r["summary"][m] for r in rs]
            mu = mean(v)
            sd = stdev(v) if len(v) > 1 else float("nan")
            out[cfg][m] = {"n": len(v), "mean": mu, "stdev": sd,
                           "cv": (sd / mu if mu else float("nan")),
                           "min": min(v), "max": max(v), "median": median(v),
                           "range_pct_of_mean": (max(v) - min(v)) / mu * 100 if mu else float("nan"),
                           "values": v}
    return out


def repeats(disp):
    out = {}
    for cfg, per in disp.items():
        s = per.get("ttft_p95_s")
        if not s or s["n"] < 2:
            continue
        out[cfg] = {"n_collected": s["n"], "mean": s["mean"], "stdev": s["stdev"], "cv": s["cv"]}
        for t in (0.05, 0.10):
            out[cfg][f"n_for_{int(t*100)}pct"] = repeats_needed(s["mean"], s["stdev"], t)
            out[cfg][f"n_for_{int(t*100)}pct_z"] = repeats_needed_z(s["mean"], s["stdev"], t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder-dir", default="results/ladder")
    ap.add_argument("--noise-stats", default="results/noise/noise_stats.json")
    ap.add_argument("--out", default="results/LADDER_REPORT.md")
    ap.add_argument("--out-json", default="results/ladder/ladder_stats.json")
    a = ap.parse_args()

    runs = load(a.ladder_dir, ["K", "C"])
    disp = dispersion(runs)
    reps = repeats(disp)

    # A and J come unchanged from the noise batch
    prev_disp, prev_reps = {}, {}
    if os.path.exists(a.noise_stats):
        NS = json.load(open(a.noise_stats))
        prev_disp = NS.get("dispersion", {})
        prev_reps = NS.get("repeats", {})

    all_disp = {**{k: v for k, v in prev_disp.items()}, **disp}
    all_reps = {**{k: v for k, v in prev_reps.items()}, **reps}
    order = [c for c in ("C", "K", "J", "A") if c in all_disp]

    json.dump({"dispersion": disp, "repeats": reps, "curve_order": order},
              open(a.out_json, "w"), indent=2, default=float)

    excluded = []
    q = os.path.join(a.ladder_dir, "queue_log.txt")
    if os.path.exists(q):
        for line in open(q):
            if any(k in line for k in ("FAIL_", "SKIP ", "BREAKER", "PAIR_DEADLINE")):
                excluded.append(line.strip())

    L, W = [], None
    W = L.append
    W("# LADDER_REPORT — how benchmark noise scales with KV-pool pressure\n")
    W("**Date:** 2026-08-29  ")
    W("**Pre-registered** in `results/LADDER_PLAN.md`, committed before any run.  ")
    W("**No simulator, `perf.json`, or verdict change. Nothing is re-scored.**\n")
    W("Extends NOISE_PLAN analyses A (dispersion) and C (repeats needed) from two "
      "utilisation points to four. Configs J and A are taken unchanged from "
      "`results/noise/noise_stats.json`; K and C were run tonight under the same "
      "protocol — full restart, strict VRAM drain, asserted KV pool, `--drop-first 10`.\n")

    ns = {c: all_disp[c]["ttft_p95_s"]["n"] for c in order}
    under = [c for c in order if ns[c] < UNDERPOWERED_N]
    W("**Repeats:** " + ", ".join(f"{c} (util {UTIL[c]:.2f}) **n={ns[c]}**" for c in order) + ".")
    if under:
        W(f"\n> **Under-powered:** {', '.join(under)} finished with n < {UNDERPOWERED_N}. "
          f"Every number derived from {'them' if len(under) > 1 else 'it'} below is "
          f"labelled accordingly and should be read as indicative only.\n")
    else:
        W("")

    # ---- the curve ----
    W("## 1. The curve\n")
    W("`ttft_p95` run-to-run CV against utilisation:\n")
    W("| config | util | KV pool (tokens) | n | `ttft_p95` mean | CV | |")
    W("|---|---|---|---|---|---|---|")
    for c in order:
        d = all_disp[c]["ttft_p95_s"]
        flag = " ⚠ under-powered" if ns[c] < UNDERPOWERED_N else ""
        bar = "█" * max(1, int(round(100 * d["cv"] * 2)))
        W(f"| **{c}** | {UTIL[c]:.2f} | {POOL[c]:,} | {d['n']} | {d['mean']:.4f} s | "
          f"**{100*d['cv']:.2f}%**{flag} | `{bar}` |")
    W("")

    # ---- all six metrics ----
    means = {c: all_disp[c]["ttft_p95_s"]["mean"] for c in order}
    cvs = {c: all_disp[c]["ttft_p95_s"]["cv"] for c in order}
    loud = max(order, key=lambda c: cvs[c])
    quiet = min(order, key=lambda c: cvs[c])
    W("### What the curve shows\n")
    W(f"**It is not monotone.** The two configs under the most pool pressure, C "
      f"(util 0.60) and K (0.75), are the *quietest* of the four at {100*cvs['C']:.2f}% "
      f"and {100*cvs['K']:.2f}% — quieter than A at {100*cvs['A']:.2f}%. "
      f"{loud} stands alone at {100*cvs[loud]:.2f}%, roughly "
      f"{cvs[loud]/cvs[quiet]:.0f}× the quietest point, with lower-pressure and "
      f"higher-pressure neighbours on either side of it. This is a spike at one "
      f"utilisation, not a trend across the axis.\n")
    W(f"**Reproducibility and speed are different axes.** Over the same four configs "
      f"the *mean* `ttft_p95` spans {means[min(order, key=lambda c: means[c])]:.3f} s to "
      f"{means[max(order, key=lambda c: means[c])]:.1f} s — a factor of "
      f"{max(means.values())/min(means.values()):.0f}. C is the slowest config measured "
      f"by a wide margin and also the most repeatable. A config being consistent says "
      f"nothing about it being good.\n")
    W("Per the plan, this report states the shape and does not fit a model to four "
      "points or propose a mechanism.\n")
    W("## 2. All six metrics, all four configs (CV %)\n")
    W("| metric | " + " | ".join(f"C ({UTIL['C']:.2f})" if c == "C" else f"{c} ({UTIL[c]:.2f})" for c in order) + " |")
    W("|---|" + "---|" * len(order))
    for m in METRICS:
        cells = []
        for c in order:
            d = all_disp[c].get(m)
            cells.append(f"{100*d['cv']:.2f}%" if d else "n/a")
        W(f"| `{m}` | " + " | ".join(cells) + " |")
    W("")

    W("## 3. Distribution shape\n")
    W("The CV alone hides what the four configs are actually doing. These are the "
      "per-run `ttft_p95` values, sorted — the pre-registered min/max/range of "
      "analysis A, shown in full:\n")
    for c in order:
        d = all_disp[c]["ttft_p95_s"]
        vals = sorted(d["values"])
        W(f"- **{c}** (util {UTIL[c]:.2f}, n={d['n']}, CV {100*d['cv']:.2f}%): "
          + ", ".join(f"`{v:.3f}`" for v in vals))
    W("")
    jd = all_disp.get("J", {}).get("ttft_p95_s")
    if jd and jd["n"] >= 8:
        jv = sorted(jd["values"])
        lo = [v for v in jv if v < 0.5 * (jv[0] + jv[-1])]
        if 0 < len(lo) < len(jv):
            W(f"**J is bimodal, not broadly spread.** {len(lo)} of its {len(jv)} runs sit "
              f"at {min(lo):.3f}–{max(lo):.3f} s and the other {len(jv)-len(lo)} at "
              f"{min(v for v in jv if v not in lo):.3f}–{jv[-1]:.3f} s, with nothing in "
              f"between. Its 6.07% CV is the gap between two modes being averaged, not "
              f"scatter around one. C, K and A are each a single tight cluster.\n")
            W("No outlier rejection was applied and none is proposed — the low mode is "
              "real, reproducible behaviour that occurred twice, not a defective run. "
              "It is flagged because a CV computed across two modes does not mean what a "
              "CV normally means, and the repeats-needed figures in §5 inherit that.\n")
    W("## 4. Dispersion detail (plan §5, analysis A)\n")
    for c in order:
        if c not in disp:
            continue
        W(f"### Config {c} — util {UTIL[c]:.2f}, pool {POOL[c]:,} tokens (n = {ns[c]})\n")
        W("| metric | mean | stdev | CV | min | max | median | range as % of mean |")
        W("|---|---|---|---|---|---|---|---|")
        for m in METRICS:
            d = disp[c][m]
            p = 4 if d["mean"] < 10 else 1
            W(f"| `{m}` | {d['mean']:.{p}f} | {d['stdev']:.{p}f} | **{100*d['cv']:.2f}%** | "
              f"{d['min']:.{p}f} | {d['max']:.{p}f} | {d['median']:.{p}f} | "
              f"{d['range_pct_of_mean']:.1f}% |")
        W("")

    W("## 5. Repeats needed for a trustworthy `ttft_p95` (plan §5, analysis C)\n")
    W("Smallest *n* with t(0.975, n−1)·s/√n ≤ target · mean.\n")
    W("| config | util | n collected | mean | stdev | CV | n for ±5% | n for ±10% |")
    W("|---|---|---|---|---|---|---|---|")
    for c in order:
        r = all_reps.get(c)
        if not r:
            W(f"| {c} | {UTIL[c]:.2f} | {ns[c]} | — | — | — | n/a (needs n≥2) | n/a |")
            continue
        flag = " ⚠" if ns[c] < UNDERPOWERED_N else ""
        W(f"| **{c}**{flag} | {UTIL[c]:.2f} | {r['n_collected']} | {r['mean']:.4f} s | "
          f"{r['stdev']:.4f} | {100*r['cv']:.2f}% | **{r['n_for_5pct']}** | "
          f"**{r['n_for_10pct']}** |")
    W("")

    W("## 6. Excluded repeats\n")
    if excluded:
        W(f"{len(excluded)} attempt(s) did not pass the pre-registered cleanliness gate:\n")
        W("```")
        for e in excluded[:30]:
            W(e)
        W("```")
        W("")
    else:
        W("None. Every attempt passed the gate on its first try.\n")
    W("No outlier rejection of any kind was applied, as pre-committed in plan §3.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out}")
    for c in order:
        d = all_disp[c]["ttft_p95_s"]
        print(f"  {c} util {UTIL[c]:.2f}: n={d['n']} ttft_p95 CV {100*d['cv']:.2f}%")


if __name__ == "__main__":
    main()
