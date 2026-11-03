# ChainXim Honest Conflux DAG

基于[ChainXim](https://github.com/ChainXim-Team/ChainXim)的全诚实节点PoW区块DAG仿真。实现Conflux的pivot树、epoch和全序；保留原PoW单链作为诚实节点对照。DAG主线仅使用诚实节点；原ChainXim单链的攻击框架、共识后端、网络、配置和输入输出均保留。

支持五种网络：Lockstep、DeterProp、StochProp、Topology、AdHoc。数据项、可撤销pivot深度确认、缺父补块、分片重组、重连同步及离线分析均保留。

## 环境与运行

建议Python 3.10及以上。安装Python依赖，并在系统中安装Graphviz，使dot可执行程序位于PATH：

```bash
pip install -r requirements.txt
python main.py --config conf/conflux_lockstep.ini --miner_num 4 --total_round 200 --q_ave 5 --difficulty 8 --no_compact_outputfile --result_path Results/example
```

切换网络时选择对应配置：

| 网络 | 配置 |
|---|---|
| Lockstep | conf/conflux_lockstep.ini |
| DeterProp | conf/conflux_deterprop.ini |
| StochProp | conf/conflux_stochprop.ini |
| Topology | conf/conflux_topology.ini |
| AdHoc | conf/conflux_adhoc.ini |

`python main.py`继续读取原system_config.ini并执行原单链默认配置。运行DAG需显式选择conf/conflux_*.ini。

原PoW诚实对照可运行：

```bash
python main.py --config conf/conflux_lockstep.ini --consensus_type consensus.PoW --miner_num 4 --total_round 200 --q_ave 5 --difficulty 8 --no_compact_outputfile --result_path Results/bitcoin_example
```

## 源码导航

| 位置 | 职责 |
|---|---|
| main.py / environment.py | 配置、节点初始化和按轮执行 |
| data/ | 原生区块、DAG存储、邻接索引和协议事件 |
| consensus/ | PoW、Conflux、编码、依赖接纳、排序及确认 |
| miner/ | 节点状态、数据项池和网络接口 |
| network/ | 五种网络的传播、拓扑、移动及带宽模型 |
| util/ | 结构化输出、DAG绘图、指标、校验和重放 |
| plot_honest_dag.py | 读取已有结果进行统计绘图 |
| conf/ | 诚实节点运行配置和拓扑样例 |


## 相关文档

原单链入口文档保持原文件名：[README](README.zh.md)、[开发指南](developer-guide.zh.md)、[仿真示例](simulation-example.zh.md)。以下是独立DAG文档。

- [Conflux开发指南](developer-guide.dag.zh.md)：数据结构、协议流程、接口、指标及扩展位置。
- [Conflux仿真示例与统计分析](simulation-example.dag.zh.md)：五网络参数、四组吞吐对照、DAG特征、独立扫描命令和离线绘图。
- [Conflux协议规则](protocol.md)：pivot、epoch、排序和确认公式。

Conflux实现参考《Scaling Nakamoto Consensus to Thousands of Transactions per Second》的2018 v4算法。当前确认采用本地经验深度规则，未实现论文中风险概率或确定性最终确认规则。全局生成图仅用于观察，节点共识只使用本地已接纳图。
