import matplotlib.pyplot as plt
import numpy as np

# 文件路径
file_path = 'D:/mthre_impact.txt'


def parse_file(file_path):
    data = {}

    with open(file_path, 'r') as f:
        lines = f.readlines()

    m_thre = None  # 当前的 m_thre
    beta = None  # 当前的 beta

    for line in lines:
        line = line.strip()  # 移除首尾空白字符

        # 调试输出
        print(f"Processing line: {line}")

        # 解析 m_thre
        if line.startswith("m_thre:"):
            m_thre = int(line.split(":")[1].strip())
            if m_thre not in data:
                data[m_thre] = {'betas': {}, 'T': [], 'ups': [], 'downs': []}
            print(f"Found m_thre: {m_thre}")

        # 解析 beta
        elif line.startswith("beta:"):
            beta = float(line.split(":")[1].strip())
            if beta not in data[m_thre]['betas']:
                data[m_thre]['betas'][beta] = {'ups': [], 'downs': []}
            print(f"Found beta: {beta}")

        # 解析 T
        elif line.startswith("T:"):
            T = int(line.split(":")[1].strip())
            data[m_thre]['T'].append((beta, T))  # 将 (beta, T) 配对加入
            print(f"Found T: {T} for beta: {beta}")

        # 解析 ups
        elif line.startswith("ups:"):
            ups = eval(line.split(":")[1].strip())  # 将字符串转换为列表
            data[m_thre]['betas'][beta]['ups'] = ups
            print(f"Found ups: {ups} for beta: {beta}")

        # 解析 downs
        elif line.startswith("downs:"):
            downs = eval(line.split(":")[1].strip())  # 将字符串转换为列表
            data[m_thre]['betas'][beta]['downs'] = downs
            print(f"Found downs: {downs} for beta: {beta}")

    return data


# 解析文件
data = parse_file(file_path)

# 打印数据结构
print(data)


# 绘图函数
def plot_graphs(data):
    m_thres = sorted(data.keys())
    betas = sorted(next(iter(data.values()))['betas'].keys())  # 获取所有的 beta

    # 图1：T vs m_thre（单条曲线）
    plt.figure(figsize=(10, 6))

    # 提取 m_thre 和对应的 T 值
    m_thres = sorted(data.keys())  # 所有 m_thre 值，按升序排列
    T_values = [data[m_thre]['T'][0][1] for m_thre in m_thres]  # 取每个 m_thre 下的第一个 T 值

    # 绘制曲线
    plt.plot(m_thres, T_values, marker='o', label='T vs m_thre')  # 用 marker='o' 表示数据点

    plt.xlabel('m_thre')
    plt.ylabel('T')
    plt.title('T vs m_thre')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 图2：ups vs m_thre，按 beta 区分
    plt.figure(figsize=(10, 6))
    for beta in betas:
        ups_values = [data[m_thre]['betas'][beta]['ups'][0] for m_thre in m_thres]
        plt.plot(m_thres, ups_values, label=f'beta = {beta}', marker='x')

    plt.xlabel('m_thre')
    plt.ylabel('ups')
    plt.title('ups vs m_thre for different beta values')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 图3：downs vs m_thre，按 beta 区分
    plt.figure(figsize=(10, 6))
    for beta in betas:
        downs_values = [data[m_thre]['betas'][beta]['downs'][0] for m_thre in m_thres]
        plt.plot(m_thres, downs_values, label=f'beta = {beta}', marker='o')

    plt.xlabel('m_thre')
    plt.ylabel('downs')
    plt.title('downs vs m_thre for different beta values')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


# 调用绘图函数
plot_graphs(data)