# Premining 使用说明

Premining 是双花攻击正式开始前的私有挖矿阶段。攻击者提前维护一条私有链，希望在双花目标出现时获得领先优势。

当前功能仅用于 `DoubleSpending`，支持：

- 单次仿真中的高度结束模式和轮次结束模式；
- `main.py` 内直接配置的固定高度批量试验；
- 每次攻击的成功/失败结果和 premining 结束 lead 统计；
- 多个参数组以及多个独立 `main.py` 进程并行运行。

## 一、Premining 的执行过程

启用 premining 后，攻击者按照以下过程工作：

1. 在攻击者观察到的诚实链高度达到 `premining_start_height` 前，攻击者不进行私有 premining。
2. 达到开始高度后，攻击者从当前诚实链头开始维护私有链。
3. 每轮开始时，如果攻击者私有链落后于其当前观察到的诚实链，攻击者先采用诚实链，再继续私有挖矿。
4. 满足结束条件后进入正常双花攻击阶段。

这里的“诚实链高度”指攻击模块维护的 `honest_chain`，它由攻击者本地接收到的区块更新。因此，在 bounded-delay 网络中，高度模式不是在某个诚实矿工刚产生目标区块的瞬间结束，而是在攻击者收到并观察到该高度区块后结束。

### 1. 按高度结束

当攻击者观察到的诚实链达到 `premining_target_height` 时：

- 该高度的诚实区块直接成为双花目标；
- 攻击阶段从 `PREMINING` 切换到 `DOUBLE_SPENDING`；
- `Premining End Lead` 在阶段切换瞬间记录，早于该轮后续的正常双花挖矿。

例如目标高度为 30：

```text
诚实矿工产生 H30
    ↓ 网络传播
攻击者接收并把 H30 更新到其 honest_chain
    ↓
记录 premining_end_lead
    ↓
以 H30 为双花目标进入正常攻击
```

### 2. 按轮次结束

当轮次达到 `premining_target_round` 时：

- 先记录当前诚实链头和 premining lead；
- 攻击者不会停止挖矿，而是继续维护私有链；
- 目标轮次之后产生的第一个诚实区块成为双花目标；
- 时间戳仍等于目标轮次的区块属于结束边界，不作为目标。

## 二、单次仿真配置

### 1. 在 `system_config.ini` 中配置

在 `[AttackSettings]` 中设置：

```ini
attack_type = DoubleSpending
attack_arg = {'Ng': 20,
              'premining_enabled': True,
              'premining_start_height': 1,
              'premining_end_condition': 'height',
              'premining_target_height': 30}
```

主要参数如下：

| 参数 | 说明 |
| --- | --- |
| `premining_enabled` | 是否启用 premining，默认 `False` |
| `premining_start_height` | 攻击者观察到该诚实链高度后开始 premining |
| `premining_end_condition` | `height` 或 `round`，默认 `height` |
| `premining_target_height` | 高度模式的目标高度，必须不小于开始高度 |
| `premining_target_round` | 轮次模式的结束轮次 |
| `Ng` | 攻击链允许落后的最大区块数 |
| `N` | 交易确认深度，来自 `[ConsensusSettings]` 或命令行 `-N` |

轮次模式示例：

```ini
attack_type = DoubleSpending
attack_arg = {'Ng': 20,
              'premining_enabled': True,
              'premining_start_height': 3,
              'premining_end_condition': 'round',
              'premining_target_round': 2000}
```

关闭 premining：

```ini
attack_arg = {'Ng': 20, 'premining_enabled': False}
```

不填写任何 `premining_*` 参数时，premining 默认关闭。

### 2. 使用命令行覆盖配置

`main.py` 提供以下选项：

```text
--premining / --no-premining
--premining-start-height
--premining-end-condition {height,round}
--premining-target-height
--premining-target-round
```

高度模式示例：

```powershell
python main.py `
  --attack_type DoubleSpending `
  --miner_num 14 `
  --adver_num 4 `
  -N 3 `
  -Ng 20 `
  --premining `
  --premining-start-height 1 `
  --premining-end-condition height `
  --premining-target-height 30 `
  --seed 10000
```

重要：只有把 `main.py` 顶部 `PREMINING_DOUBLE_SPENDING_TEST['enabled']` 设置为 `False` 后，普通单次仿真命令和 `--premining-test-config` 才会执行。内置批量配置的检查发生在这两个入口之前。

### 3. 单次结果

攻击统计中包含：

- `Premining End Condition`：结束方式；
- `Premining Max Lead`：premining 期间最大领先区块数；
- `Premining End Height`：结束时攻击者观察到的诚实链高度；
- `Premining End Lead`：阶段切换瞬间的攻击链高度减诚实链高度；
- `attack_success`、`attack_fail` 和 `Attack times`：攻击结果。



## 三、在 `main.py` 中直接运行固定高度批量试验

批量入口是：

```python
premining_double_spending_attack(...)
```

每次试验都会：

1. 启动一个全新的 `main.py` 子进程；
2. 使用独立种子；
3. 强制使用 `DoubleSpending`、开启 premining 并采用高度结束模式；
4. 在恰好一次攻击成功或失败后结束；
5. 立即把结果追加到该攻击者数量对应的 TXT 文件。

### 当前内置配置

`main.py` 顶部当前配置为：

```python
PREMINING_DOUBLE_SPENDING_TEST = {
    'enabled': True,
    'max_workers': 4,
    'output_dir': 'Results/premining_parallel',
    'config': 'system_config.ini',
    'keep_run_results': False,
    'defaults': {
        'trials': 5000,
        'seed': 10000,
        'honest_num': 10,
        'start_height': 1,
        'attack_height': 30,
        'Ng': 20,
        'N': 3,
        'total_round': 500000,
    },
    'parameter_sets': [
        {'adver_num': 4},
        {'adver_num': 5},
        {'adver_num': 6},
        {'adver_num': 7},
    ],
}
```

直接运行：

```powershell
python main.py
```

当前配置固定 10 个诚实矿工，只改变攻击者数量。对应的总矿工数自动设置为 14、15、16、17。每组执行 5000 次试验，并使用相同的种子序列 `10000～14999`。

### 批量控制参数

| 参数 | 说明 |
| --- | --- |
| `enabled` | 为 `True` 时，运行 `python main.py` 会直接进入该批量试验 |
| `max_workers` | 同时运行的最大 `main.py` 子进程数，不是总试验数 |
| `output_dir` | 各组 TXT 统计文件的目录 |
| `config` | 默认 `system_config.ini` 路径 |
| `keep_run_results` | 是否保留每次子进程的运行目录；默认 `False`，使用完即删除 |
| `defaults` | 所有参数组共享的默认值 |
| `parameter_sets` | 各参数组覆盖默认值的部分 |

`max_workers=4` 表示最多同时运行四个试验。四组参数不会各自获得四个进程；所有组的任务共同使用这个并发池。

### 每个参数组支持的主要参数

| 参数 | 说明 |
| --- | --- |
| `adver_num` | 攻击者矿工数，必须为正数，也是文件名的一部分 |
| `trials` | 该组试验次数；`runs` 是兼容别名 |
| `seed` | 第一轮试验的种子；第 `i` 次使用 `seed+i-1` |
| `honest_num` | 固定诚实矿工数；总矿工数自动设为 `honest_num+adver_num` |
| `miner_num` | 固定总矿工数；诚实矿工数为 `miner_num-adver_num` |
| `attack_height` | 必填的攻击高度；也可使用 `premining_target_height` |
| `start_height` | 开始高度，默认 1；也可使用 `premining_start_height` |
| `Ng` | 双花失败边界；小写 `ng` 也是兼容别名 |
| `N` | 交易确认深度 |
| `total_round` | 单次试验允许的最大轮数 |
| `difficulty` | 可选 PoW 难度，会转换为 `target` |

参数组还可以传入普通 `main.py` 支持的其他配置，例如 `q_ave`、`target` 或网络参数。

不要在同一参数组中同时依赖 `honest_num` 和 `miner_num`。设置 `honest_num` 时，它优先决定总矿工数。为了让 TXT 中的诚实矿工数明确，建议始终设置两者之一。

### 固定诚实矿工数与固定总矿工数

固定诚实矿工数：

```python
'defaults': {
    'honest_num': 10,
    ...
}
```

此时：

```text
miner_num = honest_num + adver_num
```

固定总矿工数：

```python
'defaults': {
    'miner_num': 20,
    ...
}
```

此时：

```text
honest_num = miner_num - adver_num
```

要求 `miner_num > adver_num`。

### 种子含义

`seed` 是每组的起始种子，不是所有试验固定使用同一个种子。例如：

```python
'trials': 5000,
'seed': 10000,
```

会产生：

```text
trial 1    -> seed 10000
trial 2    -> seed 10001
...
trial 5000 -> seed 14999
```

不同参数组使用相同的起始种子和试验次数，可以在改变攻击者数量时使用相同的种子序列。

### 是否保留单次运行目录

默认配置：

```python
'keep_run_results': False
```

所有子进程的中间目录位于临时目录，批量试验结束后删除。设置为 `True` 时，中间目录保存在：

```text
<output_dir>/run_data_YYYYMMDD-HHMMSS/
```

其中可包含每次试验的 `case.json`、`single_attack_result.json` 和 `main.log`。5000 次试验会产生大量小文件，通常建议保持 `False`。


## 五、TXT 记录文件

每个攻击者数量对应一个文件，例如：

```text
Results/premining_parallel/adver_4.txt
Results/premining_parallel/adver_5.txt
Results/premining_parallel/adver_6.txt
Results/premining_parallel/adver_7.txt
```



