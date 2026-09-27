"""Plot fine-grid pre-mining theory against ChainXim simulation runs.

The script reuses the confirmation/catch-up solver in ``Theo dis complete.py``
and implements the paper's Lemma 4 (stationary pre-mining lead) and Theorem 2
(double-spending success probability with pre-mining).

The lower/upper discretizations in the paper converge as the number of time
slices tends to infinity.  This script therefore uses one sufficiently fine
``delta = d / theory_slices`` discretization and plots one theoretical value.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import importlib.util
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "Results" / "premining_parallel"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "Results" / "premining_theory_comparison"
THEORY_MODULE_PATH = PROJECT_ROOT / "Theo dis complete.py"


@dataclass(frozen=True)
class SimulationRecord:
    path: Path
    honest_num: int
    adver_num: int
    trials: int
    successes: int
    failures: int
    success_rate: float
    lead_probability: dict[int, float]
    parameters: dict


@dataclass(frozen=True)
class TheoryResult:
    record: SimulationRecord
    attacker_share: float
    lead_probability: np.ndarray
    success_probability: float
    tail_at_cap: float
    theory_slices: int


def load_theory_module():
    spec = importlib.util.spec_from_file_location(
        "theo_dis_complete_premining", THEORY_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load theory module: {THEORY_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_record(path: Path) -> SimulationRecord:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

    required = {
        "honest_miners",
        "adversary_miners",
        "parameters",
        "successful_attacks",
        "failed_attacks",
        "total_attacks",
        "success_rate",
    }
    missing = required - values.keys()
    if missing:
        raise ValueError(f"{path} is missing fields: {sorted(missing)}")

    lead_probability: dict[int, float] = {}
    try:
        lead_header = lines.index("lead_blocks count probability")
    except ValueError as exc:
        raise ValueError(f"{path} has no pre-mining lead distribution") from exc
    for line in lines[lead_header + 1 :]:
        fields = line.split()
        if len(fields) != 3:
            continue
        lead_probability[int(fields[0])] = float(fields[2].rstrip("%")) / 100.0

    return SimulationRecord(
        path=path,
        honest_num=int(values["honest_miners"]),
        adver_num=int(values["adversary_miners"]),
        trials=int(values["total_attacks"]),
        successes=int(values["successful_attacks"]),
        failures=int(values["failed_attacks"]),
        success_rate=float(values["success_rate"].rstrip("%")) / 100.0,
        lead_probability=lead_probability,
        parameters=json.loads(values["parameters"]),
    )


def discover_records(results_dir: Path) -> list[SimulationRecord]:
    paths = sorted(
        results_dir.glob("adver_*.txt"),
        key=lambda path: int(re.search(r"(\d+)", path.stem).group(1)),
    )
    if not paths:
        raise FileNotFoundError(f"No adver_*.txt files found in {results_dir}")
    records = [parse_record(path) for path in paths]
    if any(record.trials <= 0 for record in records):
        raise ValueError("Every simulation record must contain completed trials")
    return records


def poisson_pmf(mean: float, max_value: int) -> np.ndarray:
    pmf = np.zeros(max_value + 1, dtype=float)
    pmf[0] = math.exp(-mean)
    for value in range(1, max_value + 1):
        pmf[value] = pmf[value - 1] * mean / value
    return pmf


def cycle_adversarial_blocks_pmf(
    lambda_h: float, lambda_a: float, delay_steps: int, max_value: int
) -> tuple[np.ndarray, float]:
    """Distribution of adversarial blocks between honest-chain growth events.

    After an honest growth, there are ``delay_steps`` rounds in which the
    honest chain cannot grow, followed by a geometric number of synchronized
    rounds until the next honest growth.  Adversarial growth is Poisson.
    """
    if not 0.0 < lambda_h <= 1.0:
        raise ValueError(f"lambda_h must be in (0, 1], got {lambda_h}")
    if lambda_a < 0.0:
        raise ValueError(f"lambda_a must be non-negative, got {lambda_a}")

    per_round = poisson_pmf(lambda_a, max_value)
    waiting = np.zeros(max_value + 1, dtype=float)
    denominator = 1.0 - (1.0 - lambda_h) * per_round[0]
    for value in range(max_value + 1):
        convolution = 0.0
        for mined in range(1, value + 1):
            convolution += per_round[mined] * waiting[value - mined]
        waiting[value] = (
            lambda_h * per_round[value]
            + (1.0 - lambda_h) * convolution
        ) / denominator

    delay_growth = poisson_pmf(delay_steps * lambda_a, max_value)
    cycle = np.convolve(delay_growth, waiting)[: max_value + 1]
    tail = max(0.0, 1.0 - float(cycle.sum()))
    return cycle, tail


def lead_transition_matrix(
    lambda_h: float, lambda_a: float, delay_steps: int, lead_cap: int
) -> tuple[np.ndarray, float]:
    cycle_pmf, cycle_tail = cycle_adversarial_blocks_pmf(
        lambda_h, lambda_a, delay_steps, lead_cap + 1
    )
    transition = np.zeros((lead_cap + 1, lead_cap + 1), dtype=float)
    for lead in range(lead_cap + 1):
        for mined, probability in enumerate(cycle_pmf):
            next_lead = max(0, lead + mined - 1)
            transition[lead, min(next_lead, lead_cap)] += probability
        transition[lead, lead_cap] += cycle_tail
        row_sum = transition[lead].sum()
        transition[lead] /= row_sum
    return transition, cycle_tail


def premining_lead_distributions(
    solver, premining_blocks: int, lead_cap: int, tolerance: float = 1e-14
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return the paper's stationary PMF and a finite-height PMF."""
    mean_cycle_growth = solver.lambda_a * (solver.n + 1.0 / solver.lambda_h)
    if mean_cycle_growth >= 1.0:
        raise ValueError(
            "The pre-mining lead has no stationary distribution: expected "
            f"adversarial growth per honest block is {mean_cycle_growth:.6f} >= 1"
        )
    transition, cycle_tail = lead_transition_matrix(
        solver.lambda_h, solver.lambda_a, solver.n, lead_cap
    )

    stationary = np.zeros(lead_cap + 1, dtype=float)
    stationary[0] = 1.0
    for _ in range(1_000_000):
        updated = stationary @ transition
        if np.max(np.abs(updated - stationary)) < tolerance:
            stationary = updated
            break
        stationary = updated
    else:
        raise RuntimeError("Pre-mining stationary distribution did not converge")

    finite = np.zeros(lead_cap + 1, dtype=float)
    finite[0] = 1.0
    for _ in range(premining_blocks):
        finite = finite @ transition
    return stationary, finite, cycle_tail


def success_probability_with_premining(
    solver, lead_probability: np.ndarray, r_max: int
) -> float:
    """Paper Theorem 2 using the existing confirmation/catch-up solver."""
    confirmation_joint = np.zeros(solver.N, dtype=float)
    min_round = solver.N * solver.n + solver.N
    for adversarial_blocks in range(solver.N):
        confirmation_joint[adversarial_blocks] = sum(
            solver.base_state_probability(adversarial_blocks, rounds)
            for rounds in range(min_round, r_max + 1)
        )

    total_failure = 0.0
    for initial_lead in range(min(solver.N, len(lead_probability))):
        for adversarial_blocks in range(solver.N - initial_lead):
            deficit = solver.N - initial_lead - adversarial_blocks
            if deficit <= 0:
                catchup_failure = 0.0
            elif deficit > solver.Ng:
                catchup_failure = 1.0
            else:
                catchup_failure = float(solver.F[solver.n, deficit])
            total_failure += (
                lead_probability[initial_lead]
                * confirmation_joint[adversarial_blocks]
                * catchup_failure
            )
    return float(np.clip(1.0 - total_failure, 0.0, 1.0))


def load_chainxim_parameters(record: SimulationRecord) -> dict:
    config_path = Path(record.parameters["config"])
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    parser = configparser.ConfigParser()
    if not parser.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"Cannot read ChainXim config: {config_path}")

    if parser["EnvironmentSettings"]["network_type"] != "network.DeterPropNetwork":
        raise ValueError("The paper comparison currently requires DeterPropNetwork")
    if parser["ConsensusSettings"].get("q_distr", "equal") != "equal":
        raise ValueError("The paper comparison currently requires q_distr=equal")

    target = record.parameters.get("target") or parser["ConsensusSettings"]["target"]
    q_ave = float(
        record.parameters.get("q_ave") or parser["ConsensusSettings"]["q_ave"]
    )
    prop_vector = record.parameters.get("prop_vector")
    if prop_vector is None:
        prop_vector = ast.literal_eval(
            parser["DeterPropNetworkSettings"]["prop_vector"]
        )
    if not prop_vector or prop_vector[-1] != 1.0 or any(prop_vector[:-1]):
        raise ValueError(
            "The paper comparison currently requires a fixed-delay propagation "
            "vector of the form [0, ..., 0, 1.0]"
        )

    success_per_hash = (int(target, 16) + 1) / 2**256
    total_hashes_per_round = (
        record.honest_num + record.adver_num
    ) * q_ave
    average_block_rounds = 1.0 / (total_hashes_per_round * success_per_hash)
    delay_rounds = len(prop_vector) - 1
    ell = len(prop_vector)
    if delay_rounds <= 0:
        raise ValueError("At least one fixed-delay round is required")

    attack_arg = record.parameters.get("attack_arg", {})
    return {
        "N": int(record.parameters["N"]),
        "Ng": int(attack_arg["Ng"]),
        "attacker_share": record.adver_num / (record.honest_num + record.adver_num),
        "average_block_rounds": average_block_rounds,
        "delay_rounds": delay_rounds,
        "ell": ell,
        "premining_blocks": (
            int(record.parameters["premining_target_height"])
            - int(record.parameters["premining_start_height"])
        ),
    }


def build_solver(theory_module, record: SimulationRecord, theory_slices: int):
    """Build one fine-grid solver using delta=d/theory_slices.

    The paper's lower and upper discretizations converge to the same value as
    ``theory_slices`` grows.  We use the lower-grid expression with a much
    finer grid and present it as the single theoretical approximation.
    """
    params = load_chainxim_parameters(record)
    normalized_hashes = 100.0
    normalized_success = 1.0 / (
        params["average_block_rounds"] * normalized_hashes
    )
    solver = theory_module.DoubleSpendSolver(
        params["N"],
        params["Ng"],
        theory_slices - 1,
        params["attacker_share"],
        normalized_success,
        normalized_hashes,
        params["delay_rounds"] / theory_slices,
    )
    return params, solver


def compute_theory(
    theory_module,
    record: SimulationRecord,
    lead_cap: int,
    r_max: int,
    theory_slices: int,
) -> TheoryResult:
    params, solver = build_solver(theory_module, record, theory_slices)
    stationary_lead, _, cycle_tail = premining_lead_distributions(
        solver, params["premining_blocks"], lead_cap
    )
    if not np.isclose(stationary_lead.sum(), 1.0, atol=1e-10):
        raise RuntimeError("Stationary pre-mining lead PMF does not sum to one")

    return TheoryResult(
        record=record,
        attacker_share=params["attacker_share"],
        lead_probability=stationary_lead,
        success_probability=success_probability_with_premining(
            solver, stationary_lead, r_max
        ),
        tail_at_cap=max(cycle_tail, float(stationary_lead[-1])),
        theory_slices=theory_slices,
    )


def plot_attack_success(results: list[TheoryResult], output: Path) -> None:
    attackers = np.array([item.record.adver_num for item in results])
    theory = np.array([item.success_probability for item in results])
    simulation = np.array([item.record.success_rate for item in results])

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(
        attackers,
        theory,
        color="tab:blue",
        linewidth=2.0,
        label=f"Theory",
    )
    ax.scatter(
        attackers,
        simulation,
        facecolors="none",
        edgecolors="tab:orange",
        marker="o",
        s=48,
        linewidths=1.6,
        label=f"Simulation",
        zorder=5,
    )
    ax.set_xlabel("Number of adversarial miners (10 honest miners)")
    ax.set_ylabel("Double-spending success probability")
    ax.set_xticks(attackers)
    ax.set_ylim(0.3, 1.0)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_lead_distributions(results: list[TheoryResult], output: Path) -> None:
    shown_max = 5
    leads = np.arange(shown_max + 1)
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]
    line_styles = ["-", "--", "-.", ":"]

    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    color_handles = []
    for result, color, line_style in zip(results, colors, line_styles):
        line, = ax.plot(
            leads,
            result.lead_probability[: shown_max + 1],
            color=color,
            linestyle=line_style,
            linewidth=2.0,
            label=f"{result.record.adver_num} adversarial miners",
        )
        observed_leads = np.array([
            lead for lead in sorted(result.record.lead_probability)
            if lead <= shown_max
        ])
        ax.scatter(
            observed_leads,
            [result.record.lead_probability[int(x)] for x in observed_leads],
            facecolors="none",
            edgecolors=color,
            marker="o",
            s=32,
            linewidths=1.4,
            zorder=5,
        )
        color_handles.append(line)

    style_handles = [
        Line2D([0], [0], color="black", linewidth=2.0, label="Theory"),
        Line2D(
            [0], [0], color="black", marker="o", markerfacecolor="none",
            linestyle="none", markersize=5, label="Simulation",
        ),
    ]
    first_legend = ax.legend(handles=color_handles, loc="upper right")
    ax.add_artist(first_legend)
    ax.legend(handles=style_handles, loc="lower left")
    ax.set_xlabel("Pre-mining lead U")
    ax.set_ylabel("Probability")
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 1.0)
    ax.set_xlim(0, shown_max)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot fine-grid pre-mining theory against ChainXim results."
    )
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--theory-slices", type=int, default=100)
    parser.add_argument("--lead-cap", type=int, default=100)
    parser.add_argument(
        "--r-max",
        type=int,
        default=None,
        help="Confirmation-round truncation; default scales with theory-slices.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.theory_slices < 2 or args.lead_cap <= 0:
        raise ValueError("--theory-slices must be >=2 and --lead-cap must be positive")
    r_max = args.r_max or max(20000, 200 * args.theory_slices)
    if r_max <= 0:
        raise ValueError("--r-max must be positive")

    records = discover_records(args.results_dir.resolve())
    theory_module = load_theory_module()
    results = [
        compute_theory(
            theory_module,
            record,
            args.lead_cap,
            r_max,
            args.theory_slices,
        )
        for record in records
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    attack_plot = args.output_dir / "attack_success_comparison.png"
    lead_plot = args.output_dir / "premining_lead_comparison.png"
    plot_attack_success(results, attack_plot)
    plot_lead_distributions(results, lead_plot)

    print(f"Fine-grid theory completed with m={args.theory_slices}, R_max={r_max}")
    for result in results:
        print(
            f"  adver={result.record.adver_num}: "
            f"theory={result.success_probability:.6f}, "
            f"simulation={result.record.success_rate:.6f}"
        )
        if result.tail_at_cap > 1e-8:
            print(
                f"    warning: lead-cap tail mass={result.tail_at_cap:.3e}; "
                "increase --lead-cap"
            )
    print(f"  {attack_plot}")
    print(f"  {lead_plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
