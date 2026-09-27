from __future__ import annotations

from math import comb, exp, isfinite, lgamma, log, sqrt
from typing import Iterable

import numpy as np


def _poisson_pmf_scalar(k: int, mu: float) -> float:
    if k < 0:
        return 0.0
    if not isfinite(mu) or mu < 0.0:
        return 0.0
    if mu == 0.0:
        return 1.0 if k == 0 else 0.0
    return exp(-mu + k * log(mu) - lgamma(k + 1))


def _poisson_pmf_array(ks: np.ndarray, mu: float) -> np.ndarray:
    return np.array([_poisson_pmf_scalar(int(k), mu) for k in ks], dtype=float)


def _poisson_cdf(k: int, mu: float) -> float:
    if k < 0:
        return 0.0
    if mu == 0.0:
        return 1.0
    pmf = _poisson_pmf_scalar(0, mu)
    s = pmf
    for i in range(1, k + 1):
        pmf *= mu / i
        s += pmf
    return min(max(s, 0.0), 1.0)


def _poisson_sf(k: int, mu: float) -> float:
    return min(max(1.0 - _poisson_cdf(k, mu), 0.0), 1.0)


def _poisson_ppf(p: float, mu: float) -> int:
    p = min(max(float(p), 0.0), 1.0)
    if p <= 0.0:
        return 0
    if p >= 1.0:
        return int(max(1.0, mu + 30.0 * sqrt(max(mu, 1.0)) + 200.0))
    if mu == 0.0:
        return 0
    k = 0
    pmf = _poisson_pmf_scalar(0, mu)
    cdf = pmf
    cap = int(max(100.0, mu + 20.0 * sqrt(max(mu, 1.0)) + 1000.0))
    while cdf < p and k < cap:
        k += 1
        pmf *= mu / k
        cdf += pmf
    return k


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


def compute_e_pmf_series(a_rate: float, h_rate: float, delta_rounds: int, n_max: int) -> np.ndarray:
    c = h_rate - a_rate - h_rate * a_rate * delta_rounds

    n_coeff = np.zeros(n_max + 1, dtype=float)
    n_coeff[0] = c
    if n_max >= 1:
        n_coeff[1] = -c

    a_d = a_rate * delta_rounds
    exp_a_d = exp(a_d)
    eexp = np.zeros(n_max + 1, dtype=float)
    eexp[0] = exp_a_d
    for mm in range(1, n_max + 1):
        eexp[mm] = eexp[mm - 1] * ((-a_d) / mm)

    q = np.zeros(n_max + 1, dtype=float)
    for nn in range(n_max + 1):
        term1 = (h_rate + a_rate) * eexp[nn]
        term2 = (-a_rate) * eexp[nn - 1] if nn >= 1 else 0.0
        q[nn] = term1 + term2

    t_coeff = np.zeros(n_max + 1, dtype=float)
    if n_max >= 1:
        t_coeff[1:] = q[:-1]

    d_coeff = np.zeros(n_max + 1, dtype=float)
    d_coeff[0] = h_rate
    d_coeff[1:] = -t_coeff[1:]

    e = np.zeros(n_max + 1, dtype=float)
    d0 = d_coeff[0]
    if d0 == 0:
        return e

    e[0] = n_coeff[0] / d0
    for nn in range(1, n_max + 1):
        acc = 0.0
        for jj in range(1, nn + 1):
            acc += d_coeff[jj] * e[nn - jj]
        e[nn] = (n_coeff[nn] - acc) / d0
    return e


def compute_lemma4_tail(a_rate: float, h_rate: float, delta_rounds: int, n_max: int = 500) -> np.ndarray:
    # 1. 计算有效算力优势常数 C
    C = h_rate - a_rate - h_rate * a_rate * delta_rounds
    
    # 2. 检查边界条件：如果 C <= 0，说明攻击者占绝对优势，追平概率恒为 1
    if C <= 0:
        tail = np.ones(n_max + 2) # 无论落后多少，追赶成功的概率都是1
        return tail
    
    # 3. 正常情况 (C > 0)，走原本的 PGF 级数除法逻辑
    e = compute_e_pmf_series(a_rate, h_rate, delta_rounds, n_max)
    tail = np.zeros(n_max + 2, dtype=float)
    for i in range(n_max, -1, -1):
        tail[i] = tail[i + 1] + e[i]
    tail = np.clip(tail, 0.0, 1.0)
    return tail


def p_success_given_dtilde(g_h: int, t_rounds: int, q_a: float, tail_prob: np.ndarray) -> float:
    if not isfinite(g_h) or not isfinite(t_rounds) or t_rounds < 0:
        return 0.0
    if g_h <= 0:
        return 1.0

    mu_a = q_a * t_rounds

    js = np.arange(0, g_h, dtype=int)
    pmf = _poisson_pmf_array(js, mu_a)

    k = g_h - js
    phi_val = np.zeros_like(k, dtype=float)
    for idx, kk in enumerate(k):
        if kk <= 0:
            phi_val[idx] = 1.0
        elif kk < len(tail_prob):
            phi_val[idx] = float(tail_prob[kk])
        else:
            phi_val[idx] = 0.0

    term1 = float(np.sum(pmf * phi_val))
    tail = float(_poisson_sf(g_h - 1, mu_a))

    return clamp01(term1 + tail)


def p_order(t_rounds: int, m: int, d: int, tilde_m: int, delta_rounds: int, q_h: float) -> float:
    tau = t_rounds - d * delta_rounds
    if tau <= 0:
        return 0.0

    k = int(tilde_m)
    f_g = q_h * float(_poisson_pmf_scalar(d - 1, q_h * tau))
    f_upper = float(_poisson_sf(d - 1, q_h * tau))

    coeff = comb(m, k - 1) * (m - k + 1)
    val = coeff * f_g * (f_upper ** (k - 1)) * (max(1.0 - f_upper, 0.0) ** (m - k))
    return 0.0 if not isfinite(val) else float(val)


def p1(d: int, t_rounds: int, q_a: float, delta_rounds: int, q_h: float, tail_prob: np.ndarray) -> float:
    tau = t_rounds - d * delta_rounds
    if tau <= 0:
        return 0.0

    mu = q_h * tau
    gs = np.arange(0, max(d, 1), dtype=int)
    pmf = _poisson_pmf_array(gs, mu)
    pg = np.array([p_success_given_dtilde(int(g), t_rounds, q_a, tail_prob) for g in gs], dtype=float)

    num = float(np.sum(pmf * pg))
    den = float(_poisson_cdf(d - 1, mu))
    if den <= 0.0 or not isfinite(den):
        return 0.0
    return clamp01(num / den)


def p3(d: int, t_rounds: int, q_a: float, delta_rounds: int, q_h: float, tail_prob: np.ndarray) -> float:
    tau = t_rounds - d * delta_rounds
    if tau <= 0:
        return 0.0

    mu = q_h * tau
    g_max = int(_poisson_ppf(1 - 1e-15, mu))
    if g_max < d:
        return 0.0

    gs = np.arange(d, g_max + 1, dtype=int)
    pmf = _poisson_pmf_array(gs, mu)
    pg = np.array([p_success_given_dtilde(int(g), t_rounds, q_a, tail_prob) for g in gs], dtype=float)

    num = float(np.sum(pmf * pg))
    den = float(_poisson_sf(d - 1, mu))
    if den <= 0.0 or not isfinite(den):
        return 0.0
    return clamp01(num / den)


def overall_success(m: int, t_rounds: int, d: int, q_a: float, tilde_m: int, delta_rounds: int, q_h: float, tail_prob: np.ndarray) -> float:
    p1_val = clamp01(p1(d, t_rounds, q_a, delta_rounds, q_h, tail_prob))
    p2_val = clamp01(p_success_given_dtilde(d, t_rounds, q_a, tail_prob))
    p3_val = clamp01(p3(d, t_rounds, q_a, delta_rounds, q_h, tail_prob))

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

    max_k = 500
    tail_prob = compute_lemma4_tail(q_a, q_h, delta_rounds, max_k)

    total_attack_prob = 0.0
    comp = 0.0
    cum = 0.0

    for t_rounds in range(d, int(t_max) + 1):
        p_t = p_order(t_rounds, m, d, tilde_m, delta_rounds, q_h)
        p_atk = overall_success(m, t_rounds, d, q_a, tilde_m, delta_rounds, q_h, tail_prob)

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
