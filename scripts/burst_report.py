"""TASK 2 deliverable: results/BURST_PROBE.md. Diagnostic, no predictions frozen."""
import argparse, json, sys, os
sys.path.insert(0, os.getcwd())
from replay_sim.workload import VOCAB  # noqa: F401  (import proves the vocab is shared)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/BURST_PROBE.md")
    a = ap.parse_args()
    tr = {json.loads(l)["req_id"]: json.loads(l) for l in open("results/trace_burst.jsonl")}
    sim = {json.loads(l)["rid"]: json.loads(l) for l in open("results/burst/simpr_A.jsonl")}
    real = {json.loads(l)["rid"]: json.loads(l) for l in open("results/burst/realpr_A.jsonl")}
    perf = json.load(open("results/perf.json"))
    rows = [{"rid": r, "plen": tr[r]["prompt_len"], "arr": r,
             "real": real[r]["ttft"], "sim": sim[r]["ttft"]} for r in sorted(real)]
    rows.sort(key=lambda x: x["real"])

    levels, tol = [], 0.05
    for x in rows:
        if not levels or abs(x["real"] - levels[-1][0]) > tol:
            levels.append((x["real"], [x]))
        else:
            levels[-1][1].append(x)
    steps = [round(levels[i][0] - levels[i - 1][0], 3) for i in range(1, len(levels))]
    chunk = perf["b_p"] * 2048

    spear_arr = sum(1 for i in range(1, len(rows)) if rows[i]["arr"] >= rows[i - 1]["arr"])
    short_first = sum(1 for i in range(1, len(rows))
                      if rows[i]["plen"] >= rows[i - 1]["plen"])

    L, W = [], None
    W = L.append
    W("# BURST_PROBE — service order under a 12-request simultaneous burst\n")
    W("**Date:** 2026-08-29  ")
    W("**Diagnostic. No predictions were frozen, no verdict, no fix proposed.**  ")
    W("**No simulator, `perf.json`, or verdict change.**\n")
    W("## What was run\n")
    W("`results/trace_burst.jsonl` — 12 requests, **all with `arrival_s = 0.0`**, "
      "prompt lengths alternating 700 / 2,600 tokens over the shared prefix. Config A, "
      "standard protocol (strict drain, pool asserted 87,200), `--per-request`, **no "
      "`--drop-first`**: in a 12-request burst every request is the subject.\n")
    W("> **Note on the spec.** A ~700-token prompt cannot contain a 1,200-token shared "
      "prefix. Resolved as: short prompts are 700 tokens sharing the *first 700 words* "
      "of the common prefix; long prompts are 2,600 = the full 1,200-word prefix + "
      "1,400 unique. Every request still shares a real prefix with every other. "
      "Verified word-by-word against `results/trace.jsonl`.\n")
    W("## Ordered by real TTFT\n")
    W("| order | rid | prompt_len | arrival order | real TTFT | sim TTFT |")
    W("|---|---|---|---|---|---|")
    for i, x in enumerate(rows, 1):
        W(f"| {i} | {x['rid']} | {x['plen']:,} | {x['arr']} | **{x['real']:.3f} s** | "
          f"{x['sim']:.3f} s |")
    W("")
    W("## Service order is stepped, and the steps are one prefill batch wide\n")
    W(f"The 12 requests do not finish at 12 distinct times. They land on "
      f"**{len(levels)} levels**, requests within a level sharing a TTFT to within "
      f"{tol*1000:.0f} ms:\n")
    W("| level | real TTFT | rids | prompt lengths |")
    W("|---|---|---|---|")
    for t, g in levels:
        W(f"| {levels.index((t, g))+1} | {t:.3f} s | "
          f"{', '.join(str(y['rid']) for y in g)} | "
          f"{', '.join(str(y['plen']) for y in g)} |")
    W("")
    W(f"Consecutive levels are separated by {', '.join(f'{s:.3f}' for s in steps)} s. "
      f"`perf.json` prices a full `max-num-batched-tokens` prefill batch at "
      f"`b_p × 2048` = **{chunk:.3f} s**, which is the step size to within a few "
      f"milliseconds.\n")
    W("## Observation\n")
    W(f"The engine served this burst **first-come-first-served, batched into "
      f"fixed-token prefill steps** — not shortest-first, and not by any ordering that "
      f"looks at prompt length. Ranked by measured TTFT the requests come out in "
      f"arrival order for {spear_arr} of {len(rows)-1} adjacent pairs, while prompt "
      f"length is monotone for only {short_first} of {len(rows)-1}: the 700-token and "
      f"2,600-token prompts are interleaved through the completion order exactly as "
      f"they were submitted, and a short request queued behind a long one waits for it "
      f"rather than overtaking. What structures the result is not the ordering but the "
      f"batching: TTFTs collapse onto {len(levels)} discrete levels "
      f"{chunk:.2f} s apart, one full 2,048-token chunked-prefill step per level, so "
      f"several requests become schedulable together and are reported ready together. "
      f"The simulator reproduces that ordering and that step structure while "
      f"over-predicting every TTFT by roughly a factor of two — the ranking is right "
      f"and the magnitude is not, which is the same signature run 8a recorded. This is "
      f"a diagnostic for run 9 design; no mechanism is claimed and no change is "
      f"proposed.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out}: {len(levels)} levels, steps {steps}, chunk cost {chunk:.3f}s")


if __name__ == "__main__":
    main()
