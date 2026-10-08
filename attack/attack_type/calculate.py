import numpy as np


def compute_sum(r, i, N_min=3, N_max=1000):
    total_sum = 0.0

    for N in range(N_min, N_max + 1):
        term = (r ** i - r ** N) / (1 - r ** N)
        total_sum += term

    return total_sum


# 示例调用
r = 0.5  # 你可以修改 r 的值
i = 2  # 你可以修改 i 的值
N_max = 10000  # 近似无穷大的上限

result = compute_sum(r, i, N_max=N_max)
print(f"计算结果: {result}")
