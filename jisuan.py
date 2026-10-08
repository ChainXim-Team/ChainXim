import math

# 定义函数
def binomial_coefficient(n, k):
    return math.comb(n, k)

# 第一个函数计算
def pc_T_1(T, d, q):
    result = sum(binomial_coefficient(T, k) * (q ** k) * ((1 - q) ** (T - k)) for k in range(d, T + 1))
    return result

# 第二个函数计算
def pc_T_2(T, d, q):
    if d > 0 and T > d:
        result = binomial_coefficient(T - 1, d - 1) * (q ** (d - 1)) * ((1 - q) ** (T - d))
        return result
    else:
        return 0

# 参数定义
T = 10  # 总次数
d = 3   # 至少成功的次数
q = 0.5 # 成功概率

# 计算两个函数
result_1 = pc_T_1(T, d, q)
result_2 = pc_T_2(T, d, q)

print(f"第一个函数计算结果: {result_1}")
print(f"第二个函数计算结果: {result_2}")