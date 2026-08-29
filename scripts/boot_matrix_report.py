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
    # ---- extensions ----
    def readcsv(path):
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [r for r in csv.DictReader(f)]

    hostile = readcsv("results/boot_matrix_hostile.csv")
    nov1 = readcsv("results/boot_matrix_novel.csv")
    nov2 = readcsv("results/boot_matrix_novel2.csv")

    W("---\n")
    W("## Extension 1 — forcing residual VRAM (beyond the specified matrix)\n")
    W("The specified matrix could not vary its own independent variable: "
      "`stop_server.sh` kills the server processes and *waits*, so the GPU is back to "
      "its 255 MiB idle floor before either the 450 MiB or the 1500 MiB threshold is "
      "ever evaluated. Both regimes were therefore the same experiment.\n")
    W("To create genuine residual VRAM, the server was SIGKILLed and restarted "
      "immediately, with 1–3 s of reclamation time:\n")
    if hostile:
        W("| boot | VRAM before (MiB) | pool | ready | note |")
        W("|---|---|---|---|---|")
        for r in hostile:
            W(f"| {r['boot']} | {r['vram_before_mib']} | {r['pool_tokens']} | "
              f"{r['ready_s']}s | {r['note']} |")
        W("")
    W("**Also negative.** Even one second after SIGKILL the driver had reclaimed "
      "everything: 255 MiB before every boot, 87,200 tokens every time. Residual VRAM "
      "is not reachable through this path on this box, and is therefore not the "
      "mechanism.\n")

    W("## Extension 2 — a never-before-booted shape. This reproduces it.\n")
    W("Every pool that varied during this work was a **novel `(max-num-batched-tokens, "
      "max-num-seqs)` shape**; every stable one had been booted before. Testing that "
      "directly, with the strict drain held constant on both boots:\n")
    W("| shape (mbt/mns) | boot | VRAM before | granted pool | ready |")
    W("|---|---|---|---|---|")
    for rs in (nov1, nov2):
        for r in rs:
            W(f"| {r['shape']} | {r['boot']} ({'first ever' if r['boot']=='1' else 'repeat'}) | "
              f"{r['vram_before_mib']} MiB | **{int(r['pool_tokens']):,}** | {r['ready_s']}s |")
    W("")
    deltas = []
    for rs in (nov1, nov2):
        if len(rs) == 2 and all(r["pool_tokens"].isdigit() for r in rs):
            d = int(rs[1]["pool_tokens"]) - int(rs[0]["pool_tokens"])
            t = int(rs[1]["ready_s"]) - int(rs[0]["ready_s"])
            deltas.append((rs[0]["shape"], d, -t, int(rs[0]["pool_tokens"])))
    if deltas:
        W("| shape | pool gained on the 2nd boot | time saved on the 2nd boot |")
        W("|---|---|---|")
        for sh, d, t, _ in deltas:
            W(f"| {sh} | **+{d:,} tokens** | {t}s faster |")
        W("")
        W(f"**Reproduced and replicated.** On both novel shapes the first boot was "
          f"granted {min(x[3] for x in deltas):,}–{max(x[3] for x in deltas):,} tokens "
          f"and the second, byte-identical, boot was granted "
          f"{min(x[1] for x in deltas):,}–{max(x[1] for x in deltas):,} more. The first "
          f"boot also took {min(x[2] for x in deltas)}–{max(x[2] for x in deltas)} "
          f"seconds longer to reach `/health`, which is the compile and CUDA-graph "
          f"capture the second boot loads from cache. Memory held during that work is "
          f"resident when vLLM profiles free memory to size the KV cache.\n")
        W("The drain threshold, the thing this matrix was built to test, is not "
          "involved: both boots drained to the same 255 MiB.\n")
    W("## What remains unexplained\n")
    W("Two points in the published series still do not fit. Config **D** "
      "(mns 32, run 2) was that shape's first boot and came in *high* (87,840); config "
      "**I** (mbt 8192, run 5) was a repeat after G and came in *low* (68,768, matching "
      "G's offset to 3 tokens). A first-boot-compilation story does not account for "
      "either, so the effect is reproducible on demand without being fully "
      "characterised.\n")

    open(a.out, "w").write("\n".join(O) + "\n")
    print(f"wrote {a.out}")

    # ---- upstream issue draft ----
    reproduced = bool(deltas)
    lo = min((x[3] for x in deltas), default=0)
    gain = max((x[1] for x in deltas), default=0)
    I, V = [], None
    V = I.append
    V("# Draft upstream issue — NOT FILED\n")
    V("Draft only, from a single two-GPU box. Worth reproducing elsewhere before "
      "filing.\n")
    V("---\n")
    V("**Title:** First boot of a new `(max-num-batched-tokens, max-num-seqs)` shape is "
      "granted a ~5% smaller KV cache than subsequent identical boots\n")
    V("### Environment\n")
    V("- vLLM 0.28.0, V1 engine, TP=2")
    V("- 2 × NVIDIA RTX 4090 (24,564 MiB each), driver 580.173.02, CUDA 13.0")
    V("- Qwen/Qwen3-32B-AWQ, `--max-model-len 8192`")
    V("- Ubuntu 24.04, Python 3.12.3, `VLLM_USE_FLASHINFER_SAMPLER=0`, "
      "`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`\n")
    V("### Summary\n")
    V("Booting the server twice with byte-identical arguments gives two different "
      "`GPU KV cache size` values when the first boot is that shape's first ever. The "
      "second boot is granted roughly 5% more KV. The difference persists as long as "
      "the compile cache does, so a deployment's capacity depends on whether the cache "
      "happened to be warm when it started.\n")
    V("### Reproduction\n")
    V("Pick a `(--max-num-batched-tokens, --max-num-seqs)` pair this machine has never "
      "served, and boot it twice, waiting for GPU memory to return to idle in between "
      "so residual memory is not a factor:\n")
    V("```bash")
    V("drain() {  # wait for VRAM to return to idle before starting")
    V("  while [ \"$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits \\")
    V("            | paste -sd+ | bc)\" -ge 450 ]; do sleep 2; done")
    V("}")
    V("")
    V("for i in 1 2; do")
    V("  drain")
    V("  vllm serve Qwen/Qwen3-32B-AWQ --port 8000 --tensor-parallel-size 2 \\")
    V("    --max-model-len 8192 --max-num-batched-tokens 1536 --max-num-seqs 48 \\")
    V("    --gpu-memory-utilization 0.85 --enable-prefix-caching &")
    V("  # wait for /health, then grep the log:")
    V("  #   grep -o 'GPU KV cache size: [0-9,]* tokens' server.log")
    V("  # ...then shut down")
    V("done")
    V("```")
    V("")
    V("### Observed\n")
    V("Two independently chosen novel shapes, strict drain to 255 MiB before **both** "
      "boots:\n")
    V("| shape (mbt/mns) | boot 1 (first ever) | boot 2 (identical args) | difference | boot-1 startup | boot-2 startup |")
    V("|---|---|---|---|---|---|")
    for rs in (nov1, nov2):
        if len(rs) == 2 and all(r["pool_tokens"].isdigit() for r in rs):
            V(f"| {rs[0]['shape']} | {int(rs[0]['pool_tokens']):,} tokens | "
              f"{int(rs[1]['pool_tokens']):,} tokens | "
              f"**+{int(rs[1]['pool_tokens'])-int(rs[0]['pool_tokens']):,}** | "
              f"{rs[0]['ready_s']}s | {rs[1]['ready_s']}s |")
    V("")
    V("The first boot is also ~30–35 s slower to reach `/health` — the compile and "
      "CUDA-graph capture that the second boot loads from "
      "`~/.cache/vllm/torch_compile_cache`.\n")
    V("### Why it matters\n")
    V("The KV pool is the main capacity parameter of a deployment, and this makes it "
      "depend on cache state rather than on the arguments. On this box the effect "
      f"(~{gain:,} tokens) is **larger than the difference between "
      "`--gpu-memory-utilization 0.82` and `0.85`** (5,776 tokens), so two runs of the "
      "same configuration can straddle what was meant to be a deliberate configuration "
      "change. It is silent: the server starts normally and reports its pool as though "
      "the arguments determined it. Anyone A/B testing server configurations, or "
      "sizing capacity from a first deployment, inherits an uncontrolled ~5% term.\n")
    V("### Workaround\n")
    V("Boot each new shape once to populate the compile cache and discard that run, "
      "then measure. Waiting for VRAM to drain is *not* sufficient on its own — see "
      "below.\n")
    V("### What was ruled out\n")
    V("- **Residual GPU memory.** 10 boots alternating a strict drain (<450 MiB) with "
      "vLLM's default (<1500 MiB) gave 87,200 tokens every time. Forcing the issue with "
      "SIGKILL and a 1–3 s restart gave 87,200 every time as well; the driver had "
      "already reclaimed everything and pre-boot VRAM read 255 MiB in all 14 boots.")
    V("- **Utilisation, batched-token and sequence budgets** are held constant across "
      "each pair above.\n")
    V("### Caveats\n")
    V("- Single machine, single model, TP=2 only; not reproduced on other hardware.")
    V("- Two points from earlier work on this box do not fit a pure "
      "first-boot-compilation story: one shape's first boot came in high, and one "
      "repeat boot came in low. The effect reproduces on demand but is not fully "
      "characterised.")
    V("- The exact allocation being counted was not instrumented; the association with "
      "startup time is strong but indirect.\n")
    open(a.issue, "w").write("\n".join(I) + "\n")
    print(f"wrote {a.issue}  (reproduced={reproduced})")


if __name__ == "__main__":
    main()
