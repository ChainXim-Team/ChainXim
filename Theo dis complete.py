import numpy as np
from scipy.stats import poisson
from scipy.special import gammaln
from numba import jit
import time

class DoubleSpendSolver:
    def __init__(self, N, Ng, n, beta, h=1/1300, m=100, delta=30):
        """
        初始化双花攻击求解器
        """
        self.N = N
        self.Ng = Ng
        self.n = n
        self.beta = beta
        self.alpha = 1 - beta
        self.h = h
        self.m = m
        self.delta = delta
        
        # 计算一轮内的出块概率和期望
        self._compute_lambdas()
        
        # 求解 F_x(k)
        self.F = self._solve_F_system()
    
    def _compute_lambdas(self):
        """计算λ_h和λ_a"""
        honest_trials = self.alpha * self.m * self.delta
        self.lambda_h = 1 - (1 - self.h) ** honest_trials
        self.lambda_a = self.beta * self.m * self.delta * self.h
    
    def _solve_F_system(self):
        """求解差分方程系统"""
        F = np.zeros((self.n + 1, self.Ng + 1))
        
        # 预计算泊松分布PMF
        j_max = self.Ng
        pmf_values = np.zeros(j_max + 1)
        
        if self.lambda_a > 0:
            for j in range(j_max + 1):
                pmf_values[j] = poisson.pmf(j, self.lambda_a)
        else:
            pmf_values[0] = 1.0
        
        # 调用numba加速的核心函数
        F = _solve_F_numba(F, self.n, self.Ng, self.lambda_h, pmf_values, j_max)
        
        return F
    
    def base_state_probability_log(self, H_a, R):
        """计算基态概率的对数形式"""
        min_R = self.N * self.n + self.N
        if R < min_R:
            return -np.inf
        
        # log(C(R-Nn-1, N-1))
        log_comb = (gammaln(R - self.N * self.n) - 
                   gammaln(self.N) - 
                   gammaln(R - self.N * self.n - self.N + 1))
        
        log_honest = (log_comb + 
                     self.N * np.log(self.lambda_h) + 
                     (R - self.N * self.n - self.N) * np.log(1 - self.lambda_h))
        
        log_attack = poisson.logpmf(H_a, R * self.lambda_a)
        
        return log_honest + log_attack
    
    def base_state_probability(self, H_a, R):
        """计算基态概率"""
        log_prob = self.base_state_probability_log(H_a, R)
        if log_prob > -700:
            return np.exp(log_prob)
        return 0.0
    
    def attack_success_probability(self, R_max=5000):
        """计算攻击成功率"""
        min_R = self.N * self.n + self.N
        
        total_failure = 0.0
        
        for H_a in range(self.N):
            k = self.N - H_a
            
            # 失败概率 F_n(k)
            if k <= 0:
                fail_prob = 0.0
            elif k > self.Ng:
                fail_prob = 1.0
            else:
                fail_prob = self.F[self.n, k]
            
            for R in range(min_R, R_max + 1):
                phi = self.base_state_probability(H_a, R)
                if phi > 1e-15:
                    total_failure += phi * fail_prob
        
        return 1.0 - total_failure

# 使用numba加速的核心函数
@jit(nopython=True, cache=False)
def _solve_F_numba(F, n, Ng, lambda_h, pmf_values, j_max):
    """numba加速的F矩阵求解核心"""
    max_iter = 200000
    tolerance = 1e-14
    # 边界条件：只在x=0且k=Ng时失败
    F[0, Ng] = 1.0
    
    for iteration in range(max_iter):
        F_old = F.copy()
        max_diff = 0.0
        
        # 更新延迟期 (x >= 1)
        for x in range(1, n + 1):
            for k in range(1, Ng + 1):
                total = 0.0
                max_j = min(k, j_max)
                for j in range(max_j):
                    total += pmf_values[j] * F[x-1, k-j]
                F[x, k] = total
                diff = abs(F[x, k] - F_old[x, k])
                if diff > max_diff:
                    max_diff = diff
        
        # 更新可出块期 (x = 0)
        for k in range(1, Ng):
            total1 = 0.0
            total2 = 0.0
            
            max_j = min(k, j_max)
            for j in range(max_j + 1):
                pmf = pmf_values[j]
                if pmf == 0:
                    continue
                
                idx = k + 1 - j
                if idx < Ng:
                    total1 += pmf * F[n, idx]
                else:
                    total1 += pmf * 1.0
            
            for j in range(max_j):
                pmf = pmf_values[j]
                if pmf == 0:
                    continue
                total2 += pmf * F[0, k-j]
            
            F[0, k] = lambda_h * total1 + (1 - lambda_h) * total2
            diff = abs(F[0, k] - F_old[0, k])
            if diff > max_diff:
                max_diff = diff
        
        if max_diff < tolerance:
            break
    
    return F

def calculate_success_rates_upper(beta_list, N, Ng, m, lambdaah, delta):
    """计算多个beta值的攻击成功率，返回逗号分隔的字符串"""
    success_rates = []
    
    for beta in beta_list:
        solver = DoubleSpendSolver(N, Ng, m - 1, beta, 1/(lambdaah*100), 100, delta/(m - 1))
        success = solver.attack_success_probability(R_max = 20000)
        success_rates.append(success)
    
    # 返回逗号分隔的字符串
    return ",".join([f"{s:.10f}" for s in success_rates])

def calculate_success_rates_lower(beta_list, N, Ng, m, lambdaah, delta):
    """计算多个beta值的攻击成功率，返回逗号分隔的字符串"""
    success_rates = []
    
    for beta in beta_list:
        solver = DoubleSpendSolver(N, Ng, m - 1, beta, 1/(lambdaah*100), 100, delta/m)
        success = solver.attack_success_probability(R_max = 20000)
        success_rates.append(success)
    
    # 返回逗号分隔的字符串
    return ",".join([f"{s:.10f}" for s in success_rates])

if __name__ == "__main__":
    # 基础参数
    N = 6             # 诚实方区块的确认深度
    Ng = 50           # 攻击方停止攻击的最大落后高度
    m = 10            # 模型精度，即延迟被划分的轮数(额外包含出块轮本身，即第0轮末发送，第m轮开头收到)
    lambdaah = 13     # 全网矿工平均产生一个区块所需要的时间(秒)  平均出块间隔
    delta = 13        # 每个诚实块需要经历的时延长度(秒)
    R_max = 20000
    
    # 输入的攻击者占比alpha列表
    alpha_list = [0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1]
    
    # 计算成功率上下界
    result_upper = calculate_success_rates_upper(alpha_list, N, Ng, m, lambdaah, delta)
    result_lower = calculate_success_rates_lower(alpha_list, N, Ng, m, lambdaah, delta)
    
    # 只输出一行逗号分隔的结果
    print(f"双花攻击成功率上界: {result_upper}")
    print(f"双花攻击成功率下界: {result_lower}")