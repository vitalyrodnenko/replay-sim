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

# 512 words that encode to exactly one token each under the Qwen3.8
# tokenizer, both mid-string and at start-of-string, so prompt_len
# (words) equals the token count the engine actually sees. The list is
# frozen inline so workload.py stays pure-stdlib and runs on any CPU box.
# (The previous "tok0".."tok511" vocabulary tokenized at 3.78 tok/word,
# which overflowed --max-model-len 8192 on 167 of 192 requests.)
VOCAB = [
    "aaa", "aan", "aba", "abad", "abajo", "abat", "abb", "abbr", "abbrev",
    "abc", "abd", "aber", "abi", "abil", "abit", "abl", "able", "abol",
    "abord", "abort", "about", "above", "abr", "abra", "abras", "abs",
    "abu", "abus", "abwe", "aby", "acad", "acar", "acara", "acc", "accel",
    "accent", "accep", "accept", "access", "accia", "accom", "accomp",
    "accord", "accro", "acct", "accum", "accur", "ace", "acer", "acet",
    "ach", "acha", "achat", "ache", "achie", "acho", "acht", "achten",
    "achter", "aci", "acid", "acier", "ack", "acl", "acol", "acom",
    "acons", "acos", "acqu", "acqua", "acquis", "acr", "acre", "act",
    "acte", "acted", "acteur", "actie", "acting", "action", "activ",
    "active", "activo", "acto", "actor", "actors", "acts", "actu",
    "actual", "acu", "acus", "acute", "ada", "adalah", "adam", "adapt",
    "adat", "aday", "adb", "adc", "add", "added", "adding", "addir",
    "addon", "addons", "addr", "adds", "ade", "adel", "adem", "aden",
    "ader", "ades", "adet", "adh", "adi", "adj", "adjust", "adm", "admin",
    "admins", "ado", "adop", "adopt", "ador", "adore", "adr", "adres",
    "adress", "ads", "adult", "adv", "advert", "aes", "aff", "affer",
    "afh", "afir", "afs", "aft", "after", "aga", "again", "agak", "agama",
    "agar", "age", "aged", "agen", "agence", "agency", "agenda", "agent",
    "agents", "ages", "agg", "aggi", "aging", "agir", "agit", "agli",
    "ago", "agon", "agr", "agre", "agree", "agric", "agro", "agu", "agua",
    "agus", "ahead", "aid", "aide", "aider", "aik", "ail", "aim", "aime",
    "aimer", "aims", "ain", "aina", "air", "aire", "aired", "airs",
    "airy", "ais", "ait", "aiuto", "aix", "aja", "ajan", "ajang", "ajar",
    "ajaran", "ajax", "ajo", "aka", "akan", "akar", "akhir", "aki",
    "akin", "ako", "aks", "akses", "aksi", "akt", "aktif", "aktiv",
    "aktor", "aktu", "aku", "ala", "alak", "alam", "alamat", "alami",
    "alan", "alap", "alarm", "alas", "alat", "alb", "album", "albums",
    "alc", "alcool", "ald", "alde", "ale", "alem", "alent", "alert",
    "alerts", "ales", "alex", "alf", "alg", "algo", "ali", "alian",
    "alias", "alice", "alien", "align", "aline", "alist", "alive", "alk",
    "all", "alla", "allar", "alle", "allele", "allen", "aller", "alles",
    "alley", "alli", "allo", "alloc", "allow", "allows", "ally", "alm",
    "alma", "almost", "alo", "aload", "alone", "along", "alp", "alph",
    "alpha", "als", "also", "alt", "alta", "altar", "alte", "alten",
    "alter", "altern", "alti", "alto", "altra", "altro", "altura", "alue",
    "alum", "always", "alz", "ama", "amal", "aman", "amar", "amat",
    "amaz", "amazon", "amb", "amber", "ambi", "ambil", "ambito", "ambul",
    "amd", "ame", "amel", "amen", "amer", "americ", "amet", "ami", "amic",
    "amico", "amid", "amin", "amis", "amm", "ammo", "amo", "among",
    "amor", "amore", "amount", "amour", "amp", "ampi", "ampia", "ample",
    "amps", "amt", "amus", "amy", "ana", "anak", "anal", "analy",
    "analys", "anat", "anc", "ancam", "ance", "anch", "anche", "anchor",
    "anci", "ancien", "and", "anda", "andar", "anden", "ander", "anders",
    "andet", "andra", "andre", "aner", "anf", "ang", "ange", "angeb",
    "angel", "angen", "anger", "anges", "angg", "angi", "angk", "angka",
    "angkat", "angle", "angled", "angles", "angolo", "anh", "ani", "anim",
    "anima", "animal", "anime", "ank", "ann", "anne", "annen", "anni",
    "anno", "annon", "annot", "annual", "anny", "ano", "anom", "anon",
    "anos", "ans", "ansch", "ansi", "answer", "ant", "antal", "antar",
    "antara", "ante", "anter", "antes", "anth", "anti", "antic", "antica",
    "antics", "antik", "antis", "antlr", "ants", "anus", "any", "anya",
    "anyag", "anz", "anzi", "aos", "apa", "apache", "apar", "ape", "apel",
    "aper", "aperto", "aph", "api", "apie", "apis", "apk", "apl", "apo",
    "aporte", "apos", "app", "appar", "appare", "appe", "appear", "appel",
    "append", "appl", "apple", "applic", "apply", "appr", "appro",
    "approx", "apps", "apr", "apres", "apro", "aps", "apt", "aqu", "aque",
    "ara", "arah", "arahan", "aran", "aras", "aray", "arb", "arbe",
    "arbeit", "arbet", "arbre", "arc", "arch", "archit", "arco", "ard",
    "are", "area", "areas", "aren", "arena", "arg", "argc", "argent",
    "args", "argv", "aria", "arity", "ark", "arm", "arma", "arme",
    "armed", "armi", "armor", "arms", "around", "arp", "arqu", "arque",
    "arr", "arra", "array", "arrays", "arre", "arrive", "arrivo", "arro",
]

def words(rng, n):
    return [VOCAB[rng.randrange(len(VOCAB))] for _ in range(n)]

def gen(seed, sessions, turns, sys_len, turn_user, turn_growth, out_mean, rate):
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
    for (s, k) in order:
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
    a = ap.parse_args()
    reqs = gen(a.seed, a.sessions, a.turns, a.sys_len, a.turn_user,
               a.turn_growth, a.out_mean, a.rate)
    with open(a.out, "w") as f:
        for r in reqs:
            f.write(json.dumps(r) + "\n")
    tot = sum(r["prompt_len"] for r in reqs)
    print(f"wrote {len(reqs)} requests, {tot} prompt tokens (approx), "
          f"span {reqs[-1]['arrival_s']:.0f}s -> {a.out}")

if __name__ == "__main__":
    main()
