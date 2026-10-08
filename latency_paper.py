import math

def calculate_r_and_delta_k(k, xi, q, m):
    """
    根据设定的 k 计算 Lemma 35 中的 r 和 delta_k。

    参数:
    k (int): 用户设定的 k 值，必须为正整数
    xi (float): ξ 参数，0 < xi <= 1
    q (float): 每轮诚实矿工挖出至少一个区块的概率，0 < q < 1
    m (int): 投票者区块链的数量

    返回:
    tuple: (r_min, delta_k) - r 的最小整数值和对应的 delta_k
    """
    # 检查输入参数
    if k < 1 or not isinstance(k, int):
        raise ValueError("k 必须是正整数")
    if not (0 < xi <= 1):
        raise ValueError("xi 必须在 (0, 1] 之间")
    if not (0 < q < 1):
        raise ValueError("q 必须在 (0, 1) 之间")
    if m < 1 or not isinstance(m, int):
        raise ValueError("m 必须是正整数")

    # 计算 eta
    eta = (xi ** 2 * q) / 180

    # 计算 r (公式 116)
    denominator = (1 - xi / 6) * xi * q
    r_float = 2 * (k + 1) / denominator + 1
    r_min = math.ceil(r_float)

    # 计算 delta_k (公式 134)
    delta_k = 6 * m * (eta ** -2) * math.exp(-eta * k / (2 * q))

    return r_min, delta_k

def calculate_k_and_r_from_delta(delta_k, xi, q, m):
    """
    根据设定的 delta_k 计算 Lemma 35 中的 k 和 r。

    参数:
    delta_k (float): 用户设定的 delta_k 值，0 < delta_k < 1
    xi (float): ξ 参数，0 < xi <= 1
    q (float): 每轮诚实矿工挖出至少一个区块的概率，0 < q < 1
    m (int): 投票者区块链的数量

    返回:
    tuple: (k, r_min) - 计算出的 k 和 r 的最小整数值
    """
    # 检查输入参数
    if not (0 < delta_k < 1):
        raise ValueError("delta_k 必须在 (0, 1) 之间")
    if not (0 < xi <= 1):
        raise ValueError("xi 必须在 (0, 1] 之间")
    if not (0 < q < 1):
        raise ValueError("q 必须在 (0, 1) 之间")
    if m < 1 or not isinstance(m, int):
        raise ValueError("m 必须是正整数")

    # 计算 eta
    eta = (xi ** 2 * q) / 180

    # 反解 k (公式 134)
    # delta_k = 6 * m * eta^-2 * exp(-eta * k / (2 * q))
    # => exp(-eta * k / (2 * q)) = delta_k / (6 * m * eta^-2)
    # => -eta * k / (2 * q) = ln(delta_k / (6 * m * eta^-2))
    # => k = -2 * q / eta * ln(delta_k / (6 * m * eta^-2))
    k_float = -2 * q / eta * math.log(delta_k / (6 * m * (eta ** -2)))
    k = math.ceil(k_float)
    if k < 1:
        raise ValueError("计算出的 k 小于 1，请减小 delta_k 或调整其他参数")

    # 计算 r (公式 116)
    denominator = (1 - xi / 6) * xi * q
    r_float = 2 * (k + 1) / denominator + 1
    r_min = math.ceil(r_float)

    return k, r_min

# 示例用法
if __name__ == "__main__":
    # 公共参数
    n = 21  # 矿工总数
    adver_num = 1  # 攻击者数量
    beta = adver_num / n
    xi = (1 - 2 * beta) / (1 - beta)  # ξ = (1 - 2β) / (1 - β)，假设 β = 0.25

    m_list = [11,21,31,41,51,61,71,81,91,101]  # 投票者区块链数量列表

    # 情况 1：设定 k，计算 r 和 delta_k
    k_input = 3
    print("情况 1：设定 k，计算 r 和 delta_k")
    for m in m_list:
        print(f"\nm = {m}")
        m_adjusted = m + 2
        nh = n / (1 + xi)  # 诚实矿工数量
        p = 1 / (256 * m_adjusted)  # 每个矿工每轮在每条链上出块的概率
        q = 1 - (1 - p) ** nh  # 至少出一个块的概率

        try:
            r, delta_k = calculate_r_and_delta_k(k_input, xi, q, m_adjusted)
            print(f"参数设置：k={k_input}, ξ={xi}, q={q}, m={m_adjusted}")
            print(f"计算得到的 r 最小值: {r}")
            print(f"对应的 δ_k: {delta_k}")
        except ValueError as e:
            print(f"错误: {e}")

    # # 情况 2：设定 delta_k，计算 k 和 r
    # delta_k_input = 0.001
    # print("\n情况 2：设定 δ_k，计算 k 和 r")
    # for m in m_list:
    #     print(f"\nm = {m}")
    #     m_adjusted = m + 2
    #     nh = n / (1 + xi)  # 诚实矿工数量
    #     p = 1 / (256 * m_adjusted)  # 每个矿工每轮在每条链上出块的概率
    #     q = 1 - (1 - p) ** nh  # 至少出一个块的概率

    #     try:
    #         k, r = calculate_k_and_r_from_delta(delta_k_input, xi, q, m_adjusted)
    #         print(f"参数设置：δ_k={delta_k_input}, ξ={xi}, q={q}, m={m_adjusted}")
    #         print(f"计算得到的 k: {k}")
    #         print(f"计算得到的 r 最小值: {r}")
    #     except ValueError as e:
    #         print(f"错误: {e}")