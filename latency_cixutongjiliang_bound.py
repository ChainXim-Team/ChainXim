import math


def calculate_T_max(m, m_thre, d, q, rho):
    """
    计算 T_max 的值，根据公式：
    T_max >= d/q + sqrt(2 * d * (1-q) / q^2 * ln(m! * m_thre / ((m - m_thre + 1)! * (m_thre - 1)! * rho)))

    参数：
    m (int): 正整数
    m_thre (int): 正整数，且 1 <= m_thre <= m
    d (float): 正实数
    q (float): 成功概率，0 < q < 1
    rho (float): 正实数

    返回：
    T_max (float): 计算得到的 T_max 值
    """
    # 检查参数的有效性
    if not isinstance(m, int) or not isinstance(m_thre, int):
        raise ValueError("m 和 m_thre 必须是整数")
    if m < 1 or m_thre < 1 or m_thre > m:
        raise ValueError("m 和 m_thre 必须是正整数，且 1 <= m_thre <= m")
    if q <= 0 or q >= 1:
        raise ValueError("q 必须在 (0, 1) 范围内")
    if d <= 0 or rho <= 0:
        raise ValueError("d 和 rho 必须是正数")

    # 计算阶乘
    m_fact = math.factorial(m)
    m_minus_mthre_plus1_fact = math.factorial(m - m_thre + 1)
    mthre_minus1_fact = math.factorial(m_thre - 1)

    # 计算对数项的分子和分母
    numerator = m_fact * m_thre
    denominator = m_minus_mthre_plus1_fact * mthre_minus1_fact * rho

    # 计算自然对数
    log_term = math.log(numerator / denominator)

    # 计算公式的两部分
    term1 = d / q
    term2 = math.sqrt(2 * (d * (1 - q) / q ** 2) * log_term)

    # 计算 T_max
    T_max = term1 + term2

    return T_max


def calculate_expectation_upper_bound(m, m_thre, d, q):
    """
    计算期望的上界：(m! * m_thre) / ((m - m_thre + 1)! * (m_thre - 1)!) * (d / q)

    参数：
    m (int): 正整数
    m_thre (int): 正整数，且 1 <= m_thre <= m
    d (float): 正实数
    q (float): 成功概率，0 < q < 1

    返回：
    upper_bound (float): 期望的上界
    """
    # 计算阶乘
    m_fact = math.factorial(m)
    m_minus_mthre_plus1_fact = math.factorial(m - m_thre + 1)
    mthre_minus1_fact = math.factorial(m_thre - 1)

    # 计算上界
    upper_bound = (m_fact * m_thre) / (m_minus_mthre_plus1_fact * mthre_minus1_fact) * (d / q)
    return upper_bound


def expected_order_statistic(n, m, beta, p, d):
    """
    占位函数，模拟基于次序统计量的确认延迟期望 E[T] 的计算。
    注：此处仅为占位，您需要提供实际的计算逻辑。
    """
    # 占位值，仅用于示例
    return d / p  # 示例返回值，需替换为实际公式


if __name__ == "__main__":
    # 参数设置：
    n = 10  # 矿工总数
    beta = 0  # 攻击者与诚实矿工比例（beta=0 表示全为诚实矿工）
    d = 3  # 单条链确认深度
    rho = 0.01  # rho 的值，可以根据需求调整

    # 定义多个 m 和 m_thre 的组合
    m_list = [11, 21, 31, 41, 51, 61, 71, 81, 91, 101]  # 不同的 m 值
    m_thre_list = [m for m in m_list]  # m_thre 与 m 相等

    for m, m_thre in zip(m_list, m_thre_list):
        print(f"m = {m}, m_thre = {m_thre}")
        m2 = m + 2
        p = 1 / (256 * m2)  # 每个矿工每轮在每条链上出块的概率
        n_H = n / (1 + beta)  # 诚实矿工数量
        q = 1 - (1 - p) ** n_H  # 至少一个矿工出块的概率
        TT = d / q
        TT2 = math.exp(1) * TT
        print(f"单链预期需要轮次 TT = {TT:.4f}")
        print(f"计算的预期需要轮次 TT2 = {TT2:.4f}")

        # 计算 T_max
        T_max = calculate_T_max(m, m_thre, d, q, rho)
        print(f"T_max >= {T_max:.4f}")

        # 计算期望的上界
        upper_bound = calculate_expectation_upper_bound(m, m_thre, d, q)
        print(f"期望的上界 = {upper_bound:.4f}")

        # 基于次序统计量的确认延迟期望 E[T]（占位函数）
        E_T_order = expected_order_statistic(n, m, beta, p, d)
        print(f"基于次序统计量的确认延迟期望 E[T] = {E_T_order:.4f}")
        print("-" * 50)