import matplotlib.pyplot as plt
import re

# 读取数据文件
file_path = "D:/p.txt"  # 请替换为你的实际文件路径
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 解析数据
rounds = []
probabilities = {}
current_round = None

for line in lines:
    line = line.strip()
    if line.startswith("round:"):
        current_round = int(re.findall(r"\d+", line)[0])
        rounds.append(current_round)
        probabilities[current_round] = []
    elif current_round is not None:
        try:
            probabilities[current_round].append(float(line))
        except ValueError:
            continue

# 计算 p == p_theory 的概率
p_theory = 0.0004  # 你可以修改这个值
prob_match_ratio = []
round_match = []
avg_p_values = []

for r in rounds:
    prob_list = probabilities[r]
    match_count = sum(1 for p in prob_list if abs(p - p_theory) < 1e-6)  # 计算符合条件的数量
    prob_match_ratio.append(match_count / len(prob_list) if prob_list else 0)

    # 计算每个round的出块概率平均值是否等于p_theory
    avg_p = sum(prob_list) / len(prob_list) if prob_list else 0
    round_match.append(1 if abs(avg_p - p_theory) < 1e-6 else 0)
    avg_p_values.append(avg_p)

# 绘制图像
plt.figure(figsize=(10, 5))
plt.plot(rounds, prob_match_ratio, marker='o', linestyle='-', label=f'P(p = {p_theory})')
plt.xlabel("Round")
plt.ylabel("Probability of p = p_theory")
plt.title("Probability Distribution of p = p_theory over Rounds")
plt.legend()
plt.grid()
plt.show()

# 绘制平均值是否等于 p_theory 的图像
plt.figure(figsize=(10, 5))
plt.plot(rounds, round_match, marker='s', linestyle='-', color='r', label=f'Avg(p) == {p_theory}')
plt.xlabel("Round")
plt.ylabel("Match (1 = Yes, 0 = No)")
plt.title("Comparison of Average p and p_theory over Rounds")
plt.legend()
plt.grid()
plt.show()

# 绘制每个round的平均概率 p
plt.figure(figsize=(10, 5))
plt.plot(rounds, avg_p_values, marker='d', linestyle='-', color='b', label='Average p per Round')
plt.axhline(y=p_theory, color='g', linestyle='--', label=f'p_theory = {p_theory}')
plt.xlabel("Round")
plt.ylabel("Average p")
plt.title("Average Block Probability per Round")
plt.legend()
plt.grid()
plt.show()