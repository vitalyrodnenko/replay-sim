"""Statistics helpers for the noise analysis: no scipy on this box.

Everything here is standard and self-contained so the noise report does not
depend on a library that is not installed in the venv.
"""
import math, random

# ---- Student-t quantile via the regularized incomplete beta -----------------

def _betacf(a, b, x, itmax=200, eps=3e-16):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta) * _betacf(b, a, 1.0 - x) / b


def t_cdf(t, df):
    x = df / (df + t * t)
    p = 0.5 * betai(df / 2.0, 0.5, x)
    return 1.0 - p if t > 0 else p


def t_ppf(p, df):
    """Inverse Student-t CDF by bisection. Accurate to ~1e-10."""
    lo, hi = -1e3, 1e3
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ---- descriptive ------------------------------------------------------------

def mean(v):
    return sum(v) / len(v)


def stdev(v):
    """Sample standard deviation, ddof=1."""
    if len(v) < 2:
        return float("nan")
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def bench_percentile(sorted_vals, q):
    """EXACTLY bench.py's and simulator.py's estimator, so every number in the
    report is about the same statistic the published series reports."""
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


# ---- Spearman with a permutation p-value ------------------------------------

def _rank(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _pearson(x, y):
    mx, my = mean(x), mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    return num / (dx * dy) if dx and dy else float("nan")


def spearman(x, y, n_perm=10000, seed=12345):
    """Returns (rho, two-sided permutation p-value)."""
    rx, ry = _rank(x), _rank(y)
    rho = _pearson(rx, ry)
    if math.isnan(rho):
        return rho, float("nan")
    rng = random.Random(seed)
    shuf = list(ry)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(shuf)
        if abs(_pearson(rx, shuf)) >= abs(rho) - 1e-12:
            hits += 1
    return rho, (hits + 1) / (n_perm + 1)


def repeats_needed(m, s, target, max_n=1000):
    """Smallest n>=2 with t(.975,n-1)*s/sqrt(n) <= target*m. None if > max_n."""
    if m <= 0 or s <= 0:
        return 2
    for n in range(2, max_n + 1):
        if t_ppf(0.975, n - 1) * s / math.sqrt(n) <= target * m:
            return n
    return None


def repeats_needed_z(m, s, target, z=1.9599639845, max_n=100000):
    if m <= 0 or s <= 0:
        return 2
    n = math.ceil((z * s / (target * m)) ** 2)
    return max(2, int(n))
