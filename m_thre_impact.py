import math
from scipy.special import betainc


def log_binom(n, k):
    """计算 ln(C(n, k))，利用 math.lgamma 避免整数溢出"""
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def F_single(t, d, q):
    """单链确认时间的累积分布函数"""
    if t < d:
        return 0.0
    return betainc(d, t - d + 1, q)


def f_single(t, d, q):
    """单链确认时间的概率质量函数"""
    if t < d:
        return 0.0
    return math.comb(t - 1, d - 1) * (q ** d) * ((1 - q) ** (t - d))


def p_order(T, m, m_thre, d, q):
    """
    计算 m 条链中第 m_thre 个次序统计量的概率质量函数。

    参数：
      T      : 确认轮次
      m      : 总链数
      m_thre : 确认阈值
      d      : 单条链确认深度
      q      : 单条链每轮出块概率
    """
    # 当 T < d 时，单链肯定没有确认
    if T < d:
        return 0.0

    # 计算 P_conf(T) 对应的概率
    P_c = F_single(T, d, q)
    p_c = f_single(T, d, q)

    # 根据新公式计算次序统计量
    coeff = (math.factorial(m) * m_thre) / (math.factorial(m - m_thre + 1) * math.factorial(m_thre - 1))
    P_conf = coeff * (P_c ** (m_thre - 1)) * ((1 - P_c) ** (m - m_thre)) * p_c

    return P_conf


def expected_order_statistic(n, m, m_thre, beta, p, d, q, T_max=10000, eps=1e-6):
    """
    计算系统确认延迟的期望轮次，允许自定义确认阈值 m_thre。
    """
    # 公共链上只有诚实矿工，数量 n_H = n/(1+beta)

    expected = 0.0
    cumulative = 0.0
    for T in range(1, T_max + 1):
        pT = p_order(T, m, m_thre, d, q)  # 修改此处，传入 m_thre 参数
        # print(f"p_order({T}) = {pT}, T = {T}")
        expected += T * pT
        cumulative += pT
        if cumulative > 1 - eps:
            print(f"提前结束，累计概率 F(T) = {cumulative}，T = {T}")
            break
    return expected


def S_func(n, beta, flag_up_down, ng):
    """计算 S(n, beta)"""
    tmp = 0.0
    if beta == 0:
        return 0
    if n == 0:
        return beta
    else:
        if flag_up_down == 1:
            for j in range(0, n + 1):
                log_comb = math.lgamma(n + j) - math.lgamma(j + 1) - math.lgamma(n)
                term = math.exp(log_comb + n * math.log(1 / (1 + beta)) + j * math.log(beta / (1 + beta))) \
                       * (1 - beta ** (n - j + 1))
                tmp += term
        if flag_up_down == 0:
            for j in range(0, n + 1):
                log_comb = math.lgamma(n + j) - math.lgamma(j + 1) - math.lgamma(n)
                term = math.exp(log_comb + n * math.log(1 / (1 + beta)) + j * math.log(beta / (1 + beta))) \
                       * ((1 - beta ** (n - j + 1)) / (1 - beta ** (ng + 1)))
                tmp += term
        return 1 - tmp

def overall_attack_success(m, m_thre, p_success_less, p_success_equal, p_success_geq):
    """
    计算总体攻击成功概率，允许自定义确认阈值 m_thre。

    参数：
      m               : 投票者链总数（奇数）
      m_thre          : 确认阈值，至少 m_thre 条链成功才算确认
      p_success_less  : 条件 P(success | X(T) < d) 对应 p_1
      p_success_equal : 条件 P(success | X(T) = d) 对应 p_2
      p_success_geq   : 条件 P(success | X(T) >= d) 对应 p_3

    返回：
      总体攻击成功概率 P_attack
    """
    # 情况1：X(T)=d 的链成功，概率为 p_success_equal，
    # 此时只需要在另外 m-1 条链中获得至少 m_thre-1 个成功。
    sum_case1 = 0.0
    for i in range(0, m - m_thre + 1):
        for j in range(0, m - m_thre + 1):
            if i + j >= m_thre - 1:
                term = (math.comb(m-m_thre, i) * (p_success_less ** i) * ((1 - p_success_less) ** (m-m_thre - i)) *
                        math.comb(m-m_thre, j) * (p_success_geq ** j) * ((1 - p_success_geq) ** (m-m_thre - j)))
                sum_case1 += term

    # 情况2：X(T)=d 的链失败，概率为 1 - p_success_equal，
    # 此时需要在另外 m-1 条链中获得至少 m_thre 个成功。
    sum_case2 = 0.0
    for i in range(0, m - m_thre + 1):
        for j in range(0, m - m_thre + 1):
            if i + j >= m_thre:
                term = (math.comb(m-m_thre, i) * (p_success_less ** i) * ((1 - p_success_less) ** (m-m_thre - i)) *
                        math.comb(m-m_thre, j) * (p_success_geq ** j) * ((1 - p_success_geq) ** (m-m_thre - j)))
                sum_case2 += term

    P_attack = p_success_equal * sum_case1 + (1 - p_success_equal) * sum_case2
    return P_attack


def P_X_T(k, T, q):
    """计算诚实方在 T 轮内出块数为 k 的概率"""
    log_comb = math.lgamma(T + 1) - math.lgamma(k + 1) - math.lgamma(T - k + 1)
    log_prob = log_comb + k * math.log(q) + (T - k) * math.log(1 - q)
    return math.exp(log_prob)


def success_probability_less_than_d(T, d, q, beta, flag_up_down, ng):
    """计算 P(success | X(T) < d)"""
    num = 0.0
    den = 0.0
    for k in range(0, d):
        p_k = P_X_T(k, T, q)
        num += p_k * S_func(k, beta, flag_up_down, ng)
        den += p_k
    return num / den if den != 0 else 0.0


def success_probability_equal_d(T, d, q, beta, flag_up_down, ng):
    """计算 P(success | X(T) = d)"""
    return S_func(d, beta, flag_up_down, ng)


def success_probability_geq_d(T, d, q, beta, flag_up_down, ng):
    """计算 P(success | X(T) >= d)"""
    num = 0.0
    den = 0.0
    for k in range(d, T + 1):
        p_k = P_X_T(k, T, q)
        num += p_k * S_func(k, beta, flag_up_down, ng)
        den += p_k
    return num / den if den != 0 else 0.0

# 新增函数计算指定表达式
def calculate_rho(m, m_thre, mu):
    """
    计算表达式：m! * m_thre * e^(-mu) / ((m - m_thre + 1)! * (m_thre - 1)!)
    
    参数：
    m (int): 正整数
    m_thre (int): 正整数，且 1 <= m_thre <= m
    mu (float): 正实数
    
    返回：
    result (float): 计算结果
    """
    # 检查参数有效性
    if not isinstance(m, int) or not isinstance(m_thre, int):
        raise ValueError("m 和 m_thre 必须是整数")
    if m < 1 or m_thre < 1 or m_thre > m:
        raise ValueError("m 和 m_thre 必须是正整数，且 1 <= m_thre <= m")
    if mu <= 0:
        raise ValueError("mu 必须是正数")

    # 计算阶乘
    m_fact = math.factorial(m)
    m_minus_mthre_plus1_fact = math.factorial(m - m_thre + 1)
    mthre_minus1_fact = math.factorial(m_thre - 1)

    # 计算表达式
    numerator = m_fact * m_thre * math.exp(-mu)
    denominator = m_minus_mthre_plus1_fact * mthre_minus1_fact
    result = numerator / denominator

    return result


# 主程序
if __name__ == "__main__":
    m = 21
    m_thres = [11,21,31,41,51,61,71,81,91,101]  # 自定义确认阈值
    d = 3
    beta = 0.6
    n = 16
    n_H = n / (1 + beta)
    p = 1 / (256 * m)
    q = 1 - (1 - p) ** n_H
    flag_up_downs = [0, 1]
    ng = 3
    betas = [0]
    Ts = []
    downs = []
    ups = []

    file_path = 'D:/mthre_impact.txt'  # 请将路径替换为你指定的文件路径

    Tss = {}
    downss = {}
    upss = {}

    for m_thre in m_thres:
        m = m_thre
        Tss[m_thre] = {}
        downss[m_thre] = {}
        upss[m_thre] = {}

        with open(file_path, 'a') as f:
            f.write(f"\nm_thre:{m_thre}\n")

        for beta in betas:
            with open(file_path, 'a') as f:
                f.write(f"  beta:{beta}\n")

            

            n = 10 * beta + 10
            n_H = n / (1 + beta)
            m2 = m + 2
            p = 1 / (256 * m2)
            q = 1 - (1 - p) ** n_H

            T = expected_order_statistic(n, m, m_thre, beta, p, d, q)
            T = math.ceil(T)

            Tss[m_thre][beta] = T  # 存储 T 值
            with open(file_path, 'a') as f:
                f.write(f"    T:{T}\n")
            TT = d / q
            expression_result = calculate_rho(m, m_thre, TT)
            print(f"m_thre = {m_thre}, 表达式结果: {expression_result}")
            print(f"单链期望的确认轮数 E_T = {TT}")
            print('expect_latency:', T)

            # # 初始化 ups 和 downs
            # ups = []
            # downs = []

            # for flag_up_down in flag_up_downs:
            #     p_success_less = success_probability_less_than_d(T, d, q, beta, flag_up_down, ng)
            #     p_success_equal = success_probability_equal_d(T, d, q, beta, flag_up_down, ng)
            #     p_success_geq = success_probability_geq_d(T, d, q, beta, flag_up_down, ng)

            #     P_attack = overall_attack_success(m, m_thre, p_success_less, p_success_equal, p_success_geq)
            #     print("总体双花攻击成功率 P_attack =", P_attack)

            #     if flag_up_down == 0:
            #         downs.append(P_attack)
            #     if flag_up_down == 1:
            #         ups.append(P_attack)

            # downss[m_thre][beta] = downs
            # upss[m_thre][beta] = ups

            # with open(file_path, 'a') as f:
            #     f.write(f"    downs:{downs}\n"
            #             f"    ups:{ups}\n")

            # print("downs = ", downs)
            # print("ups = ", ups)

    # 输出最终结果
    print('Tss:', Tss)
    print('downss:', downss)
    print('upss:', upss)