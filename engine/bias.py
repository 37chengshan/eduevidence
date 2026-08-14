"""engine/bias.py - publication-bias diagnostics for v4 meta-analysis.

    egger_regression  Egger (1997) funnel-asymmetry test: regress the
                      standard normal deviate SND = d/se on precision
                      prec = 1/se; the intercept estimates small-study bias
                      (Borenstein 2009, ch. 41, eq. 41.1-41.3).
    fail_safe_n       Rosenthal (1979) fail-safe N: how many null-effect
                      studies would push the combined z below significance
                      (Borenstein 2009, ch. 42):  N_fs = (ΣZ)² / 2.706 − k,
                      with 2.706 = 1.645² (one-tailed z at α = 0.05).

Pure stdlib (math only). Egger's intercept is tested with a two-tailed
Student t (df = k − 2); the t CDF uses the regularized incomplete beta
function (Numerical Recipes betacf) so no scipy is required.
"""
from __future__ import annotations

import math
from typing import Any

_Z_CRIT_ONE_TAIL = 1.6448536269514722  # z at α = 0.05, one-tailed
_Z_CRIT_SQUARED = _Z_CRIT_ONE_TAIL ** 2  # 2.7055434540954042


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _usable(rows: list[dict]) -> list[dict]:
    import math as _m
    return [r for r in rows or []
            if _is_number(r.get("d")) and _is_number(r.get("se")) and r["se"] > 0
            and _m.isfinite(float(r["d"])) and _m.isfinite(float(r["se"]))]


# ---------------------------------------------------------------------------
# Student-t survival via regularized incomplete beta (stdlib only)
# ---------------------------------------------------------------------------

def _betacf(a: float, b: float, x: float, max_iter: int = 200,
            eps: float = 3.0e-12) -> float:
    """Continued-fraction evaluation of the incomplete beta function."""
    tiny = 1.0e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _t_two_tailed_p(t: float, df: int) -> float:
    """Two-tailed p for a Student t with ``df`` degrees of freedom.

    Uses the identity P(T > t) = 0.5 · I_{df/(df+t²)}(df/2, 1/2).
    """
    if df <= 0:
        return 1.0
    if not math.isfinite(t):
        return 0.0
    x = df / (df + t * t)
    return 2.0 * 0.5 * _betai(df / 2.0, 0.5, x)


# ---------------------------------------------------------------------------
# Egger's regression test
# ---------------------------------------------------------------------------

def egger_regression(rows: list[dict]) -> dict:
    """Egger (1997) funnel-asymmetry test via OLS of SND on precision.

    Symmetric data (effect independent of precision) yields intercept ≈ 0;
    a nonzero intercept signals small-study bias. Significance: two-tailed
    t-test on the intercept, df = k − 2. With k < 3, or constant precision
    across studies, the test is not applicable. A perfect fit (RSS = 0) is
    treated as no detectable bias (t = 0, p = 1).
    """
    usable = _usable(rows)
    k = len(usable)
    if k < 3:
        return {"applicable": False, "reason": "need >= 3 studies",
                "k": k}
    x = [1.0 / float(r["se"]) for r in usable]   # precision
    y = [float(r["d"]) / float(r["se"]) for r in usable]  # SND
    x_bar = sum(x) / k
    y_bar = sum(y) / k
    sxx = sum((xi - x_bar) ** 2 for xi in x)
    if sxx == 0:
        return {"applicable": False, "reason": "constant precision",
                "k": k}
    sxy = sum((xi - x_bar) * (yi - y_bar) for xi, yi in zip(x, y))
    slope = sxy / sxx
    intercept = y_bar - slope * x_bar
    residuals = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]
    rss = sum(rr * rr for rr in residuals)
    mse = rss / (k - 2) if k > 2 else 0.0
    se_intercept = math.sqrt(mse * (1.0 / k + x_bar * x_bar / sxx))
    if se_intercept == 0 or not math.isfinite(se_intercept):  # perfect fit
        t, p = 0.0, 1.0
    else:
        t = intercept / se_intercept
        p = _t_two_tailed_p(t, k - 2)
    return {
        "applicable": True,
        "k": k,
        "intercept": intercept,
        "se_intercept": se_intercept,
        "slope": slope,
        "t": t,
        "p_value": p,
        "significant": p < 0.05,
        "bias_detected": p < 0.05,
    }


# ---------------------------------------------------------------------------
# Rosenthal's fail-safe N
# ---------------------------------------------------------------------------

def fail_safe_n(rows: list[dict]) -> dict:
    """Rosenthal (1979) fail-safe N: null studies needed to nullify the result.

    N_fs = (ΣZ)² / 2.706 − k with Z = d/se (floored at 0). ``tolerates_5``
    reports whether the finding survives the addition of 5 null studies
    (N_fs ≥ 5) — the task's minimum robustness bar.
    """
    usable = _usable(rows)
    k = len(usable)
    zs = [float(r["d"]) / float(r["se"]) for r in usable]
    sum_z = sum(zs)
    n_fail_safe = max(0.0, (sum_z * sum_z) / _Z_CRIT_SQUARED - k)
    return {
        "method": "rosenthal",
        "k": k,
        "sum_z": sum_z,
        "z_crit": _Z_CRIT_ONE_TAIL,
        "z_crit_squared": _Z_CRIT_SQUARED,
        "n_fail_safe": n_fail_safe,
        "tolerates_5": n_fail_safe >= 5.0,
    }
