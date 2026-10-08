#!/usr/bin/env python3
"""
Markov Chain 模型描述 Prism 双花攻击过程

状态定义：
  每条链的状态为 (a, h)，a 表示攻击者区块数，h 表示诚实方区块数。
  全局状态为一个包含 3 个链状态的元组：((a₁, h₁), (a₂, h₂), (a₃, h₃))

参数：
  beta: 攻击者与诚实方的算力比例，表示相对出块概率比，即当某链处于“正常”状态时，
        在该链上出块事件中，攻击者区块出现的概率为 beta/(1+beta)，诚实方为 1/(1+beta)

转移规则：
  1. 每一步选择一条链（各 1/3 概率）。
  2. 如果全局确认已经触发（至少 2 条链满足 h>=2）且当前链满足攻击者领先 (a > h)，
     则该链本轮只能出攻击者区块。
  3. 否则，该链按照正常概率产生攻击者区块或诚实方区块：
         - 攻击者：beta/(1+beta)
         - 诚实方：1/(1+beta)
  4. 更新时仅修改所选链，其他链状态保持不变。

终止条件：
  - 攻击成功：全局确认触发（至少 2 条链 h>=2）且有 ≥2 条链满足 a > h
  - 攻击失败：有 ≥2 条链满足 h - a >= 3

当达到终止状态时，我们认为一次攻击周期结束（状态可看作归零，即重置到 ((0,0),(0,0),(0,0))）
"""

from collections import defaultdict, deque


def is_global_confirmation(state):
    """
    判断全局是否已确认，即是否有至少 2 条链上 h >= 2。
    """
    count = sum(1 for (a, h) in state if h >= 2)
    return count >= 2


def check_terminal(state):
    """
    检查当前全局状态是否达到终止条件：
      - 如果有至少 2 条链满足 (h - a) >= 3，则视为攻击失败；
      - 如果全局确认触发且有至少 2 条链满足 a > h，则视为攻击成功；
    返回 'failure'、'success' 或 None（表示未终止）。
    """
    if sum(1 for (a, h) in state if (h - a) >= 3) >= 2:
        return 'failure'
    if is_global_confirmation(state) and (sum(1 for (a, h) in state if a > h) >= 2):
        return 'success'
    return None


def transition(state, beta):
    """
    对于给定状态 state 和参数 beta，返回下一步所有可能状态及其转移概率（字典形式）。

    参数：
      state: 全局状态，形如 ((a1,h1), (a2,h2), (a3,h3))
      beta: 攻击者算力因子

    返回：
      transitions: dict, key 为新状态，value 为转移概率。
    """
    transitions = defaultdict(float)
    confirmed = is_global_confirmation(state)
    # 对于 3 条链，每次只选择其中一条进行更新（均匀选择，每条概率 1/3）
    for i in range(3):
        chain = state[i]
        # 复制当前状态为列表，方便修改当前链 i 的状态
        new_state_list = list(state)
        # 如果全局确认已触发且当前链上攻击者已经领先，则该链只能出攻击者块
        if confirmed and (chain[0] > chain[1]):
            new_chain = (chain[0] + 1, chain[1])
            new_state_list[i] = new_chain
            new_state = tuple(new_state_list)
            transitions[new_state] += (1 / 3) * 1.0
        else:
            # 正常状态：更新分两路：攻击者出块和诚实方出块
            # 攻击者出块：
            new_chain_attacker = (chain[0] + 1, chain[1])
            new_state_list[i] = new_chain_attacker
            new_state_attacker = tuple(new_state_list)
            transitions[new_state_attacker] += (1 / 3) * (beta / (1 + beta))
            # 诚实方出块：
            new_state_list = list(state)  # 重置
            new_chain_honest = (chain[0], chain[1] + 1)
            new_state_list[i] = new_chain_honest
            new_state_honest = tuple(new_state_list)
            transitions[new_state_honest] += (1 / 3) * (1 / (1 + beta))
    return dict(transitions)


def display_transitions(state, beta):
    """
    打印给定状态 state 的所有下一步状态及其转移概率，并标注终止状态（成功或失败）。
    """
    print("当前状态:", state)
    trans = transition(state, beta)
    for next_state, prob in trans.items():
        terminal = check_terminal(next_state)
        term_str = f" 终止状态: {terminal}" if terminal is not None else ""
        print(f" -> 下一状态: {next_state}, 概率: {prob:.4f}{term_str}")


if __name__ == "__main__":
    # 示例：初始状态均为 (0,0)
    beta = 0.5  # 假设攻击者算力比例 β=0.5
    initial_state = ((0, 0), (0, 0), (0, 0))
    print("【单步转移展示】")
    display_transitions(initial_state, beta)


    # 以下代码展示如何利用 BFS 遍历部分状态空间（最大深度可设定），便于观察整个马尔可夫转移过程
    def explore_state_space(initial_state, beta, max_depth=5):
        print("\n【状态空间探索】")
        visited = {}  # state -> depth
        queue = deque([(initial_state, 0)])
        while queue:
            state, depth = queue.popleft()
            if depth > max_depth:
                continue
            if state in visited and visited[state] <= depth:
                continue
            visited[state] = depth
            terminal = check_terminal(state)
            print(f"状态: {state}  深度: {depth}  终止标志: {terminal}")
            # 如果当前状态未终止，则扩展下一步状态
            if terminal is None:
                trans = transition(state, beta)
                for next_state, prob in trans.items():
                    print(f"   -> {next_state}, p = {prob:.4f}, 终止标志: {check_terminal(next_state)}")
                    # 若未到终止状态，则加入队列
                    if check_terminal(next_state) is None:
                        queue.append((next_state, depth + 1))
        return visited


    explore_state_space(initial_state, beta, max_depth=5)
