#绘制双花攻击成功概率仿真值和理论值的对比图
import matplotlib.pyplot as plt
import numpy as np
import math

adversary_ratio = [0.4, 0.5, 0.6, 0.7, 0.8]
success_simulation = [0.018648, 0.060606, 0.151898,  0.337542 ,0.537142]
success_theory = [0.0221, 0.1025, 0.2641, 0.4699, 0.584]

plt.plot(adversary_ratio, success_simulation, marker='o', label='Simulation')
plt.plot(adversary_ratio, success_theory, marker='x', label='Theory')
plt.xlabel('Adversary Ratio')
plt.ylabel('Success Probability')
plt.legend()
plt.show()

