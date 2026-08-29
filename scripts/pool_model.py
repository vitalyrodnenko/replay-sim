"""Size the KV pool vLLM grants for an arbitrary (util, mbt, mns) setting.

The sweep needs num_blocks for 256 combinations; the published series only ever
booted 10 of them. Rather than guess, this builds the mapping out of pool sizes
actually measured on this box -- the published runs plus tonight's probes.

Form:

    tokens(util, mbt, mns) = base(util) + off_mbt[mbt] + off_mns[mns]

  * base(util) is a straight line fitted to the utilisation points measured at the
    reference setting (mbt 2048, mns 128). Those points are very nearly exactly
    collinear, so this is interpolation, not extrapolation.
  * off_mbt and off_mns are MEASURED PER LEVEL, not fitted slopes. This matters:
    the pool is NOT monotonic in mbt. mbt=1024 and mbt=8192 both cost 4,944 tokens
    relative to mbt=2048, so any linear term in mbt is simply wrong.
  * The offsets are assumed independent of util. That assumption is directly
    supported: the mbt=8192 offset measured -4,944 tokens at util 0.85 (A->G) and
    -4,944 tokens at util 0.78 (F->I), identical. It is additionally checked
    out-of-sample by a held-out probe that moves all three axes at once.

Prefix caching does not enter: config B (caching off) was granted exactly the same
pool as config A.

usage: python scripts/pool_model.py [--probe-csv results/pool_probe.csv]
"""
import argparse, csv, json, os

REF_MBT, REF_MNS = 2048, 128

# Measured in the published series, each read from that run's own startup log
# (results/logs/kv_pool_*.txt).
PUBLISHED = [
    ("C", 0.60, 2048, 128, "on", 39040),
    ("E", 0.70, 2048, 128, "on", 58304),
    ("K", 0.75, 2048, 128, "on", 67936),
    ("F", 0.78, 2048, 128, "on", 73712),
    ("J", 0.82, 2048, 128, "on", 81424),
    ("A", 0.85, 2048, 128, "on", 87200),
    ("H", 0.88, 2048, 128, "on", 92976),
    ("D", 0.85, 2048,  32, "on", 87840),
    ("G", 0.85, 8192, 128, "on", 82256),
    ("I", 0.78, 8192, 128, "on", 68768),
]


def load_probes(path):
    pts = []
    if not os.path.exists(path):
        return pts
    with open(path) as f:
        for row in csv.DictReader(f):
            if row.get("status") != "OK" or not row.get("tokens"):
                continue
            pts.append((row["tag"], float(row["util"]), int(row["mbt"]),
                        int(row["mns"]), row["pc"], int(row["tokens"])))
    return pts


def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return slope, my - slope * mx


def build(points):
    ref = [(u, t) for _, u, b, s, _, t in points if b == REF_MBT and s == REF_MNS]
    if len(ref) < 3:
        raise SystemExit("need >=3 reference-setting points to fit base(util)")
    slope, inter = linfit([u for u, _ in ref], [t for _, t in ref])

    def base(u):
        return slope * u + inter

    off_mbt, off_mns = {REF_MBT: 0.0}, {REF_MNS: 0.0}
    for _, u, b, s, _, t in points:
        if s == REF_MNS and b != REF_MBT:
            off_mbt.setdefault(b, []) if False else None
            off_mbt[b] = t - base(u)
        if b == REF_MBT and s != REF_MNS:
            off_mns[s] = t - base(u)
    return {"slope": slope, "intercept": inter, "off_mbt": off_mbt,
            "off_mns": off_mns, "ref_mbt": REF_MBT, "ref_mns": REF_MNS,
            "base_points": len(ref)}


def predict(m, util, mbt, mns):
    ob, os_ = m["off_mbt"], m["off_mns"]
    kb, ks = str(mbt), str(mns)
    if kb not in ob and mbt not in ob:
        raise KeyError(f"no measured offset for mbt={mbt}")
    if ks not in os_ and mns not in os_:
        raise KeyError(f"no measured offset for mns={mns}")
    b = ob.get(mbt, ob.get(kb))
    s = os_.get(mns, os_.get(ks))
    return m["slope"] * util + m["intercept"] + b + s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-csv", default="results/pool_probe.csv")
    ap.add_argument("--out", default="results/pool_model.json")
    ap.add_argument("--block-size", type=int, default=16)
    ap.add_argument("--holdout", default=None,
                    help="tag of a probe to EXCLUDE from the fit and test against")
    a = ap.parse_args()

    pts = PUBLISHED + load_probes(a.probe_csv)
    seen, uniq = set(), []
    for p in pts:
        k = (p[1], p[2], p[3])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)

    holdout = [p for p in uniq if p[0] == a.holdout] if a.holdout else []
    train = [p for p in uniq if not (a.holdout and p[0] == a.holdout)]

    m = build(train)
    print(f"base(util) fitted on {m['base_points']} points at mbt={REF_MBT}, mns={REF_MNS}")
    print(f"  tokens = {m['slope']:.1f}*util + {m['intercept']:.1f}")
    print(f"  off_mbt (tokens vs mbt={REF_MBT}): "
          + ", ".join(f"{k}:{v:+,.0f}" for k, v in sorted(m["off_mbt"].items())))
    print(f"  off_mns (tokens vs mns={REF_MNS}): "
          + ", ".join(f"{k}:{v:+,.0f}" for k, v in sorted(m["off_mns"].items())))
    print()
    print(f"{'tag':<12}{'util':>6}{'mbt':>6}{'mns':>5}{'measured':>10}{'fitted':>10}{'resid':>9}{'resid %':>9}")
    worst = 0.0
    for tag, u, b, s, _, tok in train:
        f = predict(m, u, b, s)
        r = tok - f
        worst = max(worst, abs(r) / tok * 100)
        print(f"{tag:<12}{u:>6}{b:>6}{s:>5}{tok:>10,}{f:>10,.0f}{r:>+9.0f}{100*r/tok:>+8.3f}%")
    print(f"\nworst in-sample residual: {worst:.3f}%")

    if holdout:
        print("\n=== HELD-OUT ===")
        for tag, u, b, s, _, tok in holdout:
            f = predict(m, u, b, s)
            print(f"{tag}: predicted {f:,.0f}  measured {tok:,}  "
                  f"error {tok-f:+,.0f} tokens ({100*(tok-f)/tok:+.3f}%)")

    m.update({"block_size": a.block_size, "n_points": len(train),
              "worst_resid_pct": worst,
              "points": [{"tag": t, "util": u, "mbt": b, "mns": s, "pc": p, "tokens": k}
                         for t, u, b, s, p, k in train],
              "holdout": [{"tag": t, "util": u, "mbt": b, "mns": s, "tokens": k,
                           "predicted": predict(m, u, b, s)}
                          for t, u, b, s, _, k in holdout]})
    json.dump(m, open(a.out, "w"), indent=2)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
