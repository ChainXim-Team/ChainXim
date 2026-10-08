#!/usr/bin/env python3
"""
利用理论推导计算双花攻击成功率

参数说明：
  - BETA : 攻击者与诚实方的算力比例 β
  - M    : 投票者链的总数
  - N_G  : 攻击者允许落后诚实方的最大区块数（Ng，即单链失守的阈值）

单链上攻击者最终控制该链的概率 f 由下式给出：
  若 β ≠ 1:
      f = (1 - (1/β)^N_G) / (1 - (1/β)^(N_G+1))
  若 β = 1:
      f = N_G / (N_G+1)

整体攻击成功率要求攻击者在 M 条链中至少获得 T = floor(M/2)+1 条链的控制，
即：
      P_attack = sum_{k=T}^{M} binom(M, k)*f^k*(1-f)^(M-k)
"""

import math


def compute_single_chain_probability(beta, N_G):
    """
    计算单链上攻击者最终获得控制权（吸收到上界 x=1）的概率 f.
    """
    # 当 beta 接近 1 时采用对称情况的公式
    if abs(beta - 1.0) < 1e-8:
        f = N_G / (N_G + 1)
    else:
        f = (1 - (1 / beta) ** (N_G)) / (1 - (1 / beta) ** (N_G + 1))
    return f


def compute_attack_probability(beta, M, N_G):
    """
    计算整体双花攻击成功率。

    参数：
      beta : 攻击者与诚实方的算力比例 β
      M    : 投票者链的总数
      N_G  : 单链失守的阈值 (攻击者最大允许落后数)

    返回：
      f         : 单链上攻击者获胜的概率
      attack_p  : 在 M 条链中，至少 T = floor(M/2)+1 条链获胜的总体成功率
    """
    f = compute_single_chain_probability(beta, N_G)
    T = M // 2 + 1  # 至少需要获得的链数
    attack_p = 0.0
    for k in range(T, M + 1):
        attack_p += math.comb(M, k) * (f ** k) * ((1 - f) ** (M - k))
    return f, attack_p


def main():
    # -------------------------------
    # 参数设置（可修改）
    # -------------------------------
    BETA = 0.5  # 攻击者与诚实方的算力比例 β（例如 0.5 表示攻击者算力为 50%）
    M = 3  # 投票者链的总数
    N_G = 3  # 单链中，攻击者允许落后诚实方的最大区块数 Ng

    # -------------------------------
    # 计算双花攻击成功率
    # -------------------------------
    f, attack_probability = compute_attack_probability(BETA, M, N_G)

    # 输出结果
    print("参数设置:")
    print("  攻击者与诚实方比例 β = {}".format(BETA))
    print("  投票者链总数 M = {}".format(M))
    print("  单链失守阈值 N_G = {}".format(N_G))
    print("")
    print("单链上攻击者最终获胜概率 f = {:.6f}".format(f))
    print("总体双花攻击成功率 P_attack = {:.6f}".format(attack_probability))


if __name__ == "__main__":
    main()
