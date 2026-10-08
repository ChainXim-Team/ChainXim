import math

def poisson_cumulative_probability(beta, t_start, t_end, a):
    """
    Calculate the lower bound of P(Z_t - Z_s <= a) based on a Poisson distribution.

    Parameters:
        beta (float): Adversarial mining rate.
        t_start (float): Start time of the interval.
        t_end (float): End time of the interval.
        a (int): The threshold value for the number of adversarial blocks.

    Returns:
        float: The lower bound probability.
    """
    # Calculate the parameter for the Poisson distribution
    lambda_ = beta * (t_end - t_start)

    # Calculate the cumulative probability
    cumulative_prob = sum((lambda_ ** i) / math.factorial(i) for i in range(0, math.floor(a) + 1))

    # Multiply by the exponential factor
    probability = math.exp(-lambda_) * cumulative_prob

    return probability

# Example usage
beta = 0.1      # Adversarial mining rate
t_start = 0     # Start time
t_end = 10      # End time
a = 5           # Threshold value

result = poisson_cumulative_probability(beta, t_start, t_end, a)
print(f"The lower bound of P(Z_t - Z_s <= {a}) is {result:.6f}")
