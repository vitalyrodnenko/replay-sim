"""Trace-driven discrete-event simulator of a vLLM-style engine.

Models, deliberately at v0 fidelity:
  - continuous batching with chunked prefill (token budget per step)
  - paged KV cache (block_size granularity) with a fixed block pool
  - prefix caching: content-hash chain over full blocks, LRU eviction
  - preemption by recompute when the pool is exhausted
  - step latency from a calibrated linear model:
      t_step = a + b_p * prefill_tokens + b_d * n_decode_seqs
                 + c_kv * kv_tokens_read / 1e6

Known simplifications (documented, to be tightened in v1):
  - no CUDA graph / compilation warmup effects
  - linear prefill cost (no quadratic attention term); acceptable at <8k ctx
  - single GPU, no TP communication model
  - sampling cost folded into constants

Outputs per request: ttft, e2e, queue time, cached_prefix_tokens; aggregate:
throughput, p50/p95, cache hit rate, gpu_busy_seconds (cost proxy).
"""
import argparse, hashlib, json, statistics
from dataclasses import dataclass, field

@dataclass
class Perf:
    a: float = 0.004          # s, fixed per-step overhead
    b_p: float = 0.000090     # s per prefill token
    b_d: float = 0.00035      # s per decoding sequence per step
    c_kv: float = 0.0035      # s per 1M KV tokens read per step

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls(**json.load(f))

@dataclass
class Cfg:
    block_size: int = 16
    num_blocks: int = 8000            # KV pool size (from gpu_mem_util)
    max_num_seqs: int = 128
    max_batched_tokens: int = 2048    # chunked prefill budget per step
    prefix_caching: bool = True

@dataclass
class Req:
    rid: int
    arrival: float
    prompt_len: int
    output_len: int
    block_hashes: list
    # runtime
    prefilled: int = 0
    generated: int = 0
    cached: int = 0
    blocks: list = field(default_factory=list)
    ttft: float = -1.0
    finish: float = -1.0
    start_service: float = -1.0
    preemptions: int = 0

def block_hash_chain(prompt_words_or_len, block_size, salt):
    """Content hashes per full block. For the sim we only need identity of
    shared prefixes; workload.py prompts are word lists, hash real content."""
    words = prompt_words_or_len
    n_full = len(words) // block_size
    hashes, h = [], salt
    for i in range(n_full):
        chunk = " ".join(words[i*block_size:(i+1)*block_size])
        h = hashlib.blake2s((h + chunk).encode(), digest_size=8).hexdigest()
        hashes.append(h)
    return hashes

class PrefixCache:
    """LRU over free-but-cached blocks, keyed by content-chain hash."""
    def __init__(self, enabled):
        self.enabled = enabled
        self.map = {}       # hash -> block_id
        self.lru = []       # hash order, oldest first
        self.hits = 0
        self.lookups = 0

    def match(self, hashes):
        if not self.enabled:
            return 0
        n = 0
        for h in hashes:
            self.lookups += 1
            if h in self.map:
                self.hits += 1
                n += 1
            else:
                break
        return n

    def insert(self, hashes):
        if not self.enabled:
            return
        for h in hashes:
            if h not in self.map:
                self.map[h] = 1
                self.lru.append(h)
            else:
                try: self.lru.remove(h)
                except ValueError: pass
                self.lru.append(h)

    def evict(self, k):
        e = 0
        while e < k and self.lru:
            h = self.lru.pop(0)
            self.map.pop(h, None)
            e += 1
        return e

def simulate(trace, cfg: Cfg, perf: Perf, verbose=False):
    reqs = [Req(r["req_id"], r["arrival_s"], r["prompt_len"], r["output_len"],
                block_hash_chain(r["prompt"].split(), cfg.block_size, "s"))
            for r in trace]
    reqs.sort(key=lambda r: r.arrival)
    pending = list(reqs)
    waiting, running = [], []
    cache = PrefixCache(cfg.prefix_caching)
    free_blocks = cfg.num_blocks
    cached_blocks = 0          # blocks held only by the prefix cache
    t = 0.0
    gpu_busy = 0.0
    steps = 0

    def blocks_needed(tokens):
        return (tokens + cfg.block_size - 1) // cfg.block_size

    def try_admit():
        nonlocal free_blocks, cached_blocks
        while waiting and len(running) < cfg.max_num_seqs:
            r = waiting[0]
            matched = cache.match(r.block_hashes)
            reuse_tokens = matched * cfg.block_size
            reuse_tokens = min(reuse_tokens, max(0, r.prompt_len - 1))
            need = blocks_needed(r.prompt_len + r.output_len) - matched
            # evict cold cached blocks if pool short
            if need > free_blocks:
                freed = cache.evict(need - free_blocks)
                cached_blocks -= freed
                free_blocks += freed
            if need > free_blocks:
                return
            free_blocks -= need
            r.cached = reuse_tokens
            r.prefilled = reuse_tokens
            r.start_service = t if r.start_service < 0 else r.start_service
            running.append(r)
            waiting.pop(0)

    def preempt_one():
        nonlocal free_blocks
        victim = max((r for r in running if r.generated < r.output_len),
                     key=lambda r: r.arrival, default=None)
        if victim is None:
            return False
        used = blocks_needed(victim.prompt_len + victim.generated)
        free_blocks += used
        victim.prefilled = 0
        victim.generated = 0
        victim.cached = 0
        victim.preemptions += 1
        running.remove(victim)
        waiting.insert(0, victim)
        return True

    while pending or waiting or running:
        # admit arrivals up to current time
        while pending and pending[0].arrival <= t:
            waiting.append(pending.pop(0))
        try_admit()
        if not running:
            nxt = pending[0].arrival if pending else None
            if waiting and nxt is None:
                # stuck: pool too small even after eviction -> preempt loop guard
                raise RuntimeError("deadlock: KV pool too small for a single request")
            t = max(t, nxt)
            continue

        # build one step: decodes first, then chunked prefill within budget
        budget = cfg.max_batched_tokens
        decoding = [r for r in running if r.prefilled >= r.prompt_len]
        n_dec = min(len(decoding), budget)
        budget -= n_dec
        prefill_tok = 0
        kv_read = sum(r.prompt_len + r.generated for r in decoding)
        for r in running:
            if budget <= 0: break
            if r.prefilled < r.prompt_len:
                chunk = min(budget, r.prompt_len - r.prefilled)
                r.prefilled += chunk
                prefill_tok += chunk
                kv_read += r.prefilled  # attention over accumulated ctx
                budget -= chunk

        dt = perf.a + perf.b_p * prefill_tok + perf.b_d * n_dec \
             + perf.c_kv * kv_read / 1e6
        t += dt
        gpu_busy += dt
        steps += 1

        finished = []
        for r in decoding[:n_dec]:
            if r.generated == 0 and r.ttft < 0:
                r.ttft = t - r.arrival
            r.generated += 1
            if r.generated >= r.output_len:
                r.finish = t
                finished.append(r)
        # first-token edge: request whose prefill just completed this step
        for r in running:
            if r.prefilled >= r.prompt_len and r.ttft < 0 and r.generated == 0:
                pass  # ttft set on its first decode step above
        for r in finished:
            running.remove(r)
            used = blocks_needed(r.prompt_len + r.generated)
            # prompt full-blocks stay resident in the prefix cache (evictable);
            # blocks whose content is already cached are shared, so only newly
            # cached content is withheld from the free pool
            new_h = [h for h in r.block_hashes if h not in cache.map] \
                    if cfg.prefix_caching else []
            cache.insert(r.block_hashes)
            keep = len(new_h)
            cached_blocks += keep
            free_blocks += used - keep
        try_admit()
        # emergency preemption if nothing can run but waiting exists
        if waiting and not running:
            if not preempt_one():
                freed = cache.evict(10**9)
                cached_blocks -= freed
                free_blocks += freed
            try_admit()

    return reqs, {
        "steps": steps, "gpu_busy_s": gpu_busy, "makespan_s": t,
        "cache_hit_rate": (cache.hits / cache.lookups) if cache.lookups else 0.0,
    }

cached_blocks_holder = [0]

def summarize(reqs, agg):
    ttfts = sorted(r.ttft for r in reqs)
    e2e = sorted(r.finish - r.arrival for r in reqs)
    out_tok = sum(r.output_len for r in reqs)
    cached = sum(r.cached for r in reqs)
    prompt = sum(r.prompt_len for r in reqs)
    def p(v, q): return v[min(len(v)-1, int(q*len(v)))]
    return {
        "requests": len(reqs),
        "ttft_p50_s": round(p(ttfts, .5), 3), "ttft_p95_s": round(p(ttfts, .95), 3),
        "e2e_p50_s": round(p(e2e, .5), 3),   "e2e_p95_s": round(p(e2e, .95), 3),
        "throughput_tok_s": round(out_tok / agg["makespan_s"], 1),
        "makespan_s": round(agg["makespan_s"], 1),
        "gpu_busy_s": round(agg["gpu_busy_s"], 1),
        "gpu_s_per_1k_out_tok": round(1000 * agg["gpu_busy_s"] / out_tok, 3),
        "prefix_cache_hit_rate": round(agg["cache_hit_rate"], 3),
        "prompt_tokens_reused_frac": round(cached / prompt, 3),
        "preemptions": sum(r.preemptions for r in reqs),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--perf", default=None, help="perf.json from calibrate.py")
    ap.add_argument("--num-blocks", type=int, default=8000)
    ap.add_argument("--max-num-seqs", type=int, default=128)
    ap.add_argument("--max-batched-tokens", type=int, default=2048)
    ap.add_argument("--no-prefix-caching", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    trace = [json.loads(l) for l in open(a.trace)]
    perf = Perf.load(a.perf) if a.perf else Perf()
    cfg = Cfg(num_blocks=a.num_blocks, max_num_seqs=a.max_num_seqs,
              max_batched_tokens=a.max_batched_tokens,
              prefix_caching=not a.no_prefix_caching)
    reqs, agg = simulate(trace, cfg, perf)
    s = summarize(reqs, agg)
    s["config"] = {"num_blocks": cfg.num_blocks, "max_num_seqs": cfg.max_num_seqs,
                   "max_batched_tokens": cfg.max_batched_tokens,
                   "prefix_caching": cfg.prefix_caching}
    print(json.dumps(s, indent=2))
    if a.out:
        json.dump(s, open(a.out, "w"), indent=2)

if __name__ == "__main__":
    main()
