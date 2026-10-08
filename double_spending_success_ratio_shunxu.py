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
    F_T = F_Tm1
    f_T = f_single(T, d, q)
    return coeff * (F_Tm1 ** half) * f_T * ((1 - F_T) ** half)


def expected_order_statistic(n, m, beta, q, d, T_max=10000, eps=1e-6):
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
    # 单条链每轮出块概率

    expected = 0.0
    cumulative = 0.0
    for T in range(1, T_max + 1):
        pT = p_order(T, m, d, q)
        expected += T * pT
        cumulative += pT
        if cumulative > 1 - eps:
            print(f"提前结束，累计概率 F(T) = {cumulative}，T = {T}")
            break
    return expected

def S_func(n, beta, flag_up_down, ng):
    """
    计算 S(n, beta)：
      S(n, beta) = 1 - sum_{j=0}^{n} [ C(j+n-1, j) * (1/(1+beta))^n * (beta/(1+beta))^j * (1 - beta^(n-j+1)) ]
    这里 n 表示诚实方出块数 k。
    """
    tmp = 0.0
    if beta == 0:
        return 0
    if n == 0:
        return beta
    else:
        if flag_up_down == 1:
            for j in range(0, n + 1):
                # 使用 math.lgamma 计算 ln(C(j+n-1, j))
                log_comb = math.lgamma(n + j) - math.lgamma(j + 1) - math.lgamma(n)
                term = math.exp(log_comb + n * math.log(1 / (1 + beta)) + j * math.log(beta / (1 + beta))) \
                       * (1 - beta ** (n - j + 1))
                tmp += term
        if flag_up_down == 0:
            for j in range(0, n + 1):
                # 使用 math.lgamma 计算 ln(C(j+n-1, j))
                log_comb = math.lgamma(n + j) - math.lgamma(j + 1) - math.lgamma(n)
                term = math.exp(log_comb + n * math.log(1 / (1 + beta)) + j * math.log(beta / (1 + beta))) \
                       * ((1 - beta ** (n - j + 1)) / (1 - beta ** (ng + 1)))
                tmp += term
        return 1 - tmp

def P_X_T(k, T, q):
    """
    计算诚实方在 T 轮内出块数为 k 的概率，
    即 P{X(T)=k} = C(T, k)*q^k*(1-q)^(T-k)
    这里使用对数计算组合数，防止溢出。
    """
    # 使用 math.lgamma 计算 ln(C(T,k))
    log_comb = math.lgamma(T + 1) - math.lgamma(k + 1) - math.lgamma(T - k + 1)
    log_prob = log_comb + k * math.log(q) + (T - k) * math.log(1 - q)
    return math.exp(log_prob)

def success_probability_less_than_d(T, d, q, beta, flag_up_down, ng):
    """
    计算条件 P(success | X(T) < d)：
      = [sum_{k=0}^{d-1} P_X_T(k, T, q)*S_func(k, beta)] / [sum_{k=0}^{d-1} P_X_T(k, T, q)]
    """
    num = 0.0
    den = 0.0
    for k in range(0, d):
        p_k = P_X_T(k, T, q)
        num += p_k * S_func(k, beta, flag_up_down, ng)
        den += p_k
    return num / den if den != 0 else 0.0

def success_probability_equal_d(T, d, q, beta, flag_up_down, ng):
    """
    计算条件 P(success | X(T) = d)：
      = S_func(d, beta)
    """
    return S_func(d, beta, flag_up_down, ng)

def success_probability_geq_d(T, d, q, beta, flag_up_down, ng):
    """
    计算条件 P(success | X(T) >= d)：
      = [sum_{k=d}^{T} P_X_T(k, T, q)*S_func(k, beta)] / [sum_{k=d}^{T} P_X_T(k, T, q)]
    """
    num = 0.0
    den = 0.0
    for k in range(d, T + 1):
        p_k = P_X_T(k, T, q)
        num += p_k * S_func(k, beta, flag_up_down, ng)
        den += p_k
    return num / den if den != 0 else 0.0


def overall_attack_success(m, p_success_less, p_success_equal, p_success_geq):
    """
    计算总体攻击成功概率。

    参数：
      m               : 投票者链总数（奇数）
      p_success_less  : 条件 P(success | X(T) < d) 对应 p_1
      p_success_equal : 条件 P(success | X(T) = d) 对应 p_2
      p_success_geq   : 条件 P(success | X(T) >= d) 对应 p_3

    攻击成功的条件为在至少 (m+1)/2 条链上攻击成功。
    假设：
      - 有 (m-1)/2 条链满足 X(T)<d (成功概率 p_1)
      - 有 1 条链满足 X(T)=d   (成功概率 p_2)
      - 有 (m-1)/2 条链满足 X(T)>=d (成功概率 p_3)

    返回：
      总体攻击成功概率 P_attack
    """
    r = (m - 1) // 2
    threshold = (m + 1) // 2  # 因为 m 为奇数，所以 (m+1)/2 是整数

    # 情况1：X(T)=d 的链成功，概率为 p_success_equal，
    # 此时只需要在另外 m-1 条链中获得至少 threshold - 1 个成功。
    sum_case1 = 0.0
    for i in range(0, r + 1):
        for j in range(0, r + 1):
            if i + j >= threshold - 1:
                term = (math.comb(r, i) * (p_success_less ** i) * ((1 - p_success_less) ** (r - i)) *
                        math.comb(r, j) * (p_success_geq ** j) * ((1 - p_success_geq) ** (r - j)))
                sum_case1 += term

    # 情况2：X(T)=d 的链失败，概率为 1 - p_success_equal，
    # 此时需要在另外 m-1 条链中获得至少 threshold 个成功。
    sum_case2 = 0.0
    for i in range(0, r + 1):
        for j in range(0, r + 1):
            if i + j >= threshold:
                term = (math.comb(r, i) * (p_success_less ** i) * ((1 - p_success_less) ** (r - i)) *
                        math.comb(r, j) * (p_success_geq ** j) * ((1 - p_success_geq) ** (r - j)))
                sum_case2 += term
    P_attack = p_success_equal * sum_case1 + (1 - p_success_equal) * sum_case2
    return P_attack

# 示例：设置参数后计算三种条件下的攻击成功概率
if __name__ == "__main__":
    # 参数设置
    m = 21
    d = 2           # 单条链确认深度
    beta = 0.6      # 攻击者与诚实矿工比例（例如攻击者占 30%）
    n = 16        # 矿工总数
    # 公共链上只有诚实矿工，其数量为 n_H = n/(1+beta)
    n_H = n / (1 + beta)
    # 每轮单个矿工出块概率 p (例如取 p=1e-4)
    p = 1 / (256 * m)
    # 则单条链出块概率 q 约为
    q = 1 - (1-p)**n_H
    flag_up_downs = [0,1]
    ng = 3
    betas = [0.3,0.4,0.5,0.6,0.7,0.8]
    downs = []
    ups = []

    for beta in betas:
        print("beta = ", beta)
        n = 10 * beta + 10
        n_H = n / (1 + beta)
        # 每轮单个矿工出块概率 p (例如取 p=1e-4)
        m2 = m + 2
        p = 1 / (256 * m2)
        # 则单条链出块概率 q 约为
        q = 1 - (1 - p) ** n_H
        T = expected_order_statistic(n, m, beta, q, d, T_max=10000, eps=1e-6)  # 确认时刻（轮数），例如 T=100 轮
        T = math.ceil(T)
        print(f"期望的确认轮数 E_T = {T}")
        for flag_up_down in flag_up_downs:
            print("flag_up_down = ", flag_up_down)

            p_success_less = success_probability_less_than_d(T, d, q, beta, flag_up_down, ng)
            p_success_equal = success_probability_equal_d(T, d, q, beta, flag_up_down, ng)
            p_success_geq = success_probability_geq_d(T, d, q, beta, flag_up_down, ng)

            print("P(success | X(T) < d) =", p_success_less)
            print("P(success | X(T) = d) =", p_success_equal)
            print("P(success | X(T) >= d) =", p_success_geq)

            P_attack = overall_attack_success(m, p_success_less, p_success_equal, p_success_geq)
            print("总体双花攻击成功率 P_attack =", P_attack)
            if flag_up_down == 0:
                downs.append(P_attack)
            if flag_up_down == 1:
                ups.append(P_attack)
        print("downs = ", downs)
        print("ups = ", ups)
