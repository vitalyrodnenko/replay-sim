"""TASK 3 deliverables: results/BOOT_MATRIX.md and results/vllm_issue_draft.md."""
import argparse, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from noise_stats import mean, stdev

EXPECTED = 87200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="results/boot_matrix.csv")
    ap.add_argument("--out", default="results/BOOT_MATRIX.md")
    ap.add_argument("--issue", default="results/vllm_issue_draft.md")
    a = ap.parse_args()

    rows = []
    with open(a.csv) as f:
        for r in csv.DictReader(f):
            if not r.get("pool_tokens"):
                continue
            r["ok"] = r["pool_tokens"].isdigit()
            if r["ok"]:
                r["pool"] = int(r["pool_tokens"])
                r["vram"] = int(r["vram_before_mib"]) if r["vram_before_mib"].isdigit() else None
            rows.append(r)
    good = [r for r in rows if r.get("ok")]
    strict = [r for r in good if r["mode"] == "strict"]
    loose = [r for r in good if r["mode"] == "loose"]

    def stats(g):
        if not g:
            return None
        p = [r["pool"] for r in g]
        v = [r["vram"] for r in g if r["vram"] is not None]
        return {"n": len(g), "pools": p, "distinct": sorted(set(p)),
                "mean": mean(p), "sd": stdev(p) if len(p) > 1 else 0.0,
                "min": min(p), "max": max(p), "spread": max(p) - min(p),
                "vram_mean": mean(v) if v else None,
                "vram_min": min(v) if v else None, "vram_max": max(v) if v else None,
                "all_expected": all(x == EXPECTED for x in p)}

    S, L = stats(strict), stats(loose)

    O, W = [], None
    W = O.append
    W("# BOOT_MATRIX — does the VRAM drain threshold determine the KV pool?\n")
    W("**Date:** 2026-08-29  ")
    W("**No simulator, `perf.json`, or verdict change.**\n")
    W("`results/NOISE_PLAN.md` recorded that booting identical settings twice granted "
      "82,656 and 87,680 KV tokens — a 5,024-token spread with no config change — and "
      "left the mechanism unresolved. This matrix tests one candidate directly: the "
      "VRAM drain threshold used before the boot.\n")
    W("## Method\n")
    W(f"Config-A settings (`--gpu-memory-utilization 0.85 --max-num-batched-tokens 2048 "
      f"--max-num-seqs 128 --enable-prefix-caching`, TP=2, Qwen3-32B-AWQ), booted "
      f"{len(rows)} times, alternating two teardown regimes:\n")
    W("- **strict** — wait until total VRAM across both GPUs is below **450 MiB** "
      "(the idle floor with the desktop session is 255 MiB)")
    W("- **loose** — `stop_server.sh`'s original behaviour: proceed as soon as total "
      "VRAM is below **1500 MiB**\n")
    W("Every boot in this matrix has a **warm** compile/CUDA-graph cache: this shape "
      "has been booted dozens of times on this box. The matrix therefore isolates the "
      "drain variable only, and says nothing about a genuinely cold shape.\n")
    W("## Raw results\n")
    W("| boot | mode | VRAM before (MiB) | granted pool (tokens) | vs expected | ready |")
    W("|---|---|---|---|---|---|")
    for r in rows:
        if r.get("ok"):
            d = r["pool"] - EXPECTED
            W(f"| {r['boot']} | {r['mode']} | {r['vram_before_mib']} | {r['pool']:,} | "
              f"{d:+,} | {r['ready_s']}s |")
        else:
            W(f"| {r['boot']} | {r['mode']} | {r['vram_before_mib']} | "
              f"**{r['pool_tokens']}** | — | — |")
    W("")
    W("## Summary\n")
    W("| regime | n | distinct pools granted | spread | mean VRAM before |")
    W("|---|---|---|---|---|")
    for name, g in (("strict (<450 MiB)", S), ("loose (<1500 MiB)", L)):
        if not g:
            W(f"| {name} | 0 | — | — | — |")
            continue
        W(f"| {name} | {g['n']} | {', '.join(f'{x:,}' for x in g['distinct'])} | "
          f"{g['spread']:,} tokens | {g['vram_mean']:.0f} MiB |")
    W("")

    if S and L:
        if S["all_expected"] and L["all_expected"]:
            verdict = ("**Both regimes produced the expected 87,200 tokens on every "
                       "boot.** This matrix did not reproduce the irreproducibility. "
                       "The drain threshold is therefore not sufficient on its own to "
                       "cause it, at least not with a warm shape cache and this box in "
                       "this state.")
        elif S["all_expected"] and not L["all_expected"]:
            verdict = (f"**The drain threshold reproduces it.** Every strict boot was "
                       f"granted exactly {EXPECTED:,} tokens; the loose boots spread "
                       f"over {L['spread']:,} tokens ({', '.join(f'{x:,}' for x in L['distinct'])}). "
                       f"Waiting for VRAM to drain below 450 MiB removes the variation.")
        else:
            verdict = (f"**Mixed.** strict spread {S['spread']:,} tokens, loose spread "
                       f"{L['spread']:,} tokens. The drain threshold does not cleanly "
                       f"separate the two regimes in this matrix.")
        W("## Outcome\n")
        W(verdict + "\n")
    open(a.out, "w").write("\n".join(O) + "\n")
    print(f"wrote {a.out}")

    # ---- upstream issue draft ----
    I, V = [], None
    V = I.append
    reproduced = bool(S and L and S["all_expected"] and not L["all_expected"])
    V("# Draft upstream issue — NOT FILED\n")
    V("Draft only. Check the observed values against a second machine before filing; "
      "everything below is from a single two-GPU box.\n")
    V("---\n")
    V("**Title:** KV cache size varies by ~6% across boots with identical arguments "
      "when prior GPU memory has not fully drained\n")
    V("### Environment\n")
    V("- vLLM 0.28.0, V1 engine, TP=2\n- 2 × RTX 4090 (24,564 MiB each), driver 580.173.02, CUDA 13.0\n"
      "- Qwen/Qwen3-32B-AWQ, `--max-model-len 8192`\n- Ubuntu 24.04, Python 3.12.3\n")
    V("### What happens\n")
    V("Booting the server twice with byte-identical arguments can produce different "
      "`GPU KV cache size` values. Observed on this box:\n")
    V("```")
    V("--gpu-memory-utilization 0.85 --max-num-batched-tokens 2048 \\")
    V("  --max-num-seqs 64 --enable-prefix-caching --tensor-parallel-size 2")
    V("")
    V("boot 1:  GPU KV cache size: 82,656 tokens")
    V("boot 2:  GPU KV cache size: 87,680 tokens     # same command line")
    V("```")
    V("A 5,024-token (6.1%) difference. For context, on this box that is larger than "
      "the difference between `--gpu-memory-utilization 0.82` and `0.85` (5,776 "
      "tokens), so two runs of the same configuration can straddle what is supposed to "
      "be a deliberate configuration change.\n")
    V("### Why it matters\n")
    V("The KV pool is the main capacity parameter of a deployment. If it is not "
      "reproducible across restarts, then capacity planning, autoscaling thresholds, "
      "and any A/B comparison of server configurations inherit an uncontrolled ~6% "
      "term. It is silent: the server starts normally and reports its pool as if it "
      "were determined by the arguments.\n")
    V("### Suspected cause and workaround\n")
    if reproduced:
        V("Residual GPU memory from a previous process at the moment vLLM profiles "
          "available memory. Waiting for VRAM to drain fully before starting removes "
          "the variation on this box:\n")
    else:
        V("Residual GPU memory from a previous process at the moment vLLM profiles "
          "available memory is the leading suspect, but see the caveat below — a "
          "controlled matrix on this box did **not** cleanly reproduce it on demand.\n")
    V("```bash")
    V("# wait for VRAM to return to idle before starting the server")
    V("while [ \"$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits \\")
    V("          | paste -sd+ | bc)\" -ge 450 ]; do sleep 2; done")
    V("vllm serve ...")
    V("```")
    V("")
    V("### Controlled matrix\n")
    if S and L:
        V(f"{len(rows)} boots of the same configuration, alternating a strict drain "
          f"(<450 MiB) with vLLM-teardown-then-immediate-restart (<1500 MiB residual "
          f"allowed):\n")
        V("| regime | boots | distinct pools | spread |")
        V("|---|---|---|---|")
        for name, g in (("strict <450 MiB", S), ("loose <1500 MiB", L)):
            if g:
                V(f"| {name} | {g['n']} | {', '.join(f'{x:,}' for x in g['distinct'])} | "
                  f"{g['spread']:,} tokens |")
        V("")
    V("### Caveats\n")
    V("- Single machine, single model, TP=2 only.\n"
      "- Every boot in the controlled matrix had a warm `torch.compile` / CUDA-graph "
      "cache; a genuinely cold shape was not tested.\n"
      "- The original 82,656 / 87,680 observation was made while probing many different "
      "`--max-num-batched-tokens` / `--max-num-seqs` combinations back to back, so the "
      "state that produced it may involve more than residual VRAM alone.")
    if not reproduced:
        V("- **The controlled matrix above did not reproduce the variation on demand.** "
          "The workaround is still effective in practice — 29 consecutive benchmark "
          "boots with the strict drain all landed on the expected pool — but the "
          "trigger is not fully characterised, and this draft should not claim it is.")
    V("")
    open(a.issue, "w").write("\n".join(I) + "\n")
    print(f"wrote {a.issue}  (reproduced={reproduced})")


if __name__ == "__main__":
    main()
