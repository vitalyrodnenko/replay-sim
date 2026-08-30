# replay-sim

**Can an offline simulator predict what a vLLM configuration change will do to a real
GPU server — before you run it?** This repository is the complete, unedited record of
ten rounds of trying, on two RTX 4090s. Each round froze a numeric prediction in git,
then measured, then scored against a bar fixed in advance. Seven rounds failed. The
last two passed. The interesting part is not the final score but the audit trail: every
prediction is a commit that provably precedes the measurement that tested it, and no
commit in this repository has ever been rewritten.

## The articles

- **Article one — [TODO: paste URL]**
- **Article two — [TODO: paste URL]**

> Two placeholders above still need the real URLs before this README is useful to a
> visitor arriving from either piece.

## The record

| run | simulator | held-out config | v1 | v2 | verdict |
|---|---|---|---|---|---|
| [1](results/REPORT_run1_v0.md) | v0 | A/B/C, first contact | 1/11 | 1/11 | FAIL |
| [2](results/REPORT_run2_v02.md) | v0.2 | D, E | 12/23 | 18/23 | FAIL |
| [3](results/REPORT_run3_v03.md) | v0.3 | F, G | 10/12 | 11/12 | FAIL |
| [4](results/REPORT_run4_v04.md) | v0.4 | F, G (in-sample) | 10/12 | 11/12 | FAIL |
| [5](results/REPORT_run5_v05.md) | v0.5 | H, I | 10/12 | 11/12 | FAIL |
| [6](results/REPORT_run6_v06.md) | v0.6 | J | 5/6 | 5/6 | FAIL |
| [7](results/REPORT_run7_v07.md) | v0.7 | K | 5/6 | 5/6 | FAIL |
| 8a | — | *diagnostic, no verdict* | — | — | — |
| [9](results/REPORT_run9_v08.md) | v0.8 | L (bursty arrivals) | 4/6 | 6/6 | **PASS** |
| [10](results/REPORT_run10_v09.md) | v0.9 | M (bursts of 8) | 2/6 | 6/6 | **PASS** |

`v1` is the original bar: every metric's predicted config-change delta within 15
points. `v2`, adopted in writing between runs 4 and 5 and never applied retroactively,
additionally passes a latency row whose absolute error is within 15%. Both counts are
reported for every run. [`results/REPORT.md`](results/REPORT.md) is always the newest.

## → [PROTOCOL.md](PROTOCOL.md)

**The full internal protocol log lives in [PROTOCOL.md](PROTOCOL.md)** — every version
changelog from v0 to v0.9, the pre-registered protocol for each round, the verdict
criterion and the note recording why it changed, and the drop-in provenance notes. It
is the working document the runs were executed from, preserved verbatim. If you want to
know what was decided and when, read that.

## Layout

```
replay_sim/          the simulator and its harness
  workload.py          trace generator (agentic sessions, --bursty geometry)
  calibrate.py         fits the step-time model on real hardware, offline and online
  simulator.py         discrete-event model of vLLM's scheduler, KV pool, prefix cache
  bench.py             replays the same trace against a real vLLM server over HTTP
  compare.py           sim vs real, per metric
  verdict.py           scores criterion v1 and v2
  diagnose.py          per-request sim-vs-real alignment

results/
  REPORT.md            the newest run report
  REPORT_run<N>_*.md   one per run, never edited after its round closes
  PREDICTIONS_run<N>.md  numeric predictions, committed BEFORE the run that tested them
  NOISE_REPORT.md      how reproducible the benchmark itself is (14+14 repeats)
  LADDER_REPORT.md     noise vs KV-pool pressure, four utilisation points
  LOAD_REPORT.md       does the cost model survive the load axis (answer: to 2x)
  SATPROBE_REPORT.md   decode step cost at saturation, B up to 128
  SWEEP_REPORT.md      256-config capacity sweep
  SWEEP2_REPORT.md     capacity inside the validated envelope
  BOOT_MATRIX.md       vLLM grants different KV pools across identical boots
  BURST_PROBE.md       service order under a simultaneous burst
  COLDSTART_REPORT.md  the turn-0 burst, per request
  JMODES_REPORT.md     what separates config J's two measured modes
  vllm_issue_draft.md  draft upstream issue from the BOOT_MATRIX finding
  logs/                raw server, calibration and benchmark logs, verbatim
  thermal/             nvidia-smi samples taken during the measured runs

scripts/             serve / bench / probe / analysis wrappers used for every run
```

## Reproduce it

Requires a CUDA box for `calibrate.py` and `bench.py`. `workload.py`, `simulator.py`,
`compare.py` and `verdict.py` are pure Python and run anywhere.

```bash
python -m venv .venv && source .venv/bin/activate
pip install vllm httpx numpy
export MODEL=Qwen/Qwen3-32B-AWQ

# 1. trace — one file, read by both the simulator and the real bench
python -m replay_sim.workload --out results/trace.jsonl \
    --sessions 24 --turns 8 --rate 1.2

# 2. calibrate the step-time model on your own hardware (~15-20 min)
python -m replay_sim.calibrate --mode online --model $MODEL --out results/perf.json

# 3. predict BEFORE measuring, and commit the prediction.
#    Take <N> from the server's own startup log ("GPU KV cache size: N tokens")
#    for each --gpu-memory-utilization rather than guessing it.
python -m replay_sim.simulator --trace results/trace.jsonl --perf results/perf.json \
    --num-blocks <N> --drop-first 10 --out results/sim_A.json
git add results/sim_A.json && git commit -m "PREDICTIONS: frozen before real runs"

# 4. measure — fresh server per config
python -m replay_sim.bench --trace results/trace.jsonl --model $MODEL \
    --drop-first 10 --out results/real_A.json

# 5. score — the verdict is on the config-change delta, not absolute values
python -m replay_sim.verdict --sim results/sim_A.json results/sim_B.json \
    --real results/real_A.json results/real_B.json --labels A B
```

`scripts/` holds the exact wrappers used for the published runs, including the
strict-VRAM-drain and asserted-pool protocol that later rounds depend on.

## Methodology

**Predictions are committed before measurements.** Every `PREDICTIONS_run<N>.md` is a
commit that precedes the commit carrying that run's results. That ordering is the whole
claim, and it is checkable: `git log --follow results/PREDICTIONS_run7.md` against the
run-7 results commit, for any N.

**The git log is the audit trail.** Verdict criteria were changed once, between rounds,
in writing, with the motivation recorded and no retroactive application. Where a
prediction was wrong the report says falsified, not "partially confirmed". Where an
interpretation was later contradicted by better data — the noise-versus-pool-pressure
reading in `NOISE_REPORT.md`, the drain mechanism in `NOISE_PLAN.md` — a correction is
appended in place rather than the original being edited away.

**History is never rewritten.** No rebase, squash, amend, filter-branch or force push
has been applied to this repository, and none will be. The hashes and dates cited in
the articles and in the reports resolve verbatim.

**Authorship.** The early commits were authored as `replay-sim` with a personal address
and later ones under a GitHub noreply address; both are the same person. Rather than
amend 31 commits, a [`.mailmap`](.mailmap) normalises the display. `git log --format=%an`
still shows the original values, unchanged.

**Provenance of the logs.** Everything under `results/logs/` and `results/thermal/` is
published exactly as it was written during the runs, including machine-local absolute
paths and the workstation's hostname. Redacting them would make the tip inconsistent
with the evidence the reports cite. Nothing in them is security-sensitive: the only IP
that appears is RFC1918 and the hostname is a desktop machine.

## License

Apache-2.0 — see [LICENSE](LICENSE). Copyright 2026 Vitaly Rodnenko.
