import argparse
import importlib.util
import logging
from math import factorial, lgamma, exp
from math import log as log_fun
import random
from dataclasses import dataclass
from functools import lru_cache
from multiprocessing import Pool, cpu_count, Process, Manager
from pathlib import Path
from typing import Iterable, Optional, Sequence
from decimal import Decimal, getcontext

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from matplotlib import colors as mcolors
import time

from main import experiment as run_chainxim
from theory_ly import theory_ly_curve
from util.figuretopaper import print_fig_to_paper

context = getcontext()
context.prec = 79

MINER_NUM = 100
TOTAL_HEIGHT = 50000
TOTAL_ROUNDS = 999_999_999
TOTAL_TRAILS = 12000
PROCESS_BAR_TYPE = "height"
ADVER_RATIOS = [0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45]
N_VALUES = [6, 3]
MAX_DELAY_VALUES = [120, 90, 60, 30] # [180, 170, 160, 150, 140] # [100, 95, 90, 85, 80, 75, 70] # [70, 65, 60, 55, 50] # [120, 90, 60, 30] # [160, 130, 100] # [100, 80, 50] # [60, 75] # [50, 20] # [2, 10, 20, 50] # [2, 4, 6, 8]
# MAX_DELAY_VALUES = [80, 90, 100, 110, 120, 140] # [30, 40, 50, 60, 70] # 平均出块间隔为70轮次 
CONFIG_PATH = "successprob_adver_ratio_max_delay.ini"
ATTACK_TYPE = "DoubleSpending"
NETWORK_TYPE = "network.DeterPropNetwork"
NG_FIXED = 50 # 8
PLOT_MARKERS = ["d", "^", "x", "v", "+", "1", "*", "<", ">"]
DIFFICULTY = 13.66622400280318 # 使平均出块间隔为130轮次
# DIFFICULTY = 12.773139207 # 平均出块间隔为70轮次
TARGET = f"{(int(Decimal(2) ** Decimal(256 - DIFFICULTY)) - 1):0>64X}"
ROUND_SECONDS = 0.1

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lru_cache(maxsize=None)
def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _average_block_time_seconds() -> float:
    per_miner_hash_rate_per_second = 2 ** (-DIFFICULTY) / ROUND_SECONDS
    total_hash_rate_per_second = MINER_NUM * per_miner_hash_rate_per_second
    return 1.0 / total_hash_rate_per_second


def _average_block_time_rounds() -> float:
    return _average_block_time_seconds() / ROUND_SECONDS


def _compute_theory_discrete_bounds(
    alphas: np.ndarray,
    n_value: int,
    ng: int,
    max_delay_rounds: int,
) -> tuple[np.ndarray, np.ndarray]:
    theo_dis_module = _load_module_from_file(
        "theo_dis_complete_module",
        Path(__file__).parent / "Theo dis complete.py",
    )

    delay_seconds = (max_delay_rounds - 1) * ROUND_SECONDS # max_delay_rounds * ROUND_SECONDS
    block_time_seconds = _average_block_time_seconds()
    m_value = max_delay_rounds # max_delay_rounds + 1 

    upper_str = theo_dis_module.calculate_success_rates_upper(
        alphas.tolist(),
        int(n_value),
        int(ng),
        int(m_value),
        float(block_time_seconds),
        float(delay_seconds),
    )
    lower_str = theo_dis_module.calculate_success_rates_lower(
        alphas.tolist(),
        int(n_value),
        int(ng),
        int(m_value),
        float(block_time_seconds),
        float(delay_seconds),
    )

    upper = np.array([float(x) for x in upper_str.split(",")], dtype=float)
    lower = np.array([float(x) for x in lower_str.split(",")], dtype=float)
    return lower, upper


def _compute_theory_guo_curve(
    alphas: np.ndarray,
    n_value: int,
    max_delay_rounds: int,
) -> np.ndarray:
    theo_guo_module = _load_module_from_file(
        "theo_guo_2025_module",
        Path(__file__).parent / "Theo guo2025.py",
    )

    delay_seconds = (max_delay_rounds - 1) * ROUND_SECONDS # max_delay_rounds * ROUND_SECONDS
    block_time_seconds = _average_block_time_seconds()

    _, lb_cg = theo_guo_module.cg_vs_du_bounds_beta_axis(
        float(block_time_seconds),
        float(delay_seconds),
        int(n_value),
        alphas.tolist(),
        verbose=False,
    )
    return np.array(lb_cg, dtype=float).clip(0, 1)


def _compute_theory_ly_curve(
    alphas: np.ndarray,
    n_value: int,
    max_delay_rounds: int,
) -> np.ndarray:
    return theory_ly_curve(
        alphas=alphas,
        n_confirm=int(n_value),
        max_delay_rounds=int(max_delay_rounds),
        avg_block_interval_rounds=float(_average_block_time_rounds()),
        m=1,
        tilde_m=1,
        eps=1e-6,
    )


def _compute_modelB_curve(alphas: np.ndarray, n_value: int, ng: int, max_delay_rounds: int) -> np.ndarray:
    t0 = time.perf_counter()
    curve = np.array([double_spending_with_delay(n_value, ng, float(alpha), int(max_delay_rounds)) for alpha in alphas], dtype=float)
    t1 = time.perf_counter()
    print(f"ModelB compute for max_delay={max_delay_rounds}: {t1-t0:.3f}s")
    return curve


def _compute_discrete_bounds_wrapper(alphas: np.ndarray, n_value: int, ng: int, max_delay_rounds: int) -> tuple[np.ndarray, np.ndarray]:
    t0 = time.perf_counter()
    lower, upper = _compute_theory_discrete_bounds(alphas, n_value, ng, max_delay_rounds)
    t1 = time.perf_counter()
    print(f"Theo dis complete bounds compute for max_delay={max_delay_rounds}: {t1-t0:.3f}s")
    return lower, upper


def _compute_guo_wrapper(alphas: np.ndarray, n_value: int, max_delay_rounds: int) -> np.ndarray:
    t0 = time.perf_counter()
    curve = _compute_theory_guo_curve(alphas, n_value, max_delay_rounds)
    t1 = time.perf_counter()
    print(f"Theo guo2025 compute for max_delay={max_delay_rounds}: {t1-t0:.3f}s")
    return curve


def _compute_ly_wrapper(alphas: np.ndarray, n_value: int, max_delay_rounds: int) -> np.ndarray:
    t0 = time.perf_counter()
    curve = _compute_theory_ly_curve(alphas, n_value, max_delay_rounds)
    t1 = time.perf_counter()
    print(f"Theory LY compute for max_delay={max_delay_rounds}: {t1-t0:.3f}s")
    return curve


def precompute_all_theory(alphas: np.ndarray, n_value: int, ng: int, max_delays: Sequence[int]):
    tasks = list(max_delays)
    modelB = {}
    dis_bounds = {}
    guo = {}
    ly = {}

    cpu_workers = max(1, min(len(tasks), cpu_count()))

    def _run_modelB_pool(task_list, out_dict):
        with Pool(processes=cpu_workers) as pool:
            args = [(alphas, n_value, ng, d) for d in task_list]
            results = pool.starmap(_compute_modelB_curve, args)
            for d, res in zip(task_list, results):
                out_dict[d] = res

    def _run_dis_bounds_pool(task_list, out_dict):
        with Pool(processes=cpu_workers) as pool:
            args = [(alphas, n_value, ng, d) for d in task_list]
            results = pool.starmap(_compute_discrete_bounds_wrapper, args)
            for d, res in zip(task_list, results):
                out_dict[d] = res

    def _run_guo_pool(task_list, out_dict):
        with Pool(processes=cpu_workers) as pool:
            args = [(alphas, n_value, d) for d in task_list]
            results = pool.starmap(_compute_guo_wrapper, args)
            for d, res in zip(task_list, results):
                out_dict[d] = res

    def _run_ly_pool(task_list, out_dict):
        with Pool(processes=cpu_workers) as pool:
            args = [(alphas, n_value, d) for d in task_list]
            results = pool.starmap(_compute_ly_wrapper, args)
            for d, res in zip(task_list, results):
                out_dict[d] = res

    manager = Manager()
    mb_dict = manager.dict()
    db_dict = manager.dict()
    guo_dict = manager.dict()
    ly_dict = manager.dict()

    p1 = Process(target=_run_modelB_pool, args=(tasks, mb_dict))
    p2 = Process(target=_run_dis_bounds_pool, args=(tasks, db_dict))
    p3 = Process(target=_run_guo_pool, args=(tasks, guo_dict))
    p4 = Process(target=_run_ly_pool, args=(tasks, ly_dict))

    p1.start()
    p2.start()
    p3.start()
    p4.start()

    p1.join()
    p2.join()
    p3.join()
    p4.join()

    for d in tasks:
        modelB[d] = np.array(mb_dict[d], dtype=float)
        dis_bounds[d] = tuple(db_dict[d])
        guo[d] = np.array(guo_dict[d], dtype=float)
        ly[d] = np.array(ly_dict[d], dtype=float)

    return modelB, dis_bounds, guo, ly


# 旧的定义，没有考虑多个轮次的情况，理论上只适用于区块延迟为单轮的情形
# def double_spending_with_delay(N: int, ng: int, alpha, max_delay) -> float:
#     nh = round((1 - alpha) * MINER_NUM)
#     na = round(alpha * MINER_NUM)
#     Q = 1
#     prop_vec = prop_vec_generator(max_delay)
#     n = int(N)
#     Ng = int(ng)
#     p = Decimal(2**(-DIFFICULTY))
#     lambda_h = 1 - (1 - p)**Decimal(nh * Q)
#     lambda_h_prime = lambda_h/(1+Decimal(np.sum(1 - np.array(prop_vec)))*lambda_h)
#     lambda_a = 1 - (1 - p)**Decimal(na * Q)
#     # print("lambda_h", lambda_h)
#     # print("lambda_h_prime", lambda_h_prime)
#     # print("lambda_a", lambda_a)

#     total_sum = Decimal(0.0)
    
#     for m in range(0, n + 1):
#         for j in range(0, m + 1):
#             # 第一项: S(m,j) 部分
#             # 注意: 当 N+j-1 < 0 时阶乘会出问题，需要处理边界情况
#             if n + j - 1 < 0:
#                 S_mj = 0
#             else:
#                 S_mj = (n * factorial(n + j - 1)) / (factorial(m) * factorial(n - m) * factorial(j))
#             # 第二项: 概率项
#             denominator_base = lambda_a + lambda_h_prime - lambda_a * lambda_h_prime
#             if denominator_base <= 0:
#                 term2 = 0
#             else:
#                 term2 = (lambda_h_prime**n * (1 - lambda_h_prime)**j * 
#                         lambda_a**(n - m + j) * (1 - lambda_a)**m) / (denominator_base**(n + j))
#             # 第三项: 条件概率项
#             if lambda_h_prime == 0 or (1 - lambda_a) == 0:
#                 term3 = 0
#             else:
#                 ratio = (lambda_a * (1 - lambda_h_prime)) / (lambda_h_prime * (1 - lambda_a))
#                 if abs(ratio - 1) < 1e-10:  # 处理ratio接近1的情况
#                     term3 = (m - j + 1) / (Ng + 1)
#                 else:
#                     numerator = 1 - ratio**(m - j + 1)
#                     denominator = 1 - ratio**(Ng + 1)
#                     term3 = numerator / denominator if denominator != 0 else 0
#             # 累加三项乘积
#             total_sum += Decimal(S_mj) * term2 * term3
    
#     return 1 - total_sum



# Model B
from theory_complete import DoubleSpendSolver
def double_spending_with_delay(N: int, ng: int, alpha, max_delay) -> float:
    delta = 1/10
    R_max = 12000
    h = 2**(-DIFFICULTY) / delta
    solver = DoubleSpendSolver(N, ng, max_delay - 1, alpha, h, MINER_NUM, delta) # max_delay
    return solver.attack_success_probability(R_max)


# Model A

# def double_spending_with_delay(N: int, ng: int, alpha, max_delay) -> float:
#     nh = round((1 - alpha) * MINER_NUM)
#     na = round(alpha * MINER_NUM)
#     n = int(N)
#     Ng = int(ng)
#     p = 2**(-DIFFICULTY)
#     lambda_h = 1 - (1 - p)**(nh*max_delay)
#     lambda_h_prime = lambda_h/(1 + (1 - 1/nh)*lambda_h)
#     lambda_a = 1 - (1 - p)**(na*max_delay)
#     return calculate_P_success(n, Ng, lambda_h_prime, lambda_a)

def calculate_P_success(n, Ng, lambda_h_prime, lambda_a):
    """
    计算攻击者成功概率 P_success
    
    参数:
    n: 区块高度 (原公式中的N和n)
    Ng: 最大允许落后区块数
    lambda_h_prime: 诚实链调整后的增长概率参数
    lambda_a: 攻击链增长概率参数
    """
    total_sum = 0.0
    
    for m in range(0, n + 1):
        for j in range(0, m + 1):
            # 第一项: S(m,j) 部分
            # 注意: 当 N+j-1 < 0 时阶乘会出问题，需要处理边界情况
            if n + j - 1 < 0:
                S_mj = 0
            else:
                S_mj = (n * factorial(n + j - 1)) // (factorial(m) * factorial(n - m) * factorial(j))
            
            # 第二项: 概率项
            denominator_base = lambda_a + lambda_h_prime - lambda_a * lambda_h_prime
            if denominator_base <= 0:
                term2 = 0
            else:
                term2 = (lambda_h_prime**n * (1 - lambda_h_prime)**j * 
                        lambda_a**(n - m + j) * (1 - lambda_a)**m) / (denominator_base**(n + j))
            
            # 第三项: 条件概率项
            if lambda_h_prime == 0 or (1 - lambda_a) == 0:
                term3 = 0
            else:
                ratio = (lambda_a * (1 - lambda_h_prime)) / (lambda_h_prime * (1 - lambda_a))
                if abs(ratio - 1) < 1e-10:  # 处理ratio接近1的情况
                    # term3 = (m - j + 1) / (Ng + 1)
                    term3 = (m - j) / Ng
                else:
                    # numerator = 1 - ratio**(m - j + 1)
                    # denominator = 1 - ratio**(Ng + 1)
                    numerator = 1 - ratio**(m - j)
                    denominator = 1 - ratio**Ng
                    term3 = numerator / denominator if denominator != 0 else 0
            
            # 累加三项乘积
            total_sum += S_mj * term2 * term3
    
    P_success = 1 - total_sum
    return P_success

def prop_vec_generator(max_delay: int) -> list[float]:
    if max_delay <= 0:
        raise ValueError("max_delay must be a positive integer")
    if max_delay == 1:
        return [1.0]
    # return [max_delay/10] + [1.0]
    return [0] * (max_delay - 1) + [1.0] # 所有诚实矿工都必须在max_delay轮收到区块
    # [1/MINER_NUM] * (max_delay - 1) + [1.0]
    # 该传播向量仅在出块矿工延迟max_delay轮收到自己的区块的情况下才正确


@dataclass
class SimulationRecord:
    max_delay: int
    Ng: int
    N: int
    target_alpha: float
    actual_alpha: float
    theoretical_success_probability: float
    simulation_success_rate: Optional[float]
    double_spending_success_times: Optional[int]
    attack_fail: Optional[int]
    result_path: str

    def as_dict(self) -> dict:
        return self.__dict__


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_success_rate(stats: dict) -> Optional[float]:

    return stats['attack_success'] # 已经是多次实验平均后的成功率了（每次实验最多攻击一次）

    success_rate = stats.get("Success Rate")
    if success_rate is not None:
        return float(success_rate)


    success_times = stats.get("attack_success")
    fail_times = stats.get("attack_fail")
    if success_times is not None and fail_times is not None:
        total = success_times + fail_times
        if total >= 0:
            return success_times / total
    return None


def simulate_configuration(
    alpha: float,
    n_value: int,
    max_delay: int,
    base_output_dir: Path,
    seed: Optional[int] = None,
) -> SimulationRecord:
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    adver_num = max(1, int(round(alpha * MINER_NUM)))
    actual_alpha = adver_num / MINER_NUM
    theoretical_prob = None # double_spending_with_delay(n_value, NG_FIXED, actual_alpha, max_delay)

    if max_delay > 0:
        network_type = NETWORK_TYPE
        prop_vector = prop_vec_generator(max_delay)
    else:
        network_type = "network.LockstepNetwork"
        prop_vector = None
        print(f"Currently using ZeroDelayNetwork for max_delay={max_delay} in the place of DeterPropNetwork.")

    result_subdir = (
        base_output_dir
        / f"max_delay_{max_delay}"
        / f"N{n_value}"
        / f"alpha_{actual_alpha:.3f}"
    )
    ensure_directory(result_subdir)

    stats = run_chainxim(
        trail_num=TOTAL_TRAILS, # 设置每个配置的模拟次数
        seed=seed,
        total_round=TOTAL_ROUNDS,
        target=TARGET,
        total_height=TOTAL_HEIGHT,
        miner_num=MINER_NUM,
        process_bar_type=PROCESS_BAR_TYPE,
        network_type=network_type,
        attack_type=ATTACK_TYPE,
        attack_arg={"Ng": NG_FIXED},
        Ng=NG_FIXED,
        N=n_value,
        adver_num=adver_num,
        adver_lists=tuple(range(adver_num)),
        prop_vector=prop_vector,
        result_path=result_subdir,
        config=CONFIG_PATH,
    )

    sim_success_rate = parse_success_rate(stats)

    return SimulationRecord(
        max_delay=max_delay,
        Ng=NG_FIXED,
        N=n_value,
        target_alpha=alpha,
        actual_alpha=actual_alpha,
        theoretical_success_probability=theoretical_prob,
        simulation_success_rate=sim_success_rate,
        double_spending_success_times=stats.get("attack_success"),
        attack_fail=stats.get("attack_fail"),
        result_path=str(result_subdir),
    )


def _build_simulation_tasks(
    alphas: Sequence[float],
    max_delays: Sequence[int],
    base_output_dir: Path,
) -> list[tuple]:
    tasks: list[tuple] = []
    for delay_idx, max_delay in enumerate(max_delays):
        for n_idx, n_value in enumerate(N_VALUES):
            for alpha in alphas:
                seed = int(((delay_idx + 1) * 11 + (n_idx + 1)) * MINER_NUM + alpha * MINER_NUM)
                tasks.append((alpha, n_value, max_delay, base_output_dir, seed))
    return tasks


def run_experiments(
    alphas: Sequence[float],
    max_delays: Sequence[int],
    base_output_root: Path,
) -> tuple[pd.DataFrame, Path]:
    ensure_directory(base_output_root)

    import os
    with open(base_output_root / "pid.txt", "w") as f:
        f.write(str(os.getpid()))

    tasks = _build_simulation_tasks(alphas, max_delays, base_output_root)
    if not tasks:
        raise ValueError("No simulation tasks generated. Check input parameters.")

    pool_size = max(1, min(40, cpu_count(), len(tasks)))
    with Pool(processes=pool_size, maxtasksperchild=1) as pool:
        records: list[SimulationRecord] = pool.starmap(simulate_configuration, tasks)

    df = pd.DataFrame(record.as_dict() for record in records)
    excel_path = base_output_root / "successprob_adver_ratio_max_delay.xlsx"
    df.to_excel(excel_path, index=False)
    return df, excel_path


def plot_results(df: pd.DataFrame, output_dir: Path) -> list[Path]:
    ensure_directory(output_dir)

    unique_n_values = sorted(df["N"].unique())
    if not unique_n_values:
        raise ValueError("No data available for plotting.")

    alpha_min = df["actual_alpha"].min()
    alpha_max = df["actual_alpha"].max()
    # dense_alpha = df["actual_alpha"].unique()
    dense_alpha = np.arange(alpha_min, alpha_max + 1/MINER_NUM, 1/MINER_NUM)

    color_map = plt.get_cmap("tab10")
    colors = [color_map(i) for i in range(color_map.N)]

    def _adjust_lightness(color, amount: float):
        """amount < 1 变暗，amount > 1 变亮。"""
        rgb = np.array(mcolors.to_rgb(color))
        if amount >= 1:
            return tuple(np.clip(rgb + (1 - rgb) * (amount - 1), 0, 1))
        return tuple(np.clip(rgb * amount, 0, 1))

    outputs: list[Path] = []
    for n_idx, n_value in enumerate(unique_n_values):
        fig, ax = plt.subplots(figsize=(6, 4.5))
        subset = df[df["N"] == n_value]
        delay_groups = subset.groupby("max_delay")

        # Precompute theory for all delays for this N
        all_delays = sorted({int(x) for x in subset["max_delay"].unique()})
        dense_alpha_arr = dense_alpha
        modelB_map, dis_bounds_map, guo_map, ly_map = precompute_all_theory(dense_alpha_arr, n_value, NG_FIXED, all_delays)
        for group_idx, (max_delay, group) in enumerate(sorted(delay_groups, key=lambda x: x[0])):
            sorted_group = group.sort_values("actual_alpha")
            sim_values = sorted_group.dropna(subset=["simulation_success_rate"])
            if sim_values.empty:
                continue

            marker = PLOT_MARKERS[group_idx % len(PLOT_MARKERS)]
            delay_color = colors[group_idx % len(colors)]
            sim_color = _adjust_lightness(delay_color, 0.9)
            theory_main_color = _adjust_lightness(delay_color, 1.05)
            theory_guo_color = _adjust_lightness(delay_color, 1.25)
            theory_ly_color = _adjust_lightness(delay_color, 0.65)
            theory_fill_color = _adjust_lightness(delay_color, 1.45)

            ax.plot(
                sim_values["actual_alpha"].to_numpy(),
                sim_values["simulation_success_rate"].to_numpy(),
                marker=marker,
                linestyle="none",
                color=sim_color,
                markersize=6,
                label=f"Simulation Max Delay $\\Delta$ = {max_delay}",
            )
        
            theory_curve = modelB_map[int(max_delay)]
            dis_lower, dis_upper = dis_bounds_map[int(max_delay)]
            guo_curve = guo_map[int(max_delay)]
            ly_curve = ly_map[int(max_delay)]

            ax.fill_between(
                dense_alpha,
                dis_lower,
                dis_upper,
                color=theory_fill_color,
                alpha=0.28,
                linewidth=0,
            )

            ax.plot(
                dense_alpha,
                theory_curve,
                linestyle="-",
                color=theory_main_color,
                label=f"Theory Max Delay $\\Delta$ = {max_delay}",
            )

            ax.plot(
                dense_alpha,
                guo_curve,
                linestyle="--",
                color=theory_guo_color,
                linewidth=1.8,
            )

            ax.plot(
                dense_alpha,
                ly_curve,
                linestyle=":",
                color=theory_ly_color,
                linewidth=1.7,
            )

        ax.set_xlabel("Proportion of attacker's computing power, $\\alpha$")
        ax.set_ylabel("Double Spending Success Probability")
        ax.set_ylim(-0.02, 1)
        ax.set_xlim(max(-0.05, alpha_min - 0.02), min(0.55, alpha_max + 0.02))
        ax.grid(linestyle="--", alpha=0.4)
        
        # Build legend for curve styles + max_delay color mapping
        dummy_lines = [
            plt.Line2D([0], [0], color='black', marker=PLOT_MARKERS[0], linestyle='None', label='Simulation'),
            plt.Line2D([0], [0], color='grey', linestyle='-', label='Theory CXN'),
            Patch(facecolor='grey', edgecolor='grey', alpha=0.15, label='Theo CXN Bounds'),
            plt.Line2D([0], [0], color='grey', linestyle='--', label='Theo Guo'),
            plt.Line2D([0], [0], color='grey', linestyle=':', label='Theory LY')
        ]
        for group_idx, (max_delay, _) in enumerate(sorted(delay_groups, key=lambda x: x[0])):
            marker = PLOT_MARKERS[group_idx % len(PLOT_MARKERS)]
            dummy_lines.append(
                plt.Line2D([0], [0], color=colors[group_idx % len(colors)], marker=marker,
                           linestyle='None', label=f'Max Delay $\\Delta$ = {max_delay}')
                        #    linestyle='None', label=f'$w_1$ = {max_delay}')
            )
        labels = [line.get_label() for line in dummy_lines]
        ax.legend(dummy_lines, labels, loc='lower right') # 'upper left' or 'best'
        
        svg_path = output_dir / f"successprob_adver_ratio_N{n_value}_by_delay.svg"
        print_fig_to_paper(
            output_type="svg",
            plot_file_name=svg_path.stem,
            fig_font_size=16,
            fig_font_name="Times New Roman",
            fig_width=7,
            is_print=True,
            is_print_time=False,
            output_path=output_dir,
        )
        outputs.append(svg_path)
        plt.close(fig)

    return outputs


def run_from_result_file(result_file: Path) -> list[Path]:
    df = pd.read_excel(result_file)
    required_columns = {"max_delay", "N", "actual_alpha"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Result file must contain columns: {', '.join(sorted(missing))}")
    return plot_results(df, result_file.parent)


def _validate_positive_ints(values: Iterable[int], name: str) -> list[int]:
    unique_values = sorted({int(v) for v in values})
    if not unique_values:
        raise ValueError(f"{name} must contain at least one value.")
    if any(v <= 0 for v in unique_values):
        raise ValueError(f"All values in {name} must be positive integers.")
    return unique_values


def _prepare_alphas(alphas: Iterable[float]) -> list[float]:
    unique = sorted({float(alpha) for alpha in alphas})
    if not unique:
        raise ValueError("At least one attacker ratio (alpha) must be specified.")
    return unique


def main_cli():
    parser = argparse.ArgumentParser(
        description="Simulate and plot double spending success probability under deterministic propagation network."
    )
    parser.add_argument(
        "result_file",
        type=Path,
        nargs="?",
        default=None,
        help="Path to the Excel result file. If provided, skip simulations and regenerate plots.",
    )
    parser.add_argument(
        "--alphas",
        type=float,
        nargs="*",
        default=ADVER_RATIOS,
        help="Attacker ratios (alpha) to simulate. Ignored when --result-file is provided.",
    )
    parser.add_argument(
        "--max-delays",
        type=int,
        nargs="*",
        default=MAX_DELAY_VALUES,
        help="Propagation delays to evaluate. Each delay is converted to prop_vector via prop_vec_generator.",
    )
    args = parser.parse_args()

    font_path = Path('/home/xiehui/fonts/')
    if font_path.exists():
        import matplotlib.font_manager as fm
        fm.fontManager.addfont(str(font_path / 'times.ttf'))
        fm.fontManager.addfont(str(font_path / 'timesi.ttf'))
        fm.fontManager.addfont(str(font_path / 'timesbd.ttf'))
        fm.fontManager.addfont(str(font_path / 'timesbi.ttf'))

    if args.result_file is not None:
        figure_paths = run_from_result_file(args.result_file)
        for path in figure_paths:
            print(f'Regenerated figure saved to: {path}')
        return

    alphas = _prepare_alphas(args.alphas)
    max_delays = _validate_positive_ints(args.max_delays, "max_delays")

    import datetime

    output_root = Path.cwd() / 'Results' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + 'successprob_max_delay')
    ensure_directory(output_root)

    df, excel_path = run_experiments(alphas, max_delays, output_root)
    figure_paths = plot_results(df, output_root)

    print(f'Results saved to {excel_path}')
    for path in figure_paths:
        print(f'Figure saved to {path}')



if __name__ == '__main__':
    main_cli()
