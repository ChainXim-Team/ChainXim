import math

def log_binom(n, k):
    """计算 ln(C(n, k))，利用 lgamma 函数"""
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

def p_chain_confirm(T, d, q):
    """
    单条链在 T 轮内至少产生 d 个区块的概率，
    q 是单轮内该链产生一个新区块的概率。
    这里利用对数来防止数值溢出。
    """
    p = 0.0
    for k in range(d, T + 1):
        # 计算 log(组合数 * q^k * (1-q)^(T-k))
        log_term = log_binom(T, k) + k * math.log(q) + (T - k) * math.log(1 - q)
        p += math.exp(log_term)
    return p

# 对p_chain_confirm求期望
def expected_confirm_time(d, q, beta, T_max=10000, eps=1e-6):
    """
    Calculates the expected round T until p_chain_confirm(T, d, q) >= 1,
    where p_chain_confirm(T, d, q) is the probability that
    at least d blocks have been produced by round T.

    d     : confirmation depth
    q     : probability of producing a block in a single round
    T_max : maximum number of rounds to check
    eps   : threshold to stop early
    """
    q = (n / (1 + beta)) * q
    expected_val = 0.0
    prev_conf = 0.0  # p_chain_confirm for T-1
    for T in range(d, T_max + 1):
        curr_conf = p_chain_confirm(T, d, q)
        diff = curr_conf - prev_conf
        expected_val += T * diff
        prev_conf = curr_conf
        if curr_conf > 1 - eps:
            print(f"Stopping early, cumulative probability = {curr_conf}, T = {T}")
            break
    return expected_val

def P_conf(T, m, d, q):
    """
    在 T 轮内，m 条链中至少有 ceil((m+1)/2) 条链确认（产生至少 d 个区块）的概率。
    这里 m 为奇数，因此 ceil((m+1)/2) == (m+1)//2。
    """
    p_chain = p_chain_confirm(T, d, q)
    # print(f'p_chain: {p_chain}')
    P = 0.0
    j_min = (m + 1) // 2
    for j in range(j_min, m + 1):
        # 使用 math.comb 计算组合数一般不会溢出，因为 m 较小
        P += math.comb(m, j) * (p_chain ** j) * ((1 - p_chain) ** (m - j))
    # print(f'P: {P}')
    return P

def expected_rounds(m, d, q, T_max=10000, eps=1e-6):
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
    # q = 1-(1-p)**(n/(1+beta))
    # q = (n / (1 + beta)) * p

    expected = 0.0
    F_prev = 0.0  # P_conf(T-1)
    # 从 T=1 开始累加概率质量
    for T in range(d, T_max + 1):
        # curr_conf = p_chain_confirm(T, d, q)
        F_T = P_conf(T, m, d, q)
        f_T = F_T - F_prev  # 确认时刻恰好为 T 轮的概率
        expected += T * f_T
        F_prev = F_T
        # 当累计确认概率足够接近 1 时提前结束
        if F_T > 1 - eps:
            print(f"提前结束，累计概率 F(T) = {F_T}，T = {T}")
            break
    return expected

# 示例：设置参数后计算确认延迟的期望轮次
if __name__ == "__main__":
    # 参数设置：
    n = 20         # 矿工总数
    m_list = [11,21,31,41,51]         # 链数（奇数）
    beta = 0       # 攻击者与诚实矿工比例（beta=0 表示全是诚实矿工）
    d = 3          # 单条链确认深度

    for m in m_list:
        print(f"m = {m}")
        m2 = m + 2
        p = 1 / (256 * m2)  # 每个矿工每轮在每条链上出块的概率
        q = 1 - (1 - p) ** (n / (1 + beta))
        print(f"p = {p}, q = {q}")
        E_T = expected_rounds(m, d, q)
        print("期望确认延迟轮次 E[T] =", E_T)
        T = expected_confirm_time(d, p, beta)
        print("单链确认延迟轮次 E[T] =", T)
