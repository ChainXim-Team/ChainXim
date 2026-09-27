# Pre-mining 理论与仿真对比

`premining_theory_compare.py` 用论文 *Dis LU bound* 中的方法复现两项结果：

1. Lemma 4 与公式 (5) 给出的稳态 pre-mining lead 分布；
2. Theorem 2 给出的带 pre-mining 的双花攻击成功率。

脚本复用 `Theo dis complete.py` 中的 `DoubleSpendSolver`、确认阶段概率和追赶失败概率 `F`。Pre-mining lead 使用论文假定的稳态分布。

论文中的上下界会在时间切分数趋于无穷时收敛到准确值。脚本不再分别绘制上下界，而是使用

```text
delta = d / theory_slices
```

计算一条细粒度理论曲线。默认 `theory_slices=100`，比当前网络的 10 段切分细 10 倍。

## 运行

先用 `main.py` 生成 `Results/premining_parallel/adver_*.txt`，然后执行：

```powershell
python premining_theory_compare.py
```


脚本自动从每个 TXT 和其中记录的 `system_config.ini` 读取诚实矿工数、攻击者数、`N`、`Ng`、目标值及固定传播延迟。攻击者算力比例按当前仿真的实际配置计算为：

```text
adversary_miners / (honest_miners + adversary_miners)
```

## 输出

- `attack_success_comparison.png`：一条理论成功率曲线和仿真 marker；
- `premining_lead_comparison.png`：四个攻击者数量对应的四条理论 lead 曲线，以及同色的仿真 marker。

当前实现要求 `DeterPropNetwork`、固定延迟向量 `[0, ..., 0, 1.0]` 和 `q_distr=equal`。如果攻击者增长率过高，导致 pre-mining lead 不存在稳态分布，脚本会明确报错。
