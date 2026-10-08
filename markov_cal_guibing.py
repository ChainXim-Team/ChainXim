#!/usr/bin/env python3
"""
利用马尔可夫链状态转移模拟 Prism 双花攻击过程

每条链状态记为 (a, h)，其中：
    a：攻击者在该链上挖到的区块数
    h：诚实方在该链上挖到的区块数
全局状态用一个长度为 M 的元组表示：((a₁, h₁), (a₂, h₂), ..., (a_M, h_M))

【重要参数】（在程序开始处统一设置）：
    BETA              : 攻击者与诚实方比例 β
    M                 : 链的总数
    CONFIRM_DEPTH     : 确认深度 N，即当某链上 h ≥ CONFIRM_DEPTH 时认为该链确认
    ATTACKER_MAX_TRAIL: 攻击者最大允许落后数量 Ng，即当 (h - a) ≥ ATTACKER_MAX_TRAIL 时，该链失守
    EPSILON           : 暂态状态累计概率质量的截止容差

【转移规则】：
  1. 每一步从 M 条链中随机选一条（均匀概率 1/M）。
  2. 如果全局确认触发（定义为至少 (M//2 + 1) 条链满足 h ≥ CONFIRM_DEPTH）且所选链中攻击者已领先（a > h），
     则该链本轮只能出攻击者区块。
  3. 否则，在该链上分别有：
         - 攻击者区块：概率 = β/(1+β)
         - 诚实方区块：概率 = 1/(1+β)
  4. 仅更新所选链，其余链状态保持不变。

【终止条件】：
  - 攻击成功：当全局确认触发（至少 (M//2 + 1) 条链满足 h ≥ CONFIRM_DEPTH）且至少 (M//2 + 1) 条链满足 a > h；
  - 攻击失败：当至少 (M//2 + 1) 条链满足 (h - a) ≥ ATTACKER_MAX_TRAIL。

一旦达到终止状态，无论成功还是失败，都视为一次攻击周期结束。

遍历过程中会实时打印当前深度、遇到的终止状态以及当前累计的成功率和失败率。
"""

from collections import defaultdict

# ==========================
#  参数设置
# ==========================
BETA = 4/6  # 攻击者与诚实方比例 β
M = 3  # 链的总数
CONFIRM_DEPTH = 2  # 确认深度 N (例如设置为 2，即当 h >= 2 时认为该链确认)
ATTACKER_MAX_TRAIL = 100  # 攻击者最大允许落后数量 Ng (例如设置为 3，即当 h - a >= 3 时，该链失守)
EPSILON = 1e-12  # 暂态状态累计概率质量的截止容差


# ==========================
#  状态与终止判断函数
# ==========================
def is_global_confirmation(state):
    """
    判断全局确认：若至少 (M//2 + 1) 条链上 h >= CONFIRM_DEPTH，则视为全局确认
    """
    count = sum(1 for (a, h) in state if h >= CONFIRM_DEPTH)
    return count >= (M // 2 + 1)


def check_terminal(state):
    """
    判断状态是否为终止状态：
      - 若至少 (M//2 + 1) 条链满足 (h - a) >= ATTACKER_MAX_TRAIL，则攻击失败；
      - 若全局确认触发且至少 (M//2 + 1) 条链满足 a > h，则攻击成功；
    返回：
      'failure' 表示攻击失败，
      'success' 表示攻击成功，
      否则返回 None 表示状态仍为暂态。
    """
    if sum(1 for (a, h) in state if (h - a) >= ATTACKER_MAX_TRAIL) >= (M // 2 + 1):
        return 'failure'
    if is_global_confirmation(state) and (sum(1 for (a, h) in state if a > h) >= (M // 2 + 1)):
        return 'success'
    return None


# ==========================
#  状态转移函数
# ==========================
def transition(state, beta):
    """
    给定状态 state 和参数 beta，返回下一步可能状态及其转移概率（不含前因累计概率）。

    每一步：
      - 从 M 条链中均匀选择一条（概率 1/M）；
      - 如果全局确认触发且该链满足 (a > h)，则该链本轮只能出攻击者块；
      - 否则，该链分别有攻击者块（概率 β/(1+β)）和诚实方块（概率 1/(1+β)）两种转移。

    仅更新所选链，其他链状态保持不变。
    返回：
       一个 dict，键为下一状态，值为该转移概率。
    """
    transitions = defaultdict(float)
    confirmed = is_global_confirmation(state)
    for i in range(M):
        chain = state[i]
        new_state_list = list(state)
        if confirmed and (chain[0] > chain[1]) and (chain[0] >= CONFIRM_DEPTH):
            # 当前链只能出攻击者块
            new_chain = (chain[0] + 1, chain[1])
            new_state_list[i] = new_chain
            new_state = tuple(new_state_list)
            transitions[new_state] += (1 / M) * 1.0
        else:
            # 两种可能：攻击者出块或诚实方出块
            # 攻击者出块
            new_state_list[i] = (chain[0] + 1, chain[1])
            new_state_attacker = tuple(new_state_list)
            transitions[new_state_attacker] += (1 / M) * (beta / (1 + beta))
            # 诚实方出块
            new_state_list = list(state)  # 重置为原状态
            new_state_list[i] = (chain[0], chain[1] + 1)
            new_state_honest = tuple(new_state_list)
            transitions[new_state_honest] += (1 / M) * (1 / (1 + beta))
    return dict(transitions)


# ==========================
#  马尔可夫链遍历函数
# ==========================
def explore_markov_chain(initial_state, beta, epsilon=EPSILON):
    """
    从初始状态 initial_state 出发，遍历整个马尔可夫状态转移过程，
    直到所有概率质量都被吸收到终止状态（成功或失败）。
    每一路径的概率为沿途转移概率的乘积。

    在遍历过程中，实时打印当前深度，每次遇到终止状态时打印该状态及其概率，
    同时打印当前累计的成功率和失败率。

    返回：
       terminal_results: dict, 键 'success' 和 'failure' 对应的累计概率
       detailed_paths: dict, 键为 (终止状态, 终止类型)，值为累计概率
    """
    transient = {initial_state: 1.0}  # 暂态状态字典： state -> 累计概率
    terminal_results = {'success': 0.0, 'failure': 0.0}
    detailed_paths = defaultdict(float)  # 记录每个终止状态（及其类型）的累计概率

    iteration = 0
    while transient:
        print(f"\n当前深度（iteration）: {iteration}")
        new_transient = defaultdict(float)
        for state, prob in transient.items():
            next_states = transition(state, beta)
            for next_state, trans_prob in next_states.items():
                new_prob = prob * trans_prob
                terminal_flag = check_terminal(next_state)
                if terminal_flag is not None:
                    terminal_results[terminal_flag] += new_prob
                    detailed_paths[(next_state, terminal_flag)] += new_prob
                    # 打印终止状态信息
                    print(
                        f"  深度 {iteration + 1}: 遇到终止状态 {next_state}, 类型: {terminal_flag}, 路径概率: {new_prob:.12f}")
                    print(
                        f"      当前累计成功率: {terminal_results['success']:.12f}, 累计失败率: {terminal_results['failure']:.12f}")
                else:
                    new_transient[next_state] += new_prob
        total_transient_prob = sum(new_transient.values())
        print(f"深度 {iteration + 1} 完成: 暂态状态总概率 = {total_transient_prob:.12f}")
        if total_transient_prob < epsilon:
            print("暂态状态总概率低于截止容差，遍历结束。")
            break
        transient = dict(new_transient)
        iteration += 1
    return terminal_results, detailed_paths


# ==========================
#  主程序入口
# ==========================
if __name__ == "__main__":
    # 初始状态：所有链均从 (0,0) 开始
    initial_state = tuple((0, 0) for _ in range(M))

    print("初始状态:", initial_state)
    print("参数设置: BETA =", BETA, ", M =", M,
          ", CONFIRM_DEPTH =", CONFIRM_DEPTH,
          ", ATTACKER_MAX_TRAIL =", ATTACKER_MAX_TRAIL)

    terminal_results, detailed_paths = explore_markov_chain(initial_state, BETA, EPSILON)

    print("\n最终各终止情况的累计概率:")
    for result_type, prob in terminal_results.items():
        print(f"  {result_type}: {prob:.12f}")

    print("\n详细终止路径 (状态, 终止类型) 及其概率:")
    for (state, result), prob in detailed_paths.items():
        print(f"  状态: {state}, 终止类型: {result}, 概率: {prob:.12f}")
