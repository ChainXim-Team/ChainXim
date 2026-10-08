import numpy as np
import sympy as sp

# Define symbolic variables
delta, alpha, beta, propagation_delay, k, eta, mu, safety_threshold = sp.symbols(
    'delta alpha beta propagation_delay k eta mu safety_threshold', positive=True
)

# Constants based on given values
# 参数
result = 1e-3  # Target result
alpha_value = 6  # Honest block rate: 1 block per 600 seconds
beta_value = 2  # Adversarial block rate: 2 blocks per hour
propagation_delay_value = 1 / 3600  # 2 seconds propagation delay
# safety_threshold_value = 1 - 10**-20  # Safety threshold
delta_value = 0.3285  # Example δ value

# Define g and calculate g value
g = sp.exp(-alpha * propagation_delay)
g_value = g.subs({alpha: alpha_value, propagation_delay: propagation_delay_value})
print(f'g:{g_value}')

# Solve for δ range using Equation (7)
delta_range = (1 - beta_value / (g_value ** 2 * alpha_value)) / (81 / 40)
# delta_range = sp.solve(ineq_delta.subs({alpha: alpha_value, beta: beta_value, propagation_delay: propagation_delay_value}), delta)
print(f"Range for δ: {delta_range}")

# Calculate η using Equation (97): η = δ²g2α
eta_value = delta_range**2 * g_value ** 2 * alpha_value
print(f"Value of η: {float(eta_value):.6f}")


# Calculate μ using Equation (137): μ = 9e^(2η/27) / (1 - e^(-η/27))²
mu_value = 9 * sp.exp(2 * eta_value / 27) / ((1 - sp.exp(-eta_value / 27))**2)
print(f"Value of μ: {float(mu_value):.6f}")

# Solve for minimum k using k > 160α(1+Δ)/δ
k_min_value = 160 * alpha_value * (1 + propagation_delay_value) / delta_value
print(f"Minimum k: {k_min_value:.6f}")

# mu_value = 201.8
# # Solve for k to achieve safety threshold
# safety_eq = 1 - mu_value * sp.exp(-eta_value / 27 * (k / (2 * alpha_value) - 2 * propagation_delay_value)) - safety_threshold_value
# k_safety_solution = sp.solve(safety_eq, k)
#
# if k_safety_solution:
#     print(f"Required k for safety threshold: {float(k_safety_solution[0]):.2f}")
# else:
#     print("No solution found for k that satisfies the safety threshold.")


def compute_mu_eta_expression(k, delta, alpha, propagation_delay):
    """
    Compute μ * exp(-η / 27 * (k / (2α) - 2Δ)).

    Parameters:
        k (float): The depth of the blockchain.
        delta (float): The parameter δ satisfying the inequality.
        alpha (float): The honest block rate (blocks per second).
        propagation_delay (float): The block propagation delay (seconds).

    Returns:
        float: The value of μ * exp(-η / 27 * (k / (2α) - 2Δ)).
    """
    # Compute g
    g = np.exp(-alpha * propagation_delay)

    # Compute η
    eta = delta ** 2 * g * 2 * alpha
    eta = 0.643171

    # Compute μ
    mu = 9 * np.exp(2 * eta / 27) / ((1 - np.exp(-eta / 27)) ** 2)
    mu = 16691.219259

    # Compute the exponential part
    exp_part = np.exp(-eta / 27 * (k / (2 * alpha) - 2 * propagation_delay))

    # Compute the final result
    result = mu * exp_part
    return result


# # Example parameters
# k = 26000  # Depth of the blockchain
# delta = 0.328117047184523  # Example δ value
# alpha = 6  # Honest block rate: 1 block per 600 seconds
# propagation_delay = 2/3600  # 2 seconds propagation delay
#
# # Compute the result
# result = compute_mu_eta_expression(k, delta, alpha, propagation_delay)
# print(f"Result for μ * exp(-η / 27 * (k / (2α) - 2Δ)): {result:.6e}")



# delta = 0.328117047184523  # Example δ value
# alpha = 6  # Honest block rate
# propagation_delay = 2 / 3600  # 2 seconds propagation delay
#
# # 计算 g, η, μ
# g = np.exp(-alpha * propagation_delay)
# # eta = delta**2 * g * 2 * alpha
# eta = eta_value
# # mu = 9 * np.exp(2 * eta / 27) / ((1 - np.exp(-eta / 27))**2)
# mu = int(mu_value)
#
# # 反推 k 的公式
# log_term = np.log(result / mu)
# k = 2 * alpha * (2 * propagation_delay - (27 / eta) * log_term)
#
# # 打印结果
# print(f"Solved k for given result: {k:.2f}")




