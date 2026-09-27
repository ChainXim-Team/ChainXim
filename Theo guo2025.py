import numpy as np
from scipy import special
from scipy.integrate import quad
import matplotlib.pyplot as plt


def cg_vs_du_bounds_beta_axis(Block_time, Delta, N, Alpha_list, verbose=True):
    """x-axis: adversary fraction beta, y-axis: safety violation probability (log scale)"""
    # ---------------- fixed parameters ----------------
    lambda_rate = 1.0 / Block_time
    k = N  # confirmation depth

    # CG truncation
    eps_trunc = 1e-20

    UB_CG = np.full(len(Alpha_list), np.nan)
    LB_CG = np.full(len(Alpha_list), np.nan)

    for idx, beta in enumerate(Alpha_list):
        alpha = 1 - beta

        a = beta * lambda_rate    # adversary mining rate
        h = alpha * lambda_rate   # honest mining rate

        # ---------------- Cao & Guo (Thm5/6) ----------------
        t_max = tmax_by_erlang_mass(k, h, Delta, eps_trunc)

        # e(0..k) (same PGF expansion)
        e_full = compute_e_pmf_series_E_over_D(a, h, Delta, k)
        e = e_full[:k+1]

        # Thm5: J(m), m=0..k-1, PoissCDF(m; a*(t + 3Δ))
        J = np.zeros(k)
        for m in range(k):
            def integrand_J(t):
                return pois_cdf(m, a * (t + 3 * Delta)) * erlang_pdf(t - k * Delta, k, h)
            J[m], _ = quad(integrand_J, k * Delta, t_max)

        # Thm6: I_raw(m), m=0..k, PoissCDF(m; a*(t - Δ))
        I_raw = np.zeros(k + 1)
        for m in range(k + 1):
            def integrand_I(t):
                return pois_cdf(m - 1, a * t) * erlang_pdf(t - k * Delta, k, h)
            I_raw[m], _ = quad(integrand_I, k * Delta, t_max)

        UB_CG[idx] = cg_upper_thm5(k, a, h, Delta, e, J)

        # keep "I shift" exactly
        I_shift = np.zeros(k + 1)
        I_shift[0] = 0
        I_shift[1:] = I_raw[:-1]

        # ---- ONLY CHANGE: remove p0-mixture in LB ----
        LB_CG[idx] = cg_lower_thm6(k, a, h, Delta, e, I_raw)

    # ---------------- formatted output ----------------
    if verbose:
        ub_str = ', '.join([f'{val:.15f}' for val in UB_CG])
        print(f"UB_CG: [{ub_str}]")

        lb_str = ', '.join([f'{val:.15f}' for val in LB_CG])
        print(f"LB_CG: [{lb_str}]")

    return UB_CG, LB_CG


# # 无预挖矿
def cg_upper_thm5(k, a, h, Delta, e, J):
    """Cao & Guo: Theorem 5 (Eq.17) UB = inf_{n>=1} { 2 - S(n) - F^{(k)}(n-1) }"""
    best = 1.0
    for n in range(1, k + 1):
        S = 0.0
        jmax = k - n
        for j in range(jmax + 1):
            ej = e[j]
            m = k - n - j  # 0..k-1
            S += ej * J[m]
        Fkn1 = Fk_def(k, n - 1, a, h, Delta)
        cand = 2.0 - S - Fkn1
        if cand < best:
            best = cand
    return best


def cg_lower_thm6(k, a, h, Delta, e, I):
    """
    Modified LB: remove the p0-mixture term.
    Original had: ej * (p0 * I[m0] + (1-p0) * I[m1]).
    Now uses:     ej * I[m0]  only.
    """
    inner = 0.0
    for j in range(k + 1):
        ej = e[j]
        m0 = k - j  # 0..k
        inner += ej * I[m0]
    return 1.0 - inner

# 有预挖矿
# def cg_upper_thm5(k, a, h, Delta, e, J):
#     """
#     Cao & Guo: Theorem 5 with pre-mining.
#     Pre-mining lead U ~ Geometric(a/h)
#     """
#     best = 1.0
#     for n in range(1, k + 1):
#         S = 0.0
#         # Sum over pre-mining lead i
#         for i in range(k - n + 1):  # i = pre-mining lead
#             ei = e[i]            
#             jmax = k - n - i
#             for j in range(jmax + 1):
#                 ej = e[j]
#                 m = k - n - i - j
#                 S += ei * ej * J[m]
#         Fkn1 = Fk_def(k, n - 1, a, h, Delta)
#         cand = 2.0 - S - Fkn1
#         if cand < best:
#             best = cand
#     return best


# def cg_lower_thm6(k, a, h, Delta, e, I):
#     """
#     Cao & Guo: Theorem 6 with pre-mining.
#     Pre-mining lead U ~ Geometric(a/h)
#     """
#     rho = a / h
#     inner = 0.0
#     # Sum over pre-mining lead i
#     for i in range(k + 1):  # i = pre-mining lead
#         prob_i = (1 - rho) * (rho ** i) if rho < 1 else 0
#         jmax = k - i
#         for j in range(jmax + 1):
#             ej = e[j]
#             m0 = k - i - j
#             inner += prob_i * ej * I[m0]
    
#     return 1.0 - inner

def Fk_def(k, n, a, h, Delta):
    """Cao & Guo: F^{(k)}(n) (Eq.12-14)"""
    if n < 0:
        return 0.0

    eps = 1.0 - np.exp(-h * Delta)
    delta = max(1.0 - a / (h * (1.0 + h * Delta)), 0.0) * np.exp(-a * Delta)
    p = eps + delta - eps * delta

    barFb = binom_ccdf(n, k, p)
    return 1.0 - (1.0 - delta) * (eps / p) ** (n + 1) * barFb


def tmax_by_erlang_mass(k, h, Delta, eps_trunc):
    """CG truncation: choose t_max s.t. Erlang CDF >= 1-ε"""
    target = 1.0 - eps_trunc
    u_max = special.gammaincinv(k, target) / h
    return k * Delta + u_max


def erlang_pdf(u, k, h):
    """Erlang pdf: Gamma(k, rate=h), u>=0"""
    u = np.asarray(u)
    result = np.zeros_like(u)
    mask = u >= 0
    uu = u[mask]

    coef = np.exp(k * np.log(h) - special.gammaln(k))
    result[mask] = coef * (uu ** (k - 1)) * np.exp(-h * uu)
    return result


def pois_cdf(m, lam):
    """Poisson CDF: P(Pois(λ) <= m)"""
    if m < 0:
        return 0.0
    return special.gammaincc(m + 1, lam)


def binom_ccdf(n, k, p):
    """Binomial CCDF: P(Bin(k,p) > n)"""
    if n < 0:
        return 1.0
    if n >= k:
        return 0.0
    cdf = special.betainc(k - n, n + 1, 1 - p)
    return 1.0 - cdf


def compute_e_pmf_series_E_over_D(a, h, Delta, Nmax):
    """CG Lemma 4: compute e(i) from PGF E(r)=N(r)/D(r) via series division"""
    C = h - a - h * a * Delta

    # N(r) = C - C r
    N = np.zeros(Nmax + 1)
    N[0] = C
    if Nmax >= 1:
        N[1] = -C

    # exp((1-r)aΔ) = exp(aΔ) * exp(-aΔ r)
    aD = a * Delta
    expaD = np.exp(aD)
    Eexp = np.zeros(Nmax + 1)
    for m in range(Nmax + 1):
        Eexp[m] = expaD * ((-aD) ** m) / special.factorial(m)

    # (h + a - a r) = (h + a) + (-a) r
    Q = np.zeros(Nmax + 1)
    for n in range(Nmax + 1):
        term1 = (h + a) * Eexp[n]
        term2 = 0.0
        if n - 1 >= 0:
            term2 = (-a) * Eexp[n - 1]
        Q[n] = term1 + term2

    # Multiply by r: shift by 1
    T = np.zeros(Nmax + 1)
    for n in range(1, Nmax + 1):
        T[n] = Q[n - 1]

    # D(r) = h - T(r)
    D = np.zeros(Nmax + 1)
    D[0] = h
    for n in range(1, Nmax + 1):
        D[n] = -T[n]

    # Series division: e = N / D
    e = np.zeros(Nmax + 1)
    D0 = D[0]

    e[0] = N[0] / D0
    for n in range(1, Nmax + 1):
        acc = 0.0
        for j in range(1, n + 1):
            acc += D[j] * e[n - j]
        e[n] = (N[n] - acc) / D0

    return e


if __name__ == "__main__":
    # 基础参数
    block_time = 13    # 整个网络平均产生一个区块所需要的时间(秒)   平均出块间隔
    n = 6              # 诚实区块的确认深度
    delta = 13         # 诚实区块传播的时延长度(秒)
    # 攻击者所占的比例列表
    alpha_list = [0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]

    cg_vs_du_bounds_beta_axis(block_time, delta, n, alpha_list)
