"""Compute analyses A-E of results/NOISE_PLAN.md and write results/NOISE_REPORT.md.

The plan was committed before any run. This script implements it and nothing else;
anything unplanned goes in a clearly separated section of the report.
"""
import argparse, glob, json, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from noise_stats import (mean, stdev, median, bench_percentile, spearman,
                         repeats_needed, repeats_needed_z)

METRICS = ["ttft_p50_s", "ttft_p95_s", "e2e_p50_s", "e2e_p95_s",
           "throughput_tok_s", "prefix_cache_hit_rate"]
PCT_METRICS = {"ttft_p50_s": ("ttft", .5), "ttft_p95_s": ("ttft", .95),
               "e2e_p50_s": ("e2e", .5), "e2e_p95_s": ("e2e", .95)}
DROP_FIRST = 10
B_BOOT = 10000
SEED = 12345


def load_runs(nd):
    runs = {"A": [], "J": []}
    for p in sorted(glob.glob(os.path.join(nd, "real_*.json"))):
        m = re.match(r"real_([AJ])_(\d+)\.json$", os.path.basename(p))
        if not m:
            continue
        cfg, rep = m.group(1), int(m.group(2))
        if rep == 0:
            continue          # A_00 is the discarded warm-up (NOISE_PLAN amendment)
        s = json.load(open(p))
        if s.get("requests") != 182 or any(s.get(k) is None for k in METRICS):
            continue
        pr = os.path.join(nd, f"realpr_{cfg}_{rep:02d}.jsonl")
        rows = [json.loads(l) for l in open(pr)] if os.path.exists(pr) else []
        rows.sort(key=lambda r: r["rid"])
        kept = rows[DROP_FIRST:]
        runs[cfg].append({"cfg": cfg, "rep": rep, "summary": s,
                          "ttft": [r["ttft"] for r in kept],
                          "e2e": [r["e2e"] for r in kept]})
    for c in runs:
        runs[c].sort(key=lambda r: r["rep"])
    return runs


def analysis_A(runs):
    out = {}
    for cfg, rs in runs.items():
        out[cfg] = {}
        for m in METRICS:
            v = [r["summary"][m] for r in rs]
            if not v:
                continue
            mu, sd = mean(v), (stdev(v) if len(v) > 1 else float("nan"))
            out[cfg][m] = {"n": len(v), "mean": mu, "stdev": sd,
                           "cv": (sd / mu if mu else float("nan")),
                           "min": min(v), "max": max(v), "median": median(v),
                           "range_pct_of_mean": (max(v) - min(v)) / mu * 100 if mu else float("nan"),
                           "values": v}
    return out


def analysis_B(runs):
    rng = np.random.default_rng(SEED)
    out = {}
    for cfg, rs in runs.items():
        out[cfg] = {}
        for m, (field, q) in PCT_METRICS.items():
            widths, cis = [], []
            for r in rs:
                x = np.asarray(r[field], dtype=float)
                if x.size == 0:
                    continue
                n = x.size
                idx = rng.integers(0, n, size=(B_BOOT, n))
                samp = np.sort(x[idx], axis=1)
                k = min(n - 1, int(q * n))          # bench.py's estimator exactly
                stat = samp[:, k]
                lo, hi = np.percentile(stat, [2.5, 97.5])
                point = bench_percentile(sorted(x.tolist()), q)
                cis.append({"rep": r["rep"], "point": point, "lo": float(lo), "hi": float(hi),
                            "width": float(hi - lo),
                            "width_pct": float((hi - lo) / point * 100) if point else float("nan")})
                widths.append(float(hi - lo))
            out[cfg][m] = {"per_run": cis,
                           "median_width": median(widths) if widths else float("nan"),
                           "median_width_pct": median([c["width_pct"] for c in cis]) if cis else float("nan")}
    return out


def analysis_C(A):
    out = {}
    for cfg, per in A.items():
        s = per.get("ttft_p95_s")
        if not s or s["n"] < 2:
            continue
        out[cfg] = {"n_collected": s["n"], "mean": s["mean"], "stdev": s["stdev"],
                    "cv": s["cv"]}
        for tgt in (0.05, 0.10):
            out[cfg][f"n_for_{int(tgt*100)}pct"] = repeats_needed(s["mean"], s["stdev"], tgt)
            out[cfg][f"n_for_{int(tgt*100)}pct_z"] = repeats_needed_z(s["mean"], s["stdev"], tgt)
    return out


def published_rows():
    """Frozen published rows: runs 5-7 from their verdict JSONs, runs 1-4
    recomputed from the frozen sim/real pairs with the unmodified scorer."""
    rows = []
    for run, path in ((5, "results/verdict_heldout_run5.json"),
                      (6, "results/verdict_heldout_run6.json"),
                      (7, "results/verdict_heldout_run7.json")):
        if os.path.exists(path):
            for r in json.load(open(path))["rows"]:
                rows.append({**r, "run": run, "source": os.path.basename(path)})
    sys.path.insert(0, os.getcwd())
    try:
        from replay_sim.verdict import score
    except Exception:
        return rows
    MAN = {
        1: (["A", "B", "C"], "results/sim_{}_v0_run1.json", "results/real_{}_v0_run1.json"),
        2: (["A", "B", "C", "D", "E"], "results/sim_{}_v02_run2.json", "results/real_{}_v02_run2.json"),
        3: (["A", "F", "G"], "results/sim_{}.json", "results/real_{}.json"),
        4: (["A", "F", "G"], "results/sim_{}_v04_run4.json", "results/real_{}.json"),
    }
    for run, (labels, sp, rp) in MAN.items():
        try:
            sims = [json.load(open(sp.format(l))) for l in labels]
            reals = [json.load(open(rp.format(l))) for l in labels]
        except FileNotFoundError:
            continue
        for r in score(sims, reals, labels):
            rows.append({**r, "run": run, "source": f"recomputed from {sp.format('*')}"})
    return rows


def analysis_D(A, rows):
    cvA = {m: A["A"][m]["cv"] for m in METRICS if m in A.get("A", {})}
    cvJ = {m: A["J"][m]["cv"] for m in METRICS if m in A.get("J", {})}
    out = {"cv_A": cvA, "cv_J": cvJ, "primary": [], "sensitivity": []}
    for mode in ("primary", "sensitivity"):
        for r in rows:
            m = r["metric"]
            if m not in cvA or m not in cvJ:
                continue
            ca = cvA[m]
            if r["config"] == "J":
                cx = cvJ[m]
            elif r["config"] == "A":
                cx = cvA[m]
            else:
                cx = max(ca, cvJ[m]) if mode == "primary" else min(ca, cvJ[m])
            sd = abs(1 + r["real_delta"]) * ((ca ** 2 + cx ** 2) ** 0.5)
            half = 1.96 * sd
            out[mode].append({
                "run": r["run"], "config": r["config"], "metric": m,
                "gap_pt": 100 * r["gap"], "band_pt": 100 * half,
                "inside": r["gap"] <= half,
                "abs_err_pct": 100 * abs(r["abs_err"]),
                "abs_band_pct": 100 * 1.96 * cx,
                "abs_inside": abs(r["abs_err"]) <= 1.96 * cx,
                "v1": r["v1"], "v2": r["v2"], "cv_x_used": cx,
            })
    return out


def analysis_E(runs, ctx_csv):
    ctx = {}
    if os.path.exists(ctx_csv):
        import csv
        with open(ctx_csv) as f:
            for row in csv.DictReader(f):
                try:
                    t = row["temp_c"].split("/")[0]
                    ctx[row["tag"]] = float(t)
                except Exception:
                    pass
    out = {}
    for cfg, rs in runs.items():
        if len(rs) < 4:
            continue
        y = [r["summary"]["ttft_p95_s"] for r in rs]
        idx = [r["rep"] for r in rs]
        rho_i, p_i = spearman(idx, y)
        temps = [ctx.get(f"{cfg}_{r['rep']:02d}") for r in rs]
        entry = {"n": len(rs), "rho_index": rho_i, "p_index": p_i}
        if all(t is not None for t in temps) and len(set(temps)) > 1:
            rho_t, p_t = spearman(temps, y)
            entry.update({"rho_temp": rho_t, "p_temp": p_t, "temps": temps})
        out[cfg] = entry
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise-dir", default="results/noise")
    ap.add_argument("--out-json", default="results/noise/noise_stats.json")
    a = ap.parse_args()
    runs = load_runs(a.noise_dir)
    print(f"clean runs: A={len(runs['A'])} J={len(runs['J'])}")
    if not runs["A"] or not runs["J"]:
        raise SystemExit("no clean runs yet")
    A = analysis_A(runs)
    B = analysis_B(runs)
    C = analysis_C(A)
    rows = published_rows()
    D = analysis_D(A, rows)
    E = analysis_E(runs, os.path.join(a.noise_dir, "run_context.csv"))
    json.dump({"A": A, "B": B, "C": C, "D": D, "E": E,
               "n_published_rows": len(rows)},
              open(a.out_json, "w"), indent=2, default=float)
    print(f"wrote {a.out_json}")
    for cfg in ("A", "J"):
        s = A[cfg]["ttft_p95_s"]
        print(f"  {cfg}: ttft_p95 mean={s['mean']:.3f}s sd={s['stdev']:.3f} CV={100*s['cv']:.1f}% "
              f"n={s['n']}  -> repeats for +/-5%: {C[cfg]['n_for_5pct']}, +/-10%: {C[cfg]['n_for_10pct']}")


if __name__ == "__main__":
    main()
