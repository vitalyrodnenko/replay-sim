"""Size the KV pool vLLM grants for an arbitrary (util, mbt, mns) setting.

The sweep needs num_blocks for 256 combinations; the published series only ever
booted 10 of them, and tonight's probing showed the pool is NOT reproducible across
boots (identical settings gave 82,656 and 87,680 tokens -- see the amendment in
results/NOISE_PLAN.md). So this module is explicit about how much each number is
worth, rather than pretending to a precision the box does not have.

    tokens(util, mbt, mns) = base(util) + off_mbt[mbt] + off_mns[mns]

base(util) is fitted on the eight utilisation points measured at the reference
setting (mbt 2048, mns 128) -- the shape used by nearly every run in the series.
Those eight are collinear to within 4 tokens, so base() is trustworthy.

The offsets are a hand-audited table, not a fit, because their provenance differs
and that difference is the whole point:

  CONFIRMED  measured twice, consistently, at two different utilisations
  PUBLISHED  a single measurement from the published series
  SINGLE     one probe tonight, and tonight showed single probes can be off by
             ~5,000 tokens for reasons that are not understood
  ESTIMATED  no measurement at all; extrapolated from the neighbouring levels

`--variant optimistic` adds back 5,024 tokens (the size of the observed
irreproducibility) to every SINGLE/ESTIMATED level, so the sweep can be run both
ways and the ranking checked for robustness against this exact uncertainty.
"""
import argparse, csv, json, os

REF_MBT, REF_MNS = 2048, 128
IRREPRODUCIBILITY_TOKENS = 5024   # 87,680 - 82,656, same settings, two boots

# util points at the reference shape (mbt 2048, mns 128), from each run's own log
BASE_POINTS = [
    ("C", 0.60, 39040), ("p_u065", 0.65, 48672), ("E", 0.70, 58304),
    ("K", 0.75, 67936), ("F", 0.78, 73712), ("J", 0.82, 81424),
    ("A", 0.85, 87200), ("H", 0.88, 92976),
]

# offset, confidence, provenance
OFF_MBT = {
    1024: (-4944, "SINGLE",    "p_mbt1024 tonight, one boot"),
    2048: (0,     "CONFIRMED", "reference shape, booted dozens of times in the series"),
    4096: (-5184, "SINGLE",    "p_mbt4096 tonight, one boot"),
    8192: (-4944, "CONFIRMED", "G at util 0.85 (-4,944) and I at util 0.78 (-4,947), agree to 3 tokens"),
}
OFF_MNS = {
    16:  (700,  "ESTIMATED", "no clean measurement; extrapolated from 32:+640, 64:+480, 128:0"),
    32:  (640,  "PUBLISHED", "config D, run 2"),
    64:  (480,  "SINGLE",    "p_repeat_mns64 (87,680); the earlier p_mns64 boot gave 82,656"),
    128: (0,    "CONFIRMED", "reference shape"),
}


def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    s = sxy / sxx
    return s, my - s * mx


def build(variant="measured"):
    slope, inter = linfit([u for _, u, _ in BASE_POINTS], [t for _, _, t in BASE_POINTS])
    bump = IRREPRODUCIBILITY_TOKENS if variant == "optimistic" else 0
    ob = {k: (v + (bump if c in ("SINGLE", "ESTIMATED") else 0), c, p)
          for k, (v, c, p) in OFF_MBT.items()}
    om = {k: (v + (bump if c in ("SINGLE", "ESTIMATED") else 0), c, p)
          for k, (v, c, p) in OFF_MNS.items()}
    return {"slope": slope, "intercept": inter, "variant": variant,
            "off_mbt": {str(k): v[0] for k, v in ob.items()},
            "off_mns": {str(k): v[0] for k, v in om.items()},
            "off_mbt_meta": {str(k): {"tokens": v[0], "confidence": v[1], "provenance": v[2]}
                             for k, v in ob.items()},
            "off_mns_meta": {str(k): {"tokens": v[0], "confidence": v[1], "provenance": v[2]}
                             for k, v in om.items()},
            "block_size": 16, "base_points": len(BASE_POINTS),
            "irreproducibility_tokens": IRREPRODUCIBILITY_TOKENS}


def predict(m, util, mbt, mns):
    return (m["slope"] * util + m["intercept"]
            + m["off_mbt"][str(mbt)] + m["off_mns"][str(mns)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["measured", "optimistic"], default="measured")
    ap.add_argument("--out", default="results/pool_model.json")
    a = ap.parse_args()
    m = build(a.variant)
    print(f"variant: {a.variant}")
    print(f"base(util) on {m['base_points']} reference-shape points: "
          f"tokens = {m['slope']:.1f}*util + {m['intercept']:.1f}")
    resid = [(t - (m['slope'] * u + m['intercept']), tag) for tag, u, t in BASE_POINTS]
    print(f"  worst base residual: {max(abs(r) for r, _ in resid):.0f} tokens")
    for name, meta in (("off_mbt", m["off_mbt_meta"]), ("off_mns", m["off_mns_meta"])):
        print(f"\n{name}:")
        for k, v in sorted(meta.items(), key=lambda kv: int(kv[0])):
            print(f"  {k:>5}: {v['tokens']:>+7,}  [{v['confidence']:<9}] {v['provenance']}")
    json.dump(m, open(a.out, "w"), indent=2)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
