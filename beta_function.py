import numpy as np
from scipy.special import betainc, binom, factorial

def binomial_tail_prob(T, d, q):
    """计算 Pr{X(T) >= d} = sum_{k=d}^T binom(T, k) * q^k * (1-q)^(T-k)"""
    prob = 0.0
    for k in range(d, T + 1):
        prob += binom(T, k) * (q ** k) * ((1 - q) ** (T - k))
    return prob

def beta_from_factorial(x, y):
    """使用维基百科公式计算 B(x, y) = (x-1)! (y-1)! / (x+y-1)!"""
    return factorial(x - 1) * factorial(y - 1) / factorial(x + y - 1)

def regularized_beta_manual(q, a, b):
    """手动计算 I_q(a, b)，需要积分，这里用二项和近似验证"""
    # 注意：直接用积分定义计算 I_q 需要数值积分，这里用二项和验证
    pass  # 我们直接用 scipy 的 betainc 来对比

# 参数设置
T = 10      # 试验次数
d = 3       # 成功的阈值
q = 0.4     # 成功概率

# 计算 Pr{X(T) >= d}
binom_prob = binomial_tail_prob(T, d, q)
print(f"Pr{{X(T) >= {d}}} (Binomial Sum): {binom_prob:.6f}")

# 计算 I_q(d, T - d + 1) 使用 scipy
beta_prob = betainc(d, T - d + 1, q)
print(f"I_q({d}, {T - d + 1}) (scipy betainc): {beta_prob:.6f}")

# 检查是否相等
diff = abs(binom_prob - beta_prob)
print(f"Difference: {diff:.10f}")
if diff < 1e-10:
    print("两个结果几乎相等，验证通过！")
else:
    print("结果有差异，请检查计算。")

# 计算 B(d, T - d + 1) 使用维基百科公式
a = d
b = T - d + 1
B_factorial = beta_from_factorial(a, b)
print(f"B({a}, {b}) (Factorial Formula): {B_factorial:.10f}")

# 注意：I_q 需要 B_q(a, b) / B(a, b)，这里仅展示 B(a, b) 的计算