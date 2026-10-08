import math


def calculate_fork_rate(p, m):
    """
    计算分叉率的函数
    :param p: 总的出块率 (float)
    :param m: 链的数量 (int)
    :return: 分叉率 (float)
    """
    # 单条链的出块率 λ
    lambda_ = p / m

    # 计算分叉率 P(分叉) = 1 - e^(-λ) - λ * e^(-λ)
    fork_rate = 1 - math.exp(-lambda_) - lambda_ * math.exp(-lambda_)

    return fork_rate


# 示例输入
p = 1/(16)  # 总的出块率
m = 12  # 链的数量

# 计算分叉率
fork_rate = calculate_fork_rate(p, m)
print(f"分叉率为: {fork_rate:.6f}")
