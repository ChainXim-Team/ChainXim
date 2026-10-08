# import sympy as sp
# import itertools
# import numpy as np
# import hashlib
#
#
# def ovk(k, n, d, p, U):
#     """
#     计算f_OVk_n,d,p(U1, ..., Uk)的值
#     参数:
#     k - 向量集合的数量
#     n - 每个向量集合中的向量数量
#     d - 向量的维度
#     p - 质数，用于模运算
#     U - 输入向量集合的列表，包含k个(n, d)的SymPy矩阵
#     返回:
#     f_OVk_n,d,p的值
#     """
#     if len(U) != k:
#         raise ValueError(f"输入的向量集合数量不正确，期望{k}个集合，但得到了{len(U)}个")
#
#     for idx, U_s in enumerate(U):
#         if U_s.shape != (n, d):
#             raise ValueError(f"输入的第{idx + 1}个向量集合尺寸不正确，期望{(n, d)}，但得到了{U_s.shape}")
#
#     result = 0
#     # 遍历所有可能的索引组合
#     for indices in itertools.product(*[range(n)] * k):
#         product = 1
#         for l in range(d):
#             coordinate_product = 1
#             for s in range(k):
#                 coordinate_product *= U[s][indices[s], l]
#             product *= (1 - coordinate_product) % p
#             product %= p
#         result += product
#
#     return result
#
#
# # 定义多项式 f_{OVk, n, d, p} 的函数
# def f_ovk(U, n, d, k, p):
#     x = sp.symbols('x')
#     phi = []
#
#     # 对于每个 U_s，生成插值多项式 \phi_{s\ell}
#     for s in range(k):
#         U_s = U[s]
#         phi_s = []
#         for l in range(d):
#             us_l = [U_s[i, l] for i in range(n)]
#             phi_s_l = sp.interpolate(list(enumerate(us_l, 1)), x)
#             phi_s.append(phi_s_l)
#         phi.append(phi_s)
#
#     # 计算 q(i_1, ..., i_k)
#     def q(indices):
#         prod = 1
#         for l in range(d):
#             term = 1
#             for s in range(k):
#                 term *= phi[s][l].subs(x, indices[s])
#             prod *= (1 - term)
#         return prod
#
#     # 动态生成所有索引组合并计算 f_{OVk, n, d, p}
#     sum_q = 0
#     for indices_tuple in itertools.product(range(1, n + 1), repeat=k):
#         sum_q += q(indices_tuple)
#
#     return sum_q % p
#
#
# # 计算 q1 的系数
# def compute_q1_coeffs(phi, n, d, k):
#     x = sp.symbols('x')
#
#     def q(indices):
#         prod = 1
#         for l in range(d):
#             term = 1
#             for s in range(k):
#                 term *= phi[s][l].subs(x, indices[s])
#             prod *= (1 - term)
#         return prod
#
#     q1 = 0
#     for i2 in range(0,k-1):
#         q1 += q((x, i2))
#     q1 = sp.simplify(q1)
#     return sp.Poly(q1, x).all_coeffs()
#
#
# # 计算 q_s+1 的系数
# def compute_qs_coeffs(alpha_vals, s, phi, n, d, k):
#     x = sp.symbols('x')
#
#     def q(indices):
#         prod = 1
#         for l in range(d):
#             term = 1
#             for s in range(k):
#                 term *= phi[s][l].subs(x, indices[s])
#             prod *= (1 - term)
#         return prod
#
#     q_s = 0
#     for indices in itertools.product(range(1, n + 1), repeat=k - s - 1):
#         indices = alpha_vals + [x] + list(indices)
#         q_s += q(indices)
#     q_s = sp.simplify(q_s)
#     return sp.Poly(q_s, x).all_coeffs()
#
#
# # 非交互式有用工作证明
# # 非交互式有用工作证明
# def solve(cx, n, d, k, p):
#     T = []
#     z_values = []
#     for y_set in cx:
#         x = sp.symbols('x')
#         phi = []
#
#         # 对于每个 U_s，生成插值多项式 \phi_{s\ll}
#         for s in range(k):
#             U_s = y_set[s]
#             phi_s = []
#             for l in range(d):
#                 us_l = [U_s[i, l] for i in range(n)]
#                 phi_s_l = sp.interpolate(list(enumerate(us_l, 1)), x)
#                 phi_s.append(phi_s_l)
#             phi.append(phi_s)
#
#         zy = f_ovk(y_set, n, d, k, p)
#         z_values.append(zy)
#         qy1_coeffs = compute_q1_coeffs(phi, n, d, k)
#         qy1 = sp.Poly(qy1_coeffs, x)
#         τys = [zy, qy1]
#         alpha_vals = []
#
#         for s in range(1, k):
#             αys = int(hashlib.sha256(str((cx, *τys)).encode()).hexdigest(), 16) % p
#             alpha_vals.append(αys)
#             qys_plus_1_coeffs = compute_qs_coeffs(alpha_vals, s, phi, n, d, k)
#             qys_plus_1 = sp.Poly(qys_plus_1_coeffs, x)
#             τys.append(qys_plus_1)
#
#         T.append(τys)
#     print('in solve get T:')
#     print(T)
#     print('in solve get z_values:')
#     print(z_values)
#     return T, z_values
#
#
#
# # 验证非交互式有用工作证明
# def verify(cx, T, n, d, k, p):
#     def q(indices, phi):
#         x = sp.symbols('x')
#         prod = 1
#         for l in range(d):
#             term = 1
#             for s in range(k):
#                 term *= phi[s][l].subs(x, indices[s])
#             prod *= (1 - term)
#         return prod
#
#     for τy in T:
#         # 解析 τy 列表
#         zy = τy[0]
#         qy1 = τy[1]
#         qys = τy[1:]
#
#         sum_qy1 = sum(qy1.eval(i) for i in range(1, n + 1)) % p
#
#         if sum_qy1 != zy:
#             return False
#
#         αy1 = int(hashlib.sha256(str((cx, zy, qy1)).encode()).hexdigest(), 16) % p
#         alpha_vals = [αy1]
#         for s in range(1, k):
#             αys = int(hashlib.sha256(str((cx, zy, *qys[:s])).encode()).hexdigest(), 16) % p
#             alpha_vals.append(αys)
#             qys_plus_1 = qys[s]
#             sum_qys_plus_1 = sum(qys_plus_1.eval(i) for i in range(1, n + 1)) % p
#             qys_at_αys = qys[s - 1].eval(αys) % p
#             if sum_qys_plus_1 != qys_at_αys:
#                 return False
#     print('verify confirmed')
#     return True
#
#
#
#
# # 重建答案
# def recon(s, kd):
#     t = sp.symbols('t')
#     points = [(i, float(y)) for i, y in enumerate(s, 1)]
#     h = sp.interpolate(points, t)
#     z = h.evalf(subs={t: 0})
#     # return 1 if z != 0 else 0
#     return z
#
# # 示例参数
# n = 4
# k = 2
# d = 4
# kd = k * d
# p = 17
#
# # 构造包含0和1的示例矩阵集合 x
# U1 = sp.Matrix([[1, 0, 0, 1], [1, 0, 1, 0], [1, 1, 0, 0], [1, 1, 1, 0]])
# U2 = sp.Matrix([[1, 0, 0, 1], [1, 0, 1, 0], [1, 1, 0, 0], [1, 1, 1, 0]])
# x = [U1,U2
#      ]
#
# r = [sp.Matrix(np.random.randint(0, 2, (n, d))) for _ in range(k)]
#
# # 打印生成的输入矩阵集合 x
# print("Input matrices x:")
# for i, x_i in enumerate(x, 1):
#     print(f"x_{i}:")
#     sp.pretty_print(x_i)
#     print()
#
# # 生成 cx
# cx = []
# for t in range(1, kd + 2):
#     x_t = [(x_i + t * r_i) % 2 for x_i, r_i in zip(x, r)]
#     cx.append(x_t)
#
# for i, cx_i in enumerate(cx, 1):
#     print(f"cx_{i}:")
#     sp.pretty_print(cx_i)
#     print()
#
# # 计算 s
# T, s = solve(cx, n, d, k, p)
#
# # 验证 s
# is_valid = verify(cx, T, n, d, k, p)
#
# # 重构结果
# result = recon(s, kd) % p
#
# print("cx:", cx)
# print("s:", s)
# print("Is valid:", is_valid)
# print("Result:", result)
#
# fov = ovk(k,n,d,p,x)
# print("fov:", fov)
#
# import os

# def write_project_structure_to_txt(project_path, output_file):
#     with open(output_file, 'w', encoding='utf-8') as f:
#         for root, dirs, files in os.walk(project_path):
#             level = root.replace(project_path, '').count(os.sep)
#             indent = ' ' * 4 * (level)
#             f.write(f'{indent}{os.path.basename(root)}/\n')
#             subindent = ' ' * 4 * (level + 1)
#             for file in files:
#                 f.write(f'{subindent}{file}\n')
#                 file_path = os.path.join(root, file)
#                 try:
#                     with open(file_path, 'r', encoding='utf-8', errors='ignore') as file_content:
#                         content = file_content.read()
#                         content_lines = content.splitlines()
#                         for line in content_lines:
#                             f.write(f'{subindent}{line}\n')
#                 except Exception as e:
#                     f.write(f'{subindent}Error reading file: {e}\n')

# # 示例调用
# project_path = 'C:/Users/luyan/Desktop/chain/chainnew/chain-xim-master0611'  # 替换为你的PyCharm项目路径
# output_file = 'C:/Users/luyan/Desktop/chain/chainnew/chain-xim-master0611/output_project_structure.txt'
# write_project_structure_to_txt(project_path, output_file)
# import hashlib
# import time
# import random
# import string

# # 生成一个随机字符串
# random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=100))
#
# # 记录哈希计算开始时间
# start_time = time.time()
#
# # 进行SHA-256哈希计算
# hash_object = hashlib.sha256(random_string.encode())
# hash_hex = hash_object.hexdigest()
#
# # 记录哈希计算结束时间
# end_time = time.time()
#
# # 输出哈希值和用时
# print(f"Random String: {random_string}")
# print(f"SHA-256 Hash: {hash_hex}")
# print(f"Hash computation time: {end_time - start_time:.12f} seconds")


from decimal import Decimal, getcontext


def hex_to_scaled_hex(hex_str, m, n):
    """Scale a hexadecimal PoW target for ``m`` chains and ``n`` miners.

    The scale factor ``(m + 2) / (1000 * n)`` makes the expected block
    probability per chain per round equal to 0.001 when every miner performs
    one hash attempt per round.
    """
    if n <= 0:
        raise ValueError("n must be greater than 0")
    if m < 0:
        raise ValueError("m must be non-negative")

    # A 256-bit hexadecimal value has about 78 decimal digits.
    getcontext().prec = 100
    decimal_value = Decimal(int(hex_str, 16))
    scale_factor = Decimal(m + 2) / Decimal(1000 * n)
    scaled_int = int(decimal_value * scale_factor)
    scaled_hex_str = format(scaled_int, "X")
    return scaled_hex_str.zfill(len(hex_str))


if __name__ == "__main__":
    input_hex = "F" * 64
    result = hex_to_scaled_hex(input_hex, m=11, n=10)
    print(f"输入: {input_hex}")
    print(f"结果: {result}")
