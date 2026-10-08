import math
from scipy.special import betainc


def log_binom(n, k):
    """计算 ln(C(n, k))，利用 math.lgamma 避免整数溢出"""
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def F_single(t, d, q):
    """
    单链确认时间的累积分布函数，直接使用正则化不完全贝塔函数：
      F_single(t) = I_q(d, t-d+1)
    当 t < d 时，返回 0.
    """
    if t < d:
        return 0.0
    return betainc(d, t - d + 1, q)


def f_single(t, d, q):
    """
    返回单条链确认时间的概率质量函数 f_single(T) = F_single(T) - F_single(T-1)
    """
    if t < d:
        return 0.0
    return math.comb(t - 1, d - 1) * (q ** d) * ((1 - q) ** (t - d))


def p_order(T, m, d, q):
    """
    计算 m 条链中中位数（第 (m+1)/2 个次序统计量）的概率质量函数。
    其中 m 为奇数，直接表示为：

    p_order(T) = (m! / (((m-1)/2)! ((m-1)/2)!)) *
                 [F_single(T-1)]^((m-1)/2) * f_single(T) * [1 - F_single(T)]^((m-1)/2)
    """
    # 当 T < d 时，单链肯定没有确认
    if T < d:
        return 0.0
    half = (m - 1) // 2
    coeff = math.factorial(m) / (math.factorial(half) * math.factorial(half))
    F_Tm1 = F_single(T, d, q)
    F_T = F_single(T, d, q)
    f_T = f_single(T, d, q)
    return coeff * (F_Tm1 ** half) * f_T * ((1 - F_T) ** half)


def expected_order_statistic(n, m, beta, p, d, T_max=10000, eps=1e-6):
    """
    计算系统确认延迟的期望轮次，采用 m 条链中中位数（第 (m+1)/2 个次序统计量）的期望。
    参数说明：
      n     : 矿工总数
      m     : 链数（奇数）
      beta  : 攻击者与诚实矿工的比例（例如，若攻击者占 30%，则 beta = 0.3，此时诚实矿工数为 n/(1+beta)）
      p     : 每个矿工每轮在每条链上出块的概率（假设 p 很小）
      d     : 单条链确认深度
      T_max : 最大轮次（当达到此值时认为累计概率接近 1）
      eps   : 当累计概率超过 1 - eps 时提前结束累加
    返回：
      E_T   : 系统确认延迟的期望轮次
    """
    # 公共链上只有诚实矿工，数量 n_H = n/(1+beta)
    n_H = n / (1 + beta)
    # 单条链每轮出块概率
    q = 1 - (1-p)**n_H

    expected = 0.0
    cumulative = 0.0
    for T in range(1, T_max + 1):
        pT = p_order(T, m, d, q)
        # print(f"pT = {pT}, T = {T}")
        expected += T * pT
        cumulative += pT
        if cumulative > 1 - eps:
            print(f"提前结束，累计概率 F(T) = {cumulative}，T = {T}，此时的pT = {pT}")
            break
    return expected

# 示例：设置参数后计算系统确认延迟的期望轮次
if __name__ == "__main__":
    # 参数设置：
    n = 10           # 矿工总数
    beta = 0         # 攻击者与诚实矿工比例（beta=0 表示全为诚实矿工）
    d = 3            # 单条链确认深度
    m_list = [11,21,31,41,51,61,71,81,91,101]

    for m in m_list:
        print(f"m = {m}")
        m2 = m + 2
        p = 1 / (256 * m2)  # 每个矿工每轮在每条链上出块的概率
        n_H = n / (1 + beta)
        q = 1 - (1-p)**n_H
        TT = d / q
        print("单链预期需要轮次", TT)
        E_T_order = expected_order_statistic(n, m, beta, p, d)
        print("基于次序统计量的确认延迟期望 E[T] =", E_T_order)
