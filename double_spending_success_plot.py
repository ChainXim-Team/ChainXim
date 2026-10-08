from matplotlib import pyplot as plt

beta = [0.3,0.4,0.5,0.6,0.7,0.8]
# success_rate_theory_up = [0,0.0011,0.0374,0.2893,0.7565,0.9815]
# success_rate_theory_low = [0,0.00041,0.0115,0.08773,0.2885,0.5577]
success_rate_theory_new_up = [5.049046622040969e-05, 0.004601747467948723, 0.07768077147326773, 0.3947377481503975, 0.8232214289422028, 0.9884727406765779]
success_rate_theory_new_down = [3.2295970768955336e-05, 0.00237301971760383, 0.034782246751653444, 0.17861599689570842, 0.4558809217888498, 0.7383053949774838]
success_rate_sim = [0,0,0.16,0.45,0.825,0.9877]
#绘制理论和仿真对比的图
# plt.plot(beta, success_rate_theory_up, 'r--', label='Theoretical_upper', marker='o')
# plt.plot(beta, success_rate_theory_low, 'r--', label='Theoretical_lower', marker='*')
plt.plot(beta, success_rate_sim, 'b-', label='Simulation', marker='o')
plt.plot(beta, success_rate_theory_new_up, 'g-', label='Theoretical_upper', marker='o')
# plt.plot(beta, success_rate_theory_new_down, 'g-', label='Theoretical_lower', marker='*')
plt.xlabel('Beta')
plt.ylabel('Success rate')
plt.legend()
plt.savefig('C:\\Users\\luyan\\Desktop\\东南\\周报\\工作内容\\陆彦_2.23\\ds_success_rate.png')
plt.show()
