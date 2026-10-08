import math

def binom(n, k):
    """计算组合数 C(n, k)"""
    return math.comb(n, k)

def p_chain_confirm(T, d, q):
    """
    单条链在 T 轮内至少产生 d 个区块的概率，
    q 是单轮内该链产生一个新区块的概率。
    """
    p = 0.0
    for k in range(d, T + 1):
        p += binom(T, k) * (q ** k) * ((1 - q) ** (T - k))
    return p

def P_conf(T, m, d, q):
    """
    在 T 轮内，m 条链中至少有 ceil((m+1)/2) 条链确认（产生至少 d 个区块）的概率。
    这里 m 为奇数，因此 ceil((m+1)/2) == (m+1)//2。
    """
    p_chain = p_chain_confirm(T, d, q)
    P = 0.0
    j_min = (m + 1) // 2
    for j in range(j_min, m + 1):
        P += binom(m, j) * (p_chain ** j) * ((1 - p_chain) ** (m - j))
    return P

def expected_rounds(n, m, beta, p, d, T_max=10000, eps=1e-6):
    """
    计算确认延迟的期望轮数。参数说明：
      n     : 矿工总数
      m     : 链数（奇数）
      beta  : 攻击者与诚实矿工的比例（例如，如果攻击者占 30%，则 beta=0.3，
              此时诚实矿工比例为 1/(1+beta)）
      p     : 每个矿工每轮在每条链上出块的概率（假设 p 很小）
      d     : 单条链的确认深度
      T_max : 最大轮数（当达到此值后停止累加）
      eps   : 当累计确认概率超过 1-eps 时提前停止
    返回：
      E_T   : 期望的确认轮数
    """
    # 公共链上只有诚实矿工在工作，其数量为 n / (1+beta)
    # 每轮在一条链上出块的概率近似为
    q = (n / (1 + beta)) * p

    expected = 0.0
    F_prev = 0.0  # P_conf(T-1)
    # 从 T=1 开始累加概率质量
    for T in range(1, T_max + 1):
        F_T = P_conf(T, m, d, q)
        f_T = F_T - F_prev  # 确认时刻恰好为 T 轮的概率
        expected += T * f_T
        F_prev = F_T
        # 当累计确认概率足够接近 1 时提前结束
        if F_T > 1 - eps:
            break
    return expected

# 示例：设置参数后计算确认延迟的期望轮次
if __name__ == "__main__":
    # 参数设置：
    n = 10        # 矿工总数
    m = 5           # 链数（奇数）
    beta = 4/6      # 攻击者与诚实矿工比例（例如：攻击者占 30%）
    p = 0.03137        # 每个矿工每轮在每条链上出块的概率
    d = 1           # 单条链确认深度

    E_T = expected_rounds(n, m, beta, p, d)
    print("期望确认延迟轮次 E[T] =", E_T)
