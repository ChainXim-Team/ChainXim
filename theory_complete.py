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
        F = np.zeros((self.n + 1, self.Ng))
        
        # 预计算泊松分布PMF
        j_max = self.Ng - 1
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
    
    # def base_state_probability_log(self, H_a, R):
    #     """计算基态概率的对数形式（修改后：去掉一个时延阶段）"""
    #     min_R = self.N * self.n + self.N  # 注意：这里需要根据新逻辑重新考虑
        
    #     if R < min_R:
    #         return -np.inf
        
    #     # 组合数部分：log(C(R - (N-1)n - 1, N-1))
    #     log_comb = (gammaln(R - (self.N - 1) * self.n) - 
    #             gammaln(self.N) - 
    #             gammaln(R - (self.N - 1) * self.n - self.N + 1))
        
    #     # 诚实链部分：N个块，剩余轮数为 R - N - (N-1)n
    #     log_honest = (log_comb + 
    #                 self.N * np.log(self.lambda_h) + 
    #                 (R - self.N - (self.N - 1) * self.n) * np.log(1 - self.lambda_h))
        
    #     # 攻击者部分保持不变：泊松分布
    #     log_attack = poisson.logpmf(H_a, R * self.lambda_a)
        
    #     return log_honest + log_attack
    
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
            elif k >= self.Ng:
                fail_prob = 1.0
            else:
                fail_prob = self.F[self.n, k]
            
            for R in range(min_R, R_max + 1):
                phi = self.base_state_probability(H_a, R)
                if phi > 1e-15:
                    total_failure += phi * fail_prob
        
        return 1.0 - total_failure

# 使用numba加速的核心函数
@jit(nopython=True, cache=True)
def _solve_F_numba(F, n, Ng, lambda_h, pmf_values, j_max):
    """numba加速的F矩阵求解核心"""
    max_iter = 300000
    tolerance = 1e-12
    
    for iteration in range(max_iter):
        F_old = F.copy()
        max_diff = 0.0
        
        # 更新延迟期 (x >= 1)
        for x in range(1, n + 1):
            for k in range(1, Ng):
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

def calculate_success_rates(beta_list, N=6, Ng=6, n=1, h=1/1300, m=100, delta=5, R_max=5000):
    """计算多个beta值的攻击成功率，返回逗号分隔的字符串"""
    success_rates = []
    
    for beta in beta_list:
        solver = DoubleSpendSolver(N, Ng, n, beta, h, m, delta)
        success = solver.attack_success_probability(R_max)
        success_rates.append(success)
    
    # 返回逗号分隔的字符串
    return ",".join([f"{s:.10f}" for s in success_rates])

if __name__ == "__main__":
    # 基础参数
    N = 6
    Ng = 50
    n = 50  # 延迟轮数
    h = 1/1300
    m = 100
    delta = 5/50  # 单轮时间间隔
    R_max = 12000
    
    # 输入的beta列表
    beta_list = [0.45, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1]
    
    # 计算成功率
    result = calculate_success_rates(beta_list, N, Ng, n, h, m, delta, R_max)
    
    # 只输出一行逗号分隔的结果
    print(result)