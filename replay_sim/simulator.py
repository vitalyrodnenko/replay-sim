"""Trace-driven discrete-event simulator of a vLLM-style engine. v0.2

v0.2 changes, driven by the 2026-08-27 validation run (see REPORT.md):
  1. Prefix-cache blocks are published as prefill computes them, not on
     request completion. Overlapping requests share the system prompt.
  2. Incremental KV allocation: prompt blocks at admission, decode blocks
     lazily per step. Allocation failure triggers eviction, then routine
     preemption-by-recompute (latest arrival first), matching vLLM.
  3. The prefix cache is coupled to the block pool: cached blocks occupy
     pool capacity (shared, refcounted via pins) and are evicted LRU
     under allocation pressure. Shrinking the pool now degrades hit rate.
  4. prefix_cache_hit_rate is token-level (reused prompt tokens / prompt
     tokens), directly comparable to vLLM /metrics. The block-lookup rate
     is reported separately as block_lookup_hit_rate.
  5. block_size is a CLI parameter.

Step latency model unchanged:
  t_step = a + b_p*prefill_tokens + b_d*n_decode + c_kv*kv_read/1e6

Remaining known simplifications: no CUDA-graph warmup, linear prefill
(no quadratic attention term), TP comm folded into calibrated constants
(calibrate at high batch to absorb it), swap-mode preemption not modeled.
"""
import argparse, hashlib, json
from dataclasses import dataclass, field

@dataclass
class Perf:
    a: float = 0.004
    b_p: float = 0.000090
    b_d: float = 0.00035
    c_kv: float = 0.0035
    @classmethod
    def load(cls, path):
        """Load the four coefficients, ignoring provenance metadata.

        run 4: perf.json now also carries "a_source"/"note"/"online_fit" so a
        hybrid fit (online `a`, offline b_p/b_d/c_kv) is self-describing. This
        loader change is the only edit to simulator.py since v0.3 and touches
        no physics -- the step model below is byte-identical to v0.3.
        """
        with open(path) as f:
            d = json.load(f)
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})

@dataclass
class Cfg:
    block_size: int = 16
    num_blocks: int = 8000
    max_num_seqs: int = 128
    max_batched_tokens: int = 2048
    prefix_caching: bool = True

@dataclass
class Req:
    rid: int
    arrival: float
    prompt_len: int
    output_len: int
    hashes: list
    prefilled: int = 0
    generated: int = 0
    cached: int = 0            # reused prompt tokens (token-level)
    alloc: int = 0             # non-cache blocks owned (tail + decode)
    inserted: int = 0          # how many full prompt blocks published
    pinned: list = field(default_factory=list)   # hashes this req pins
    ttft: float = -1.0
    finish: float = -1.0
    preemptions: int = 0

def hash_chain(words, block_size, salt="s"):
    n_full = len(words) // block_size
    hashes, h = [], salt
    for i in range(n_full):
        chunk = " ".join(words[i*block_size:(i+1)*block_size])
        h = hashlib.blake2s((h + chunk).encode(), digest_size=8).hexdigest()
        hashes.append(h)
    return hashes

class Cache:
    """Refcounted prefix cache sharing the block pool. One hash = one block.
    pins>0 -> in use by running request(s); pins==0 -> evictable, LRU."""
    def __init__(self, enabled):
        self.enabled = enabled
        self.pins = {}      # hash -> pin count
        self.lru = []       # unpinned hashes, oldest first
        self.tok_hits = 0
        self.blk_lookups = 0
        self.blk_hits = 0

    def blocks(self):
        return len(self.pins)

    def match_and_pin(self, hashes):
        if not self.enabled:
            return 0, []
        n, pinned = 0, []
        for h in hashes:
            self.blk_lookups += 1
            if h in self.pins:
                self.blk_hits += 1
                if self.pins[h] == 0:
                    try: self.lru.remove(h)
                    except ValueError: pass
                self.pins[h] += 1
                pinned.append(h)
                n += 1
            else:
                break
        return n, pinned

    def publish(self, h):
        """Insert a freshly computed block, pinned by its owner."""
        if not self.enabled:
            return False
        if h in self.pins:
            return False
        self.pins[h] = 1
        return True

    def pin_existing(self, h):
        if h in self.pins:
            if self.pins[h] == 0:
                try: self.lru.remove(h)
                except ValueError: pass
            self.pins[h] += 1
            return True
        return False

    def unpin(self, h):
        if h in self.pins:
            self.pins[h] -= 1
            if self.pins[h] <= 0:
                self.pins[h] = 0
                self.lru.append(h)

    def evict(self, k):
        e = 0
        while e < k and self.lru:
            h = self.lru.pop(0)
            del self.pins[h]
            e += 1
        return e

def simulate(trace, cfg: Cfg, perf: Perf):
    bs = cfg.block_size
    reqs = [Req(r["req_id"], r["arrival_s"], r["prompt_len"], r["output_len"],
                hash_chain(r["prompt"].split(), bs))
            for r in trace]
    reqs.sort(key=lambda r: r.arrival)
    pending = list(reqs)
    waiting, running = [], []
    cache = Cache(cfg.prefix_caching)
    total = cfg.num_blocks
    t, gpu_busy, steps, preempt_total = 0.0, 0.0, 0, 0

    def bl(tokens):
        return (tokens + bs - 1) // bs

    def free_blocks():
        return total - cache.blocks() - sum(r.alloc for r in running)

    def reclaim(n):
        """Make room for n blocks: evict cold cache first."""
        short = n - free_blocks()
        if short > 0:
            cache.evict(short)
        return free_blocks() >= n

    def release(r, keep_cache):
        for h in r.pinned:
            cache.unpin(h)
        r.pinned = []
        r.alloc = 0
        if not keep_cache:
            pass  # published blocks stay in cache, evictable once unpinned

    def preempt_victim(exclude=None):
        nonlocal preempt_total
        cands = [r for r in running if r is not exclude]
        if not cands:
            return None
        v = max(cands, key=lambda r: r.arrival)
        release(v, keep_cache=True)
        v.prefilled = 0
        v.generated = 0
        v.cached = 0
        v.inserted = 0
        v.preemptions += 1
        preempt_total += 1
        running.remove(v)
        waiting.insert(0, v)
        return v

    def try_admit():
        while waiting and len(running) < cfg.max_num_seqs:
            r = waiting[0]
            matched, pinned = cache.match_and_pin(r.hashes)
            reuse_tok = min(matched * bs, max(0, r.prompt_len - 1))
            need = bl(r.prompt_len) - matched
            if not reclaim(need):
                for h in pinned:
                    cache.unpin(h)
                if bl(r.prompt_len) > total and not running:
                    raise RuntimeError("pool too small for a single request")
                return
            r.pinned = list(pinned)
            r.alloc = need
            r.cached = reuse_tok
            r.prefilled = reuse_tok
            r.inserted = matched
            running.append(r)
            waiting.pop(0)

    while pending or waiting or running:
        while pending and pending[0].arrival <= t:
            waiting.append(pending.pop(0))
        try_admit()
        if not running:
            if pending:
                t = max(t, pending[0].arrival)
                continue
            if waiting:
                raise RuntimeError("stuck: waiting but nothing can be admitted")
            break

        budget = cfg.max_batched_tokens
        decoding = [r for r in running if r.prefilled >= r.prompt_len]
        n_dec = min(len(decoding), budget)
        dec_batch = decoding[:n_dec]
        budget -= n_dec
        kv_read = sum(r.prompt_len + r.generated for r in dec_batch)

        # lazy decode-block allocation, with eviction then preemption
        alive = []
        for r in dec_batch:
            new_total = r.prompt_len + r.generated + 1
            if bl(new_total) > bl(new_total - 1):
                if not reclaim(1):
                    v = preempt_victim(exclude=None)
                    if v is r:
                        continue        # self-preempted, skips this step
                    if v is None or not reclaim(1):
                        continue        # cannot allocate, seq stalls
                r.alloc += 1
            alive.append(r)
        dec_batch = alive
        n_dec = len(dec_batch)

        prefill_tok = 0
        for r in running:
            if budget <= 0:
                break
            if r.prefilled < r.prompt_len:
                chunk = min(budget, r.prompt_len - r.prefilled)
                r.prefilled += chunk
                prefill_tok += chunk
                kv_read += r.prefilled
                budget -= chunk
                # publish completed full blocks immediately (v0.2 fix 1)
                full_now = r.prefilled // bs
                while r.inserted < full_now:
                    h = r.hashes[r.inserted] if r.inserted < len(r.hashes) else None
                    if h is not None:
                        if cache.publish(h):
                            # ownership moves from request to shared cache
                            r.alloc = max(0, r.alloc - 1)
                            r.pinned.append(h)
                        elif cache.pin_existing(h):
                            r.alloc = max(0, r.alloc - 1)
                            r.pinned.append(h)
                    r.inserted += 1

        dt = perf.a + perf.b_p * prefill_tok + perf.b_d * n_dec \
             + perf.c_kv * kv_read / 1e6
        t += dt
        gpu_busy += dt
        steps += 1

        finished = []
        for r in dec_batch:
            if r.generated == 0 and r.ttft < 0:
                r.ttft = t - r.arrival
            r.generated += 1
            if r.generated >= r.output_len:
                r.finish = t
                finished.append(r)
        for r in finished:
            running.remove(r)
            release(r, keep_cache=True)
        try_admit()

    cache.tok_hits = sum(r.cached for r in reqs)
    prompt_tok = sum(r.prompt_len for r in reqs)
    return reqs, {
        "steps": steps, "gpu_busy_s": gpu_busy, "makespan_s": t,
        "tok_hit_rate": cache.tok_hits / prompt_tok if prompt_tok else 0.0,
        "blk_hit_rate": (cache.blk_hits / cache.blk_lookups)
                        if cache.blk_lookups else 0.0,
        "preemptions": preempt_total,
    }

def summarize(reqs, agg, drop_first=0):
    if drop_first:
        keep_ids = set(r.rid for r in sorted(reqs, key=lambda r: r.arrival)[drop_first:])
        reqs = [r for r in reqs if r.rid in keep_ids]
    ttfts = sorted(r.ttft for r in reqs)
    e2e = sorted(r.finish - r.arrival for r in reqs)
    out_tok = sum(r.output_len for r in reqs)
    def p(v, q): return v[min(len(v)-1, int(q*len(v)))]
    return {
        "requests": len(reqs),  # after drop_first
        "ttft_p50_s": round(p(ttfts, .5), 3), "ttft_p95_s": round(p(ttfts, .95), 3),
        "e2e_p50_s": round(p(e2e, .5), 3),   "e2e_p95_s": round(p(e2e, .95), 3),
        "throughput_tok_s": round(out_tok / agg["makespan_s"], 1),
        "makespan_s": round(agg["makespan_s"], 1),
        "gpu_busy_s": round(agg["gpu_busy_s"], 1),
        "gpu_s_per_1k_out_tok": round(1000 * agg["gpu_busy_s"] / out_tok, 3),
        "prefix_cache_hit_rate": round(agg["tok_hit_rate"], 3),
        "block_lookup_hit_rate": round(agg["blk_hit_rate"], 3),
        "preemptions": agg["preemptions"],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--perf", default=None)
    ap.add_argument("--num-blocks", type=int, default=8000)
    ap.add_argument("--block-size", type=int, default=16)
    ap.add_argument("--max-num-seqs", type=int, default=128)
    ap.add_argument("--max-batched-tokens", type=int, default=2048)
    ap.add_argument("--no-prefix-caching", action="store_true")
    ap.add_argument("--drop-first", type=int, default=0,
                    help="exclude first N arrivals from summary stats, "
                         "matching bench.py --drop-first (still simulated)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    trace = [json.loads(l) for l in open(a.trace)]
    perf = Perf.load(a.perf) if a.perf else Perf()
    cfg = Cfg(block_size=a.block_size, num_blocks=a.num_blocks,
              max_num_seqs=a.max_num_seqs,
              max_batched_tokens=a.max_batched_tokens,
              prefix_caching=not a.no_prefix_caching)
    reqs, agg = simulate(trace, cfg, perf)
    s = summarize(reqs, agg, drop_first=a.drop_first)
    s["config"] = {"num_blocks": cfg.num_blocks, "block_size": cfg.block_size,
                   "max_num_seqs": cfg.max_num_seqs,
                   "max_batched_tokens": cfg.max_batched_tokens,
                   "prefix_caching": cfg.prefix_caching}
    print(json.dumps(s, indent=2))
    if a.out:
        json.dump(s, open(a.out, "w"), indent=2)

if __name__ == "__main__":
    main()
