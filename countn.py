import math
from sympy import nextprime


def compute_p_and_d(n):
    if n < 2:
        raise ValueError("n must be greater than or equal to 2")

    log_n = math.log2(n)
    p_n = nextprime(n ** log_n)
    d_n = math.ceil((math.log2(n)) ** 2)

    return p_n, d_n


# 输入一个整数n
n = int(input("请输入一个整数n (≥ 2): "))
p, d = compute_p_and_d(n)

print(f"对于n = {n}, p(n) = {p}, d(n) = {d}")
