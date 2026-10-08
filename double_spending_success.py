import math


def calculate_combination(n, k):
    """
    计算组合数 C(n, k) = n! / (k! * (n-k)!)
    """
    if k > n or k < 0:
        return 0
    return math.factorial(n) // (math.factorial(k) * math.factorial(n - k))


def single_chain_success_rate(n, ng, beta):
    """
    计算单链的理论成功率

    参数:
        n: 单链攻击参数
        ng: 攻击难度参数
        beta: 对手占比 (adver_list / honest_list)

    返回:
        thr_rate: 单链成功率
    """
    tmp = 0

    if ng > 100 * n:
        # Ng 非常大
        if beta >= 1:
            return 1.0
        else:
            for j in range(0, n + 1):
                tmp += (math.factorial(j + n - 1)) / (math.factorial(j) * math.factorial(n - 1)) * \
                       ((1 / (1 + beta)) ** n) * ((beta / (1 + beta)) ** j) * (1 - beta ** (n - j + 1))
            return 1 - tmp
    else:
        # Ng 正常
        if beta == 1:
            for j in range(0, n + 1):
                1 / (2 ** (n + j)) * (math.factorial(j + n - 1)) / (math.factorial(j) * math.factorial(n - 1)) * \
                       ((n - j + 1) / (ng + 1))
            return 1 - tmp
        else:
            for j in range(0, n + 1):
                tmp += (math.factorial(j + n - 1)) / (math.factorial(j) * math.factorial(n - 1)) * \
                       ((1 / (1 + beta)) ** n) * ((beta / (1 + beta)) ** j) * \
                       ((1 - beta ** (n - j + 1)) / (1 - beta ** (ng + 1)))
            return 1 - tmp


def success_probability_N_chains(thr_rate, N):
    """
    计算 N 条链中超过一半成功的概率

    参数:
        thr_rate: 单链的成功率 (0 <= thr_rate <= 1)
        N: 链的总数量 (正整数)

    返回:
        overall_success_rate: 超过一半链成功的概率
    """
    threshold = (N // 2)  # 超过一半的最小成功链数
    overall_success_rate = 0.0

    for k in range(threshold+1, N+1):
        # print('k:', k)
        comb = calculate_combination(N, k)
        success_prob = comb * (thr_rate ** k) * ((1 - thr_rate) ** (N - k))
        overall_success_rate += success_prob

    return overall_success_rate


def compute_formula(N, Ng, beta):
    result = 0.0
    denominator = 1 - beta ** (Ng + 1)

    for n in range(N + 1):
        binomial_coeff = math.comb(n + N - 1, n)
        term1 = (1 / (1 + beta)) ** N
        term2 = (beta / (1 + beta)) ** n
        numerator = 1 - beta ** (N - n + 1)

        term = binomial_coeff * term1 * term2 * (numerator / denominator)
        result += term

    return result

if __name__ == "__main__":
    # 定义攻击参数
    n = 2  # 单链攻击参数
    ng = 1000  # 攻击难度参数
    beta_list = [0.5]  # 对手占比

    N_total = 21  # 链的总数
    for beta in beta_list:
        # 计算单链成功率
        thr_rate = single_chain_success_rate(n, ng, beta)
        print(f"单链攻击参数 N: {n}, 攻击难度参数 Ng: {ng}, 对手占比 beta: {beta}")
        print(f"计算得到的单链成功率为: {thr_rate:.4f}")

        # 计算多链成功概率
        overall_success = success_probability_N_chains(thr_rate, N_total)

        # threshold = (N_total // 2)  # 超过一半的最小成功链数
        # overall_success = single_chain_success_rate(threshold, threshold, thr_rate)

        print(f"当链总数为 {N_total} 时，超过一半链成功的概率为: {overall_success:.4f}")

        N = 2
        Ng = 3
        # beta = 0.5


        # result = single_chain_success_rate(n, Ng, beta)
        # result = result
        result = compute_formula(N, Ng, beta)
        print(f"理论计算结果1: {result:.4f}")
        fail_rate = success_probability_N_chains(result, N_total)
        print(f"下限1: {fail_rate}")

        result = single_chain_success_rate(n, Ng, beta)
        result = result
        print(f"理论计算结果2: {result:.4f}")
        fail_rate = success_probability_N_chains(result, N_total)
        print(f"下限2: {fail_rate}")
