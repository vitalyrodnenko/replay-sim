"""Generate an agentic-style request trace.

Structure mimics agent workloads: S sessions, each session shares a long
system/tool prompt (prefix reuse target) and grows its history across turns.
Prompts are deterministic token-id sequences so the same trace replays
identically in the simulator and against a real vLLM server.

Output: JSONL, one request per line:
  {"req_id", "session", "turn", "arrival_s", "prompt_len", "output_len",
   "prefix_key": [block-content hashes precomputed at block_size granularity]}

For the real vLLM run we also emit prompt text built from a fixed vocabulary
(one word per token, approximately) so tokenized lengths are stable.
"""
import argparse, hashlib, json, random

# Prefix caching operates on exact 16-token blocks, so per-prompt drift would
# misalign the simulator's block hashes against the engine's.
# History: the shipped "tok0".."tok511" vocabulary tokenized at 3.78 tok/word
# on Qwen3.8 (digits split individually); a vocabulary derived for Qwen3.8
# then gave 1.346 tok/word here. The vocabulary must be derived from the
# tokenizer of the model actually being benchmarked.
VOCAB = [
    'abbrev', 'abras', 'acct', 'acre', 'actors', 'adding', 'adjust',
    'advert', 'agenda', 'agree', 'airy', 'albums', 'alien', 'allen',
    'allows', 'already', 'altura', 'ammo', 'ance', 'andra', 'angle',
    'anime', 'anon', 'anth', 'apache', 'appoint', 'arch', 'argent', 'arms',
    'arter', 'ascii', 'asses', 'aster', 'athlete', 'attack', 'auction',
    'authors', 'avatar', 'await', 'azure', 'badge', 'bang', 'bare', 'basic',
    'bcrypt', 'because', 'belief', 'bere', 'best', 'bigint', 'binding',
    'bitcoin', 'blas', 'blocks', 'boat', 'bones', 'boom', 'boss', 'bour',
    'brain', 'breaker', 'bright', 'browser', 'buff', 'builtin', 'burn',
    'buyer', 'caffe', 'callee', 'camp', 'capital', 'cards', 'cart',
    'castle', 'cdecl', 'centers', 'chain', 'changer', 'charg', 'chart',
    'chef', 'childs', 'choose', 'chrono', 'circle', 'clamp', 'clave',
    'cliente', 'cloak', 'cloth', 'coal', 'codigo', 'cola', 'color',
    'combat', 'coming', 'commons', 'compat', 'concat', 'config', 'const',
    'conte', 'contrib', 'cookies', 'cord', 'correo', 'counter', 'court',
    'crap', 'created', 'crew', 'crypt', 'cuda', 'cursor', 'cycles',
    'danger', 'date', 'dbname', 'debit', 'decode', 'defense', 'delay',
    'dense', 'deposit', 'derived', 'dest', 'device', 'dice', 'digits',
    'disable', 'display', 'dock', 'dojo', 'doors', 'draw', 'drivers',
    'dummy', 'earning', 'edad', 'editor', 'elapsed', 'elif', 'elles',
    'emacs', 'emoji', 'enable', 'ended', 'energy', 'entered', 'entry',
    'epochs', 'erot', 'errs', 'essay', 'esteem', 'europ', 'evil', 'exec',
    'expects', 'explain', 'extend', 'extras', 'fact', 'failed', 'fall',
    'fast', 'feas', 'fell', 'fiber', 'figures', 'filme', 'finally',
    'finite', 'fits', 'flat', 'floor', 'flux', 'folders', 'footer', 'fore',
    'fork', 'forming', 'forward', 'fram', 'frei', 'front', 'fund', 'game',
    'gear', 'generic', 'geom', 'getter', 'gist', 'globals', 'gone', 'grad',
    'grams', 'grass', 'green', 'ground', 'grund', 'guid', 'habit', 'hand',
    'hard', 'haul', 'header', 'heard', 'heels', 'helpers', 'higher', 'hist',
    'holding', 'hone', 'host', 'hover', 'human', 'icing', 'ident', 'igen',
    'image', 'immune', 'incess', 'indent', 'inds', 'infos', 'inline',
    'inside', 'inte', 'inters', 'intval', 'ioctl', 'isset', 'items', 'jest',
    'jong', 'judge', 'jylland', 'keyword', 'kits', 'kube', 'lake', 'langs',
    'lasting', 'launch', 'lazy', 'league', 'leased', 'ledger', 'lesen',
    'letters', 'liable', 'lien', 'ligne', 'limits', 'linger', 'lion',
    'listen', 'living', 'loads', 'located', 'logfile', 'logout', 'loops',
    'loss', 'luck', 'macros', 'maint', 'mall', 'mans', 'marca', 'market',
    'mart', 'masters', 'matrix', 'means', 'meet', 'memo', 'mente', 'merged',
    'meth', 'micro', 'million', 'minimum', 'misc', 'mkdir', 'models',
    'modulo', 'monkey', 'more', 'motor', 'moves', 'mult', 'mutex', 'names',
    'nearest', 'nelle', 'never', 'night', 'noise', 'normal', 'noticed',
    'numbers', 'ober', 'observe', 'office', 'olds', 'onde', 'opcion',
    'oper', 'opts', 'orden', 'organ', 'other', 'outer', 'oval', 'owing',
    'paced', 'pager', 'paired', 'pants', 'pard', 'parm', 'partial', 'past',
    'pause', 'peace', 'peng', 'perform', 'pers', 'pets', 'photo', 'pickle',
    'pile', 'pipes', 'placer', 'planet', 'played', 'plot', 'point', 'poll',
    'popular', 'portion', 'poss', 'power', 'pred', 'premium', 'press',
    'prices', 'printer', 'private', 'produ', 'profit', 'promo', 'prot',
    'prox', 'pull', 'puts', 'quam', 'quer', 'queues', 'quiz', 'race',
    'raid', 'raising', 'ranking', 'rather', 'react', 'really', 'recent',
    'recover', 'redo', 'regex', 'reject', 'remarks', 'renders', 'report',
    'reserve', 'respond', 'resume', 'reve', 'ribbon', 'ridge', 'riot',
    'road', 'roles', 'roman', 'rough', 'rows', 'rupt', 'sale', 'sandbox',
    'scala', 'scape', 'scheme', 'score', 'scroll', 'secs', 'seek', 'sell',
    'sending', 'serie', 'sess', 'setw', 'shaft', 'sharing', 'shield',
    'shop', 'shown', 'signal', 'similar', 'site', 'skins', 'slice', 'slow',
    'snake', 'sockets', 'some', 'sort', 'south', 'spark', 'spect', 'spin',
    'sponsor', 'sprintf', 'ssize', 'stairs', 'star', 'stat', 'stay',
    'stellar', 'sticky', 'stones', 'stored', 'strap', 'stress', 'strip',
    'strstr', 'stuff', 'submit', 'succ', 'suma', 'surf', 'swift', 'syntax',
    'tabs', 'taking', 'task', 'teen', 'tenant', 'terr', 'tester', 'than',
    'then', 'thesis', 'this', 'thresh', 'thumbs', 'ties', 'timing', 'titre',
    'token', 'toolbar', 'tors', 'town', 'tractor', 'trainer', 'trash',
    'trie', 'trust', 'turtle', 'typedef', 'ubic', 'ulus', 'undo', 'union',
    'unless', 'unset', 'updates', 'urban', 'userid', 'usual', 'utter',
    'value', 'vars', 'vendors', 'venues', 'vers', 'vest', 'view', 'violent',
    'visited', 'voir', 'wagon', 'wallet', 'ware', 'watch', 'wealth', 'weed',
    'weit', 'wget', 'white', 'wife', 'wine', 'wish', 'wolf', 'worked',
    'worthy', 'writers', 'xmin', 'yards', 'ymax',
]
# NOTE: the v0.8-r2 archive shipped VOCAB = [f"tok{i}"...] again,
# the pristine pre-fix vocabulary. Restored from the installed file:
# see commits f3b598b and 80feb97. The --bursty logic below is the
# archive's, unmodified.

def words(rng, n):
    return [VOCAB[rng.randrange(len(VOCAB))] for _ in range(n)]

def gen(seed, sessions, turns, sys_len, turn_user, turn_growth, out_mean, rate,
        bursty=False, burst_min=4, burst_max=6):
    rng = random.Random(seed)
    reqs = []
    t = 0.0
    # shared corporate system prompt across ALL sessions (strong reuse signal)
    shared_sys = words(rng, sys_len)
    per_session = {}
    for s in range(sessions):
        # per-session tool preamble, reused across that session's turns
        per_session[s] = words(rng, sys_len // 2)
    # interleave turns across sessions with Poisson arrivals
    order = [(s, k) for s in range(sessions) for k in range(turns)]
    rng.shuffle(order)
    order.sort(key=lambda x: x[1])  # turns roughly in order, sessions interleaved
    histories = {s: [] for s in range(sessions)}
    rid = 0
    # bursty mode: requests arrive in Poisson-spaced bursts of burst_min..max,
    # near-simultaneous within a burst. Same request count and roughly the
    # same span as the smooth trace at the same rate.
    burst_left = 0
    for (s, k) in order:
        if bursty:
            if burst_left <= 0:
                burst_left = rng.randint(burst_min, burst_max)
                t += rng.expovariate(rate / ((burst_min + burst_max) / 2))
            else:
                t += rng.uniform(0.01, 0.05)
            burst_left -= 1
        else:
            t += rng.expovariate(rate)
        user = words(rng, turn_user + k * turn_growth)
        prompt_words = shared_sys + per_session[s] + histories[s] + user
        out_len = max(8, int(rng.gauss(out_mean, out_mean * 0.3)))
        reqs.append({
            "req_id": rid, "session": s, "turn": k, "arrival_s": round(t, 3),
            "prompt": " ".join(prompt_words),
            "prompt_len": len(prompt_words),
            "output_len": out_len,
        })
        # assistant reply enters history as synthetic words (deterministic)
        histories[s] = histories[s] + user + words(rng, out_len)
        rid += 1
    return reqs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="trace.jsonl")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--sessions", type=int, default=24)
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--sys-len", type=int, default=1200)
    ap.add_argument("--turn-user", type=int, default=120)
    ap.add_argument("--turn-growth", type=int, default=20)
    ap.add_argument("--out-mean", type=int, default=180)
    ap.add_argument("--rate", type=float, default=1.2, help="arrivals per second")
    ap.add_argument("--bursty", action="store_true",
                    help="Poisson-spaced bursts of 4-6 near-simultaneous arrivals")
    a = ap.parse_args()
    reqs = gen(a.seed, a.sessions, a.turns, a.sys_len, a.turn_user,
               a.turn_growth, a.out_mean, a.rate, bursty=a.bursty)
    with open(a.out, "w") as f:
        for r in reqs:
            f.write(json.dumps(r) + "\n")
    tot = sum(r["prompt_len"] for r in reqs)
    print(f"wrote {len(reqs)} requests, {tot} prompt tokens (approx), "
          f"span {reqs[-1]['arrival_s']:.0f}s -> {a.out}")

if __name__ == "__main__":
    main()
