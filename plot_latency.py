from matplotlib import pyplot as plt

m = [11,21,31,41,51,61]
# latency_theory = [452,795,1137,1480,1822]
# latency_sim = [453,805,1135,1479,1826]
# latency_paper = [2914,5148,7383,9617,11851]
latency_theory = [1295,2667,4174,5762,7427,9127]
latency_bound_paper = [3098,5476,7855,10233,12611,14990]
latency_bound_prism = [2717,4805,6892,8980,11068,13155]
#绘制理论和仿真对比的图,bin
# 计算平均斜率
# slope_theory = (latency_theory[-1] - latency_theory[0]) / (m[-1] - m[0])
# print(slope_theory)
# slope_sim = (latency_sim[-1] - latency_sim[0]) / (m[-1] - m[0])
# print(slope_sim)

# # 计算延伸到 y=0 的位置
# x_intercept_theory = -latency_theory[0] / slope_theory + m[0]
# x_intercept_sim = -latency_sim[0] / slope_sim + m[0]

# 绘制理论和仿真对比的图，用实线和虚线表示
plt.plot(m, latency_theory, 'r--', label='latency_theory', marker='o')
plt.plot(m, latency_bound_paper, 'b-', label='latency_bound_paper', marker='o')
plt.plot(m, latency_bound_prism, 'g-', label='latency_bound_prism', marker='o')

# 绘制延伸线
# plt.plot([0, m[-1]], [0, slope_theory * (m[-1] - x_intercept_theory)], 'r--', label='Theoretical Extension')
# plt.plot([0, m[-1]], [0, slope_sim * (m[-1] - x_intercept_sim)], 'b--', label='Simulation Extension')

# plt.ylim(0, 2000)
plt.xlim(10, 52)
plt.xlabel('Number of chains')
plt.ylabel('Confirmation latency')
plt.legend()
plt.savefig('C:\\Users\\luyan\\Desktop\\东南\\周报\\工作内容\\陆彦_2.23\\latency_compare_bound.png')
plt.show()

