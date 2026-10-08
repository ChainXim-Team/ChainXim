import os
import re
import math
from scipy.special import betainc
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

# 读取txt文件
file_path = 'D:/trans/double-spending_count.txt'  # 请确保这是正确的文件路径
with open(file_path, 'r') as file:
    data = file.read()

# 使用正则表达式提取每组数据的参数和prp_to_confirm字典
pattern = r"chain_num:(\d+),miner_num:(\d+),adver_num:(\d+),attack_type_ds:(\d+),depth:(\d+).*?prp_to_confirm\s*\{(.*?)\}"
matches = re.findall(pattern, data, re.DOTALL)

# 辅助函数
def log_binom(n, k):
    """计算对数二项式系数"""
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

def F_single(t, d, q):
    """计算单链的累积分布函数"""
    if t < d:
        return 0.0
    return betainc(d, t - d + 1, q)

def f_single(t, d, q):
    """计算单链的概率密度函数"""
    if t < d:
        return 0.0
    return math.comb(t - 1, d - 1) * (q ** d) * ((1 - q) ** (t - d))

def p_order(T, m, m_thre, d, q):
    """计算理论概率分布"""
    if T < d:
        return 0.0

    # 计算 P_conf(T) 对应的概率
    P_c = F_single(T, d, q)
    p_c = f_single(T, d, q)

    # 根据新公式计算次序统计量
    coeff = (math.factorial(m) * m_thre) / (math.factorial(m - m_thre + 1) * math.factorial(m_thre - 1))
    P_conf = coeff * (P_c ** (m_thre - 1)) * ((1 - P_c) ** (m - m_thre)) * p_c

    return P_conf

# 遍历每组数据并绘制对比图
for match in matches:
    chain_num = int(match[0])
    miner_num = int(match[1])
    adver_num = int(match[2])
    attack_type_ds = int(match[3])
    depth = int(match[4])
    prp_to_confirm_str = match[5]

    # 提取prp_to_confirm中的T_values
    T_values = [int(val) for val in re.findall(r": (\d+)", prp_to_confirm_str)]

    # 参数设置
    m = chain_num
    n = miner_num
    beta = adver_num / (n - adver_num) if n - adver_num != 0 else 0
    d = depth
    m2 = m + 2
    p = 1 / (256 * m2)  # 每个矿工每轮在每条链上出块的概率
    n_H = n / (1 + beta) if beta != 0 else n
    q = 1 - (1 - p) ** n_H

    # 计算理论值的概率分布
    T_min = min(T_values)
    T_max = max(T_values)
    T_range = range(T_min, T_max + 1)
    m_thre = (m + 1) // 2
    p_theory = [p_order(T, m, m_thre, d, q) for T in T_range]

    # 计算仿真数据的概率分布（归一化频率）
    T_counts = Counter(T_values)
    total_count = len(T_values)
    p_sim = [T_counts.get(T, 0) / total_count for T in T_range]

    # 绘制理论值和仿真值的概率分布
    plt.figure(figsize=(10, 6))

    # 绘制理论值的折线图
    plt.plot(T_range, p_theory, label='theory', color='blue', linestyle='-', linewidth=2)

    # 绘制仿真值的KDE曲线
    sns.kdeplot(T_values, label='simulation', color='red', linewidth=2)

    # 设置图表属性
    plt.xlabel('T')
    plt.ylabel('probability')
    plt.title(f'chain_num={chain_num}')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    # 将图片保存到指定位置
    output_dir = r'C:\Users\luyan\Desktop\东南\周报\工作内容\陆彦_3.9'
    plot_file_name = f"chain_num={chain_num}.jpg"
    full_path = os.path.join(output_dir, plot_file_name)
    plt.savefig(full_path)
    plt.show()