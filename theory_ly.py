from __future__ import annotations

from math import comb, exp, isfinite
from typing import Iterable

import numpy as np
from scipy.stats import poisson


def clamp01(x: float) -> float:
    if not isfinite(x):
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return float(x)


def combined_prob(n_less: int, n_more: int, p1_val: float, p3_val: float, threshold: int) -> float:
    prob = 0.0
    for i in range(n_less + 1):
        for j in range(n_more + 1):
            if i + j >= threshold:
                prob += (
                    comb(n_less, i) * (p1_val ** i) * ((1 - p1_val) ** (n_less - i))
                    * comb(n_more, j) * (p3_val ** j) * ((1 - p3_val) ** (n_more - j))
                )
    return 0.0 if not isfinite(prob) else float(prob)


def p_success_given_dtilde(g_h: int, t_rounds: int, q_a: float, alpha0: float, beta1: float) -> float:
    if not isfinite(g_h) or not isfinite(t_rounds) or t_rounds < 0:
        return 0.0
    if g_h <= 0:
        return 1.0

    mu_a = q_a * t_rounds

    js = np.arange(0, g_h, dtype=int)
    pmf = poisson.pmf(js, mu_a)

    k = g_h - js
    with np.errstate(over="ignore", invalid="ignore"):
        phi_val = ((beta1 / alpha0) ** (k - 1)) * ((1 - alpha0) / (1 - beta1))
    phi_val = np.minimum(phi_val, 1.0)

    term1 = float(np.sum(pmf * phi_val))
    tail = float(poisson.sf(g_h - 1, mu_a))

    return clamp01(term1 + tail)


def p_order(t_rounds: int, m: int, d: int, tilde_m: int, delta_rounds: int, q_h: float) -> float:
    tau = t_rounds - d * delta_rounds
    if tau <= 0:
        return 0.0

    k = int(tilde_m)
    f_g = q_h * float(poisson.pmf(d - 1, q_h * tau))
    f_upper = float(poisson.sf(d - 1, q_h * tau))

    coeff = comb(m, k - 1) * (m - k + 1)
    val = coeff * f_g * (f_upper ** (k - 1)) * (max(1.0 - f_upper, 0.0) ** (m - k))
    return 0.0 if not isfinite(val) else float(val)


def p1(d: int, t_rounds: int, q_a: float, delta_rounds: int, q_h: float, alpha0: float, beta1: float) -> float:
    tau = t_rounds - d * delta_rounds
    if tau <= 0:
        return 0.0

    mu = q_h * tau
    gs = np.arange(0, max(d, 1), dtype=int)
    pmf = poisson.pmf(gs, mu)
    pg = np.array([p_success_given_dtilde(int(g), t_rounds, q_a, alpha0, beta1) for g in gs], dtype=float)

    num = float(np.sum(pmf * pg))
    den = float(poisson.cdf(d - 1, mu))
    if den <= 0.0 or not isfinite(den):
        return 0.0
    return clamp01(num / den)


def p3(d: int, t_rounds: int, q_a: float, delta_rounds: int, q_h: float, alpha0: float, beta1: float) -> float:
    tau = t_rounds - d * delta_rounds
    if tau <= 0:
        return 0.0

    mu = q_h * tau
    g_max = int(poisson.ppf(1 - 1e-15, mu))
    if g_max < d:
        return 0.0

    gs = np.arange(d, g_max + 1, dtype=int)
    pmf = poisson.pmf(gs, mu)
    pg = np.array([p_success_given_dtilde(int(g), t_rounds, q_a, alpha0, beta1) for g in gs], dtype=float)

    num = float(np.sum(pmf * pg))
    den = float(poisson.sf(d - 1, mu))
    if den <= 0.0 or not isfinite(den):
        return 0.0
    return clamp01(num / den)


def overall_success(m: int, t_rounds: int, d: int, q_a: float, tilde_m: int, delta_rounds: int, q_h: float, alpha0: float, beta1: float) -> float:
    p1_val = clamp01(p1(d, t_rounds, q_a, delta_rounds, q_h, alpha0, beta1))
    p2_val = clamp01(p_success_given_dtilde(d, t_rounds, q_a, alpha0, beta1))
    p3_val = clamp01(p3(d, t_rounds, q_a, delta_rounds, q_h, alpha0, beta1))

    n_less = m - tilde_m
    n_more = tilde_m - 1
    t1 = tilde_m - 1
    t2 = tilde_m

    val = p2_val * combined_prob(n_less, n_more, p1_val, p3_val, t1) + (1 - p2_val) * combined_prob(
        n_less, n_more, p1_val, p3_val, t2
    )
    return 0.0 if not isfinite(val) else float(val)


def overall_success_total(
    m: int,
    d: int,
    lambda_placeholder: float,
    q_a: float,
    beta: float,
    tilde_m: int,
    t_max: int,
    eps: float,
    delta_rounds: int,
    q_h: float,
) -> float:
    del lambda_placeholder, beta

    beta_frac = q_a / (q_h + q_a)
    alpha0 = (1 - beta_frac) * exp(-beta_frac * (q_h + q_a) * delta_rounds)
    alpha1 = (1 - beta_frac) * beta_frac * (q_h + q_a) * delta_rounds * exp(-beta_frac * (q_h + q_a) * delta_rounds)
    beta1 = 1 - alpha0 - alpha1

    total_attack_prob = 0.0
    comp = 0.0
    cum = 0.0

    for t_rounds in range(d, int(t_max) + 1):
        p_t = p_order(t_rounds, m, d, tilde_m, delta_rounds, q_h)
        p_atk = overall_success(m, t_rounds, d, q_a, tilde_m, delta_rounds, q_h, alpha0, beta1)

        if not isfinite(p_t) or not isfinite(p_atk):
            p_t = 0.0
            p_atk = 0.0

        incr = p_t * p_atk
        y = incr - comp
        t_val = total_attack_prob + y
        comp = (t_val - total_attack_prob) - y
        total_attack_prob = t_val

        cum += p_t
        if cum > 1 - eps and t_rounds > d * delta_rounds:
            break

    return clamp01(total_attack_prob)


def theory_ly_single_alpha(
    alpha: float,
    n_confirm: int,
    max_delay_rounds: int,
    avg_block_interval_rounds: float,
    m: int = 1,
    tilde_m: int = 1,
    t_max: int | None = None,
    eps: float = 1e-6,
) -> float:
    alpha = float(alpha)
    if alpha <= 0:
        return 0.0
    if alpha >= 1:
        return 1.0

    total_rate = 1.0 / float(avg_block_interval_rounds)
    q_h = (1.0 - alpha) * total_rate
    q_a = alpha * total_rate

    if t_max is None:
        t_max = 1e10

    beta = q_a / q_h
    return overall_success_total(
        int(m),
        int(n_confirm),
        q_h,
        q_a,
        beta,
        int(tilde_m),
        int(t_max),
        float(eps),
        int(max_delay_rounds),
        q_h,
    )


def theory_ly_curve(
    alphas: Iterable[float],
    n_confirm: int,
    max_delay_rounds: int,
    avg_block_interval_rounds: float,
    m: int = 1,
    tilde_m: int = 1,
    eps: float = 1e-8,
) -> np.ndarray:
    vals = [
        theory_ly_single_alpha(
            alpha=float(alpha),
            n_confirm=int(n_confirm),
            max_delay_rounds=int(max_delay_rounds),
            avg_block_interval_rounds=float(avg_block_interval_rounds),
            m=int(m),
            tilde_m=int(tilde_m),
            eps=float(eps),
        )
        for alpha in alphas
    ]
    return np.array(vals, dtype=float)
