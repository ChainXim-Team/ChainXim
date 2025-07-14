# ChainXim 开发者文档 Developer Guide


## 总体架构 Framework
ChainXim主要由Environment、Miner、Adversary、Network、Consensus、Blockchain六个组件组成，其中Consensus、Adversary与Network三大组件可配置、可替换，从而适应不同类型的共识协议、攻击向量与网络模型。六个抽象组件之间的关系如下图所示：

![framework](doc/framework.svg)

每个抽象组件由对应的一个或多个类实现，其中Consensus对应的Consensus类以及Network对应的Network类仅为抽象类，还需要派生出有实际功能的类，以实现各类共识协议与网络模型。

目前已实现的共识协议（目前consensus_type配置的所有可选项）：

| 共识类(派生自Consensus) | 说明                                     |
| ----------------------- | ---------------------------------------- |
| consensus.PoW           | 工作量证明机制                           |
| consensus.VirtualPoW    | 通过均匀分布随机数和出块概率模拟的工作量证明机制   |
| consensus.SolidPoW      | 严格约束每轮哈希计算次数的工作量证明机制 |

目前已实现的网络模型（目前network_type配置的所有可选项）：

| 网络类(派生自Network)       | 说明                                       |
| --------------------------- | ------------------------------------------ |
| network.SynchronousNetwork  | 同步网络模型                               |
| network.DeterPropNetwork      | 基于传播向量的网络模型                     |
| network.StochPropNetwork | 延迟有界、接收概率随轮次增加递增的网络模型 |
| network.TopologyNetwork     | 复杂拓扑网络模型，可以生成随机网络         |

Environment是仿真器的核心。用户执行main.py中的主程序开始仿真。主程序根据仿真参数初始化Environment对象，调用`exec`启动仿真循环，仿真结束后调用`view_and_write`生成仿真结果并写入Results文件夹。

ChainXim将时间离散化处理，抽象为“轮次”（round），以轮次为单位模拟每个节点的行为。每个轮次依次激活矿工节点执行共识操作，所有节点都被激活一遍之后，调用网络类中的`diffuse`方法在矿工节点间进行消息传输。(详见**环境与模型假设**章节)


## 环境与模型假设 Environment & Model Assumptions
Environment组件是ChainXim程序运行的基石，其主要完成了仿真器系统模型的架构，以便与其它五大组件进行对接。同时也定义了仿真器中主要的一些参量，并封装了仿真器各组件中需要运用的部分函数。为便于理解该部分内容，下面将首先介绍ChainXim的模型假设。
### 模型假设
ChainXim的系统模型设计主要参考了下面的论文：

* J. A. Garay, A. Kiayias and N. Leonardos, "The bitcoin backbone protocol: Analysis and applications", Eurocrypt, 2015. <https://eprint.iacr.org/2014/765.pdf>

ChainXim将连续的时间划分为一个个离散的轮次，且网络中的全部节点（包含诚实矿工与非诚实攻击者）都将在每个轮次内进行一定数目的操作，以完成记账权的竞争与新区块的生成与传播。定义网络中矿工总数为n，其中有t个矿工隶属于非诚实的攻击者。每个轮次中，全体矿工根据各自的编号被依次唤醒，并根据自己的身份采取行动，诚实矿工将严格依照共识协议的规则产生区块；攻击者则会结合实际情况选择遵守协议或发起攻击。**注意，每个轮次中，攻击模块只会被触发一次，每次触发都会进行一次完整的攻击行为。当前版本中，攻击者每轮次中会随机在轮到某一个隶属于攻击者的矿工时触发。虽然不同矿工被唤醒的次序不同，但同一轮次内实际上不存在先后顺序。** 

为模拟上述各方在现实区块链系统中的具体操作，ChainXim参考了论文中提出的两种重要方法，它们分别为随机预言（Random Oracle）和扩散（Diffuse）方法，其在ChainXim中的具体定义如下：

- **随机预言（Random Oracle）**：以PoW共识为例，各矿工在每一轮次最多可执行q次行动（不同矿工的q可能为不同值），即q次进行哈希计算的机会。每个矿工都将进行q次随机查询操作，即将某一随机数输入哈希函数，验证其结果是否小于给定难度值。若矿工成功找到了低于难度值的结果，则视为其成功产生了一个区块。**同一轮次中不同矿工产生的区块视作是同时产生的。**
- **扩散（Diffuse）**：当矿工产生了新的区块，它会将这个区块上传到网络，由网络层负责消息传播。根据网络层配置的不同，传播逻辑也会有所不同。此外，攻击者也可能选择不上传自己本轮次挖到的区块，只有上传到网络层的区块才会经由该方法进行传播。**在ChainXim的模型中，认为攻击者所控制的矿工拥有独立于区块链系统的专用通信通道，即任一隶属于攻击者的矿工一旦接收到某个区块，则攻击者麾下的所有矿工均会在下一轮次收到该区块。**

**注意，上述的扩散方法主要与Network组件对接，而随机预言方法则与Consensus组件对接。随即预言建模最初是针对比特币中的的PoW共识协议提出的。为使仿真器能够兼容其它共识，例如PBFT这类基于交互的共识，ChainXim后续将考虑在Consensus组件中对这一方法进行重载。**
**Environment中设置了exec函数来一次性完成上述两种方法**：每一轮次中，所有矿工将依次被唤醒，并各自执行随机预言方法：如果矿工为诚实方，那么exec函数将调用Consensus组件执行进行相关操作；如果激活了攻击者，则调用Attacker组件进行相关操作。（每一轮次中只会调用一次Attacker组件）
当所有矿工都完成自己的行动，即回合结束时，exec函数中将执行Network组件中的扩散方法，在网络中传播区块。一个具体的实例如下图所示：

![environment](doc/environment.png)

该实例中n=4，t=1。当第k轮次（Round k）开始时，四个矿工将依照序号从小到大的顺序被依次唤醒，且各自完成自己的q次行动。其中，仅有2号矿工（Miner 2）成功获得了记账权，并将产生的区块进行传播（Diffuse方法）。由于各自的传播时延不尽相同，1号矿工与3号矿工在第k+1轮次便已成功接收到了该区块，而4号矿工则到第k+2轮次才收到此区块。第k+1轮次没有矿工完成出块，第k+2轮次中1号与4号矿工则都完成了出块，但这里4号矿工为攻击者，它采取了自私挖矿的攻击手段，将随机预言中产生的区块置于私链上，在扩散中也暂不传播给其它矿工。第k+3轮次中只有4号攻击者矿工完成出块，这时在它的视野中，自己的私链已经长于主链，故它会将私链通过扩散方法传播给其它矿工，区块链至此发生分叉，且在收到该私链矿工的视野中，攻击者的链为最长合法链。第k+4轮次中，如果1号或2号矿工没有收到私链，并继续在诚实主链上挖矿，则它们的利益将可能受到损害。

综上所述，ChainXim利用离散的轮次与受限的行动次数有效抽象了区块链网络中区块的产生与传播。

### 仿真器环境
总体来说，环境组件完成了整体模型的搭建。初始化函数根据输入参数设置基础参数，调用了其它组件进行各自的初始化，设置n个矿工、选定t个攻击者、配置全局区块链、网络组件、攻击组件等，用于后续运行与评估。环境组件中的主要函数及其各自的参数如下表所示：

| 函数                      | 参数                                                 | 说明                                                         |
| ------------------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| envir_create_global_chain | -                                                    | 创建环境中的全局区块链                                       |
| exec                      | num_rounds:int, max_height:int, process_bar_type:str | 执行指定轮数或指定高度的仿真，通过num_rounds设置仿真运行的总轮数，通过max_height设置仿真终止的高度 |
| on_round_start            | round: int                                           | 每轮次开始时执行的操作，包括DataItem生成                     |
| generate_dataitem         | round: int                                           | 在round指定的轮次生成DataItem                                |
| view                      | -                                                    | 在终端窗口输出仿真结果，包含仿真生成的区块链结构图、吞吐量、增长率(反映链增长)、分叉率及共同前缀与链质量评估 |
| view_and_write            | -                                                    | 输出仿真结果并保存在txt文件中                                |
| assess_common_prefix      | type: str                                            | 计算评估区块链的共同前缀特性，可以统计两种类型的共同前缀分布：`pdf`以及`cdf` |
| process_bar               | -                                                    | 显示当前仿真的进度，在终端输出实时变动的进度条与百分比       |

上表中，envir_create_global_chain初始化生成了一条全局区块链。此后，该链将作为上帝视角下的全局区块链树与全局最长合法链。
主程序根据仿真参数初始化Environment对象，调用`exec`启动仿真循环，实现了论文中所述的随机预言方法与扩散方法,对于攻击者则需通过`attack_excute`调用相应接口。仿真结束后调用`view_and_write`统计并输出仿真结果。

### DataItem机制

DataItem是链上数据的抽象，数据结构为4 byte 生成轮次 + 4 bytes 随机数。

在system_config.ini中设置dataitem_enable=True之后，将启用DataItem机制。此时ChainXim将具备以下特性：

1. TopologyNetwork和AdhocNetwork两大模型在仿真时将会按照区块中存储的DataItem数量计算区块大小以及相应的区块传播延迟。
2. 评估阶段按照主链上所有区块的数据项数计算吞吐量
3. 评估阶段可按照链上非法DataItem的比例评估攻击者的攻击效果（仅Environment中产生的DataItem合法，其余均为非法）

目前的Environment中将在每个轮次为每个矿工提供`max_block_capacity`个DataItem，矿工需要在挖矿时将这些DataItem打包到区块中。一旦矿工产生了新区块，Environment将在下个轮次开始前生成新的DataItem供矿工使用，确保DataItem足以填满区块。


## 仿真器输入参数 Input
仿真器的输入参数可以通过两种方式指定：命令行以及配置文件。一般情况下可以参考ChainXim附带的配置文件system_config.ini产生新的仿真配置文件，也可以通过命令行指定个别仿真参数。命令行支持的参数少于配置文件，但是一旦被指定，优先级高于配置文件，可以通过`python main.py --help`命令查看命令行帮助信息，通过`python --config CONFIG_FILE_PATH`指定配置文件的路径。

### EnvironmentSettings

配置仿真环境:

| system_config      | 命令行示例                                   | 类型  | 说明                                                         |
| ------------------ | -------------------------------------------- | ----- | ------------------------------------------------------------ |
| total_round        | `--total_round 50`                           | int   | 仿真总轮次数                                                 |
| process_bar_type   | `--process_bar_type round`                   | str   | 进度条显示风格（round或height）                              |
| miner_num          | `--miner_num 80`                             | int   | 网络中的矿工总数                                             |
| blocksize          | `--blocksize 8`                              | float | 区块大小，单位MB                                             |
| consensus_type     | `--consensus_type consensus.PoW`             | str   | 共识类型，`consensus.PoW`、`consensus.VirutalPoW`、<br/>`consensus.SolidPoW`三选一 |
| network_type       | `--network_type network.SynchronousNetwork ` | str   | 网络类型，`network.SynchronousNetwork`、<br/>`network.PropVecNetwork`、`network.BoundedDelayNetwork`、<br/>`network.TopologyNetwork`、`network.AdHocNetwork`五选一 |
| show_fig           | `--show_fig`                                 | bool  | 是否显示仿真过程中的图像                                     |
| log_level          | `--log_level error`                          | str   | 日志文件的级别（error、warning、info或debug）                |
| compact_outputfile | `--no_compact_outputfile`                    | bool  | 是否简化log和result输出以节省磁盘空间<br/>通过`--no_compact_outputfile`设置为False |

### ConsensusSettings

配置共识协议参数:

| system_config      | 命令行示例                 | 类型 | 说明                                                         |
| ------------------ | -------------------------- | ---- | ------------------------------------------------------------ |
| q_ave              | `--q_ave 5`                | int  | 单个矿工的平均哈希率，即每轮能计算哈希的次数                 |
| q_distr            | `--q_distr equal`          | str  | 哈希率的分布模式<br>equal：所有矿工哈希率相同；<br>rand：哈希率满足高斯分布 |
| target             | 无                         | str  | 16进制格式的PoW目标值                                        |
| 无                 | `--difficulty 12`          | int  | 用二进制PoW目标值前缀零的长度表示的PoW难度，<br/>在主程序转换为PoW目标值 |
| average_block_time | `--average_block_time 400` | int  | 平均产生一个区块所需要的轮数，<br/>设置后根据q和miner_num的数值自动设置target |

### AttackModeSettings

配置攻击模式参数:

| system_config | 命令行示例                     | 类型       | 说明                                                         |
| ------------- | ------------------------------ | ---------- | ------------------------------------------------------------ |
| adver_num     | `--adver_num 0`                | int        | 攻击者总数                                                   |
| adver_lists   | 无                             | tuple[int] | 攻击者id e.g.(1,3,5)                                         |
| attack_type   | `--attack_type SelfishMining ` | str        | 攻击类型，HonestMining、SelfishMining<br/>、DoubleSpending、EclipsedDoubleSpending四选一 |

### DeterPropNetworkSettings

配置DeterPropNetwork参数

| system_config | 类型        | 说明                                                         |
| ------------- | ----------- | ------------------------------------------------------------ |
| prop_vector   | list[float] | 传播向量（以列表形式）e.g. [0.1, 0.2, 0.4, 0.6, 1.0]其中的元素代表了当(1,2,3...)轮过后接收到消息的矿工比例，最后一个元素必须为1.0 |

### StochPropNetworkSettings

配置StochPropNetwork参数:

| system_config   | 命令行示例              | 类型        | 说明                                   |
| --------------- | ----------------------- | ----------- | -------------------------------------- |
| rcvprob_start   | `--rcvprob_start 0.001` | float       | 消息的初始接收概率                     |
| rcvprob_inc     | `--rcvprob_inc 0.001`   | float       | 每轮增加的消息接收概率                 |
| stat_prop_times | 无                      | list[float] | 需统计的区块传播时间对应的接收矿工比例 |

### TopologyNetworkSettings

配置TopologyNetwork参数:

| system_config          | 命令行示例                                        | 类型        | 说明                                                         |
| ---------------------- | ------------------------------------------------- | ----------- | ------------------------------------------------------------ |
| init_mode              | `--init_mode rand`                                | str         | 网络初始化方法, 'adj'邻接矩阵, 'coo'稀疏的邻接矩阵, 'rand'随机生成。'adj'和'coo'的网络拓扑通过csv文件给定。'rand'需要指定带宽、度等参数 |
| topology_path          | `--topology_path conf/topologies/default_adj.csv` | str         | csv格式拓扑文件的路径，文件格式需要和`init_mode`匹配（路径相对于当前路径） |
| bandwidth_honest       | `--bandwidth_honest 0.5`                          | float       | 诚实矿工之间以及诚实矿工和攻击者之间的网络带宽，单位MB/round |
| bandwidth_adv          | `--bandwidth_adv 5`                               | float       | 攻击者之间的带宽，单位MB/round                               |
| rand_mode              | `--rand_mode homogeneous`                         | str         | 随机网络拓扑的生成模式<br />'homogeneous'：根据ave_degree生成网络并尽可能保持每个节点的度相同<br />'binomial'：采用Erdős-Rényi算法，以`ave_degree/(miner_num-1)`概率在节点之间随机建立链接 |
| ave_degree             | `--ave_degree 8`                                  | float       | 网络生成方式为'rand'时，设置拓扑平均度                       |
| stat_prop_times        | 无                                                | list[float] | 需统计的区块传播时间对应的接收矿工比例                       |
| outage_prob            | `--outage_prob 0.1`                               | float       | 每条链路每轮的中断概率，链路中断后消息将在下一轮重发         |
| dynamic                | `--dynamic`                                       | bool        | 是否使网络动态变化，如果动态变化，会以一定概率添加或者删除节点之间的链接 |
| avg_tp_change_interval | 无                                                | float       | dynamic=true时，设置拓扑变化的平均轮次                       |
| edge_remove_prob       | 无                                                | float       | dynamic=true时，设置拓扑变化时，已存在的每条边移除的概率     |
| edge_add_prob          | 无                                                | float       | dynamic=true时，设置拓扑变化时，未存在的条边新建立连接的概率 |
| max_allowed_partitions | 无                                                | int         | dynamic=true时,设置拓扑变化时，最大可存在的分区数量          |
| save_routing_graph     | `--save_routing_graph`                            | bool        | 是否保存各消息的路由传播图，建议网络规模较大时关闭           |
| show_label             | `--show_label`                                    | bool        | 是否显示拓扑图或路由传播图上的标签，建议网络规模较大时关闭   |

### AdHocNetworkSettings

配置AdHocNetwork参数:

| system_config             | 命令行示例           | 类型        | 说明                                                         |
| ------------------------- | -------------------- | ----------- | ------------------------------------------------------------ |
| init_mode                 | `--init_mode rand`   | str         | 网络初始化方法, 'adj'邻接矩阵, 'coo'稀疏的邻接矩阵, 'rand'随机生成。'adj'和'coo'的网络拓扑通过csv文件给定。'rand'需要指定带宽、度等参数 |
| ave_degree                | `--ave_degree 3`     | float       | 网络生成方式为'rand'时，设置拓扑平均度                       |
| segment_size              | `--ave_degree 8`     | float       | 消息分段大小 ；将完整消息分若干段，每段消息传播时间为一轮    |
| region_width              | `--region_width 100` | float       | 正方形区域的宽度，节点在该区域中进行高斯随机游走             |
| comm_range                | `--comm_range 30`    | float       | 节点通信距离，在通信距离内的两节点自动建立连接               |
| move_variance             | `--move_variance 5`  | float       | 节点进行高斯随机游走时，指定xy坐标移动距离的方差             |
| outage_prob               | `--outage_prob 0.1`  | float       | 每条链路每轮的中断概率，链路中断后消息将在下一轮重发         |
| enable_large_scale_fading | 无                   | bool        | 启用大尺度衰落之后，分片大小会自动根据衰落模型调整           |
| path_loss_level           | 无                   | str         | low/medium/high三档衰落幅度                                  |
| bandwidth_max             | 无                   | float       | 距离在comm_range/100以内所能取得的最大带宽，以MB/round为单位 |
| stat_prop_times           | 无                   | list[float] | 需统计的区块传播时间对应的接收矿工比例                       |

### DataItemSettings

配置DataItem机制的参数:

| system_config           | 命令行示例                    | 类型 | 说明                                                         |
| ----------------------- | ----------------------------- | ---- | ------------------------------------------------------------ |
| dataitem_enable         | `--dataitem_enable`           | bool | 如果启用该选项，将生成并包含在块中数据项。                          |
| max_block_capacity      | `--max_block_capacity=10`     | int  | 块中可以包含的最大数据项数。max_block_capacity=0将禁用数据项机制。   |
| dataitem_size           | `--dataitem_size=1`           | int  | 每个数据项的大小（以MB为单位）。                                  |
| dataitem_input_interval | `--dataitem_input_interval=0` | int  | 数据项输入的时间间隔（以轮次为单位）。dataitem_input_interval=0将启用全局数据项队列。 |


## 仿真器输出 Simulator Output

仿真结束后会在终端打印仿真过程中全局链的统计数据。例：
```
Chain Growth Property:
12 blocks are generated in 3000 rounds, in which 3 are stale blocks.
Average chain growth in honest miners' chain: 9.0
Number of Forks: 3
Fork rate: 0.33333333
Stale rate: 0.25
Average block time (main chain): 333.33333333 rounds/block
Average block time (total): 250.0 rounds/block
Block throughput (main chain): 0.003 blocks/round
Throughput in MB (main chain): 0.024 MB/round
Block throughput (total): 0.004 blocks/round
Throughput in MB (total): 0.032 MB/round

Chain_Quality Property: {'Honest Block': 9, 'Adversary Block': 1}
Ratio of blocks contributed by malicious players: 0.1
The simulation data of SelfishMining is as follows :
 {'The proportion of adversary block in the main chain': 'See [Ratio of blocks contributed by malicious players]', 'Theory proportion in SynchronousNetwork': '0.2731'}
Double spending success times: 1
Block propagation times: {0.03: 0, 0.05: 0, 0.08: 0, 0.1: 0, 0.2: 1.111, 0.4: 2.222, 0.5: 3.182, 0.6: 3.455, 0.7: 4.0, 0.8: 4.5, 0.9: 5.4, 0.93: 0, 0.95: 0, 0.98: 0, 1.0: 5.0}
Count of INV interactions: 257
```

终端显示的仿真结果含义如下（更详细的解释可以参考[Evaluation](#评估-Evaluation)）：

| 输出项目                                            | 解释                                                         |
| --------------------------------------------------- | ------------------------------------------------------------ |
| Number of stale blocks                              | 孤立区块数（不在主链中的区块数）                             |
| Average chain growth in honest miners' chain        | 诚实节点平均链长增长                                         |
| Number of Forks                                     | 分叉数目（只算主链）                                         |
| Fork rate                                           | 分叉率=主链上有分叉的高度数/主链高度                         |
| Stale rate                                          | 孤块率=孤块数/区块总数                                       |
| Average block time (main chain)                     | 主链平均出块时间=总轮数/主链长度(轮/块)                      |
| Block throughput (main chain)                       | 主链区块吞吐量=主链长度/总轮数                               |
| Throughput in MB (main chain)                       | 主链区块吞吐量\*区块大小                                     |
| Average block time (total)                          | 总平均出块时间=总轮数/生成的区块总数                         |
| Block throughput (total)                            | 总区块吞吐量=生成的区块总数/总轮数                           |
| Throughput in MB (total)                            | =总区块吞吐量\*区块大小                                      |
| Throughput of valid dataitems                       | 有效DataItem吞吐量                                           |
| Throughput of valid dataitems in MB                 | 以MB计的有效DataItem吞吐量                                   |
| Average dataitems per block                         | 每个区块的平均大小（平均DataItem数量\*每个DataItem大小）     |
| Input dataitem rate                                 | DataItem的输入速率                                           |
| common prefix pdf                                   | 统计共同前缀得到的pdf（统计每轮结束时，所有诚实节点的链的共同前缀与最长链长度的差值得到的概率密度分布） |
| Consistency rate                                    | 一致性指标=common_prefix_pdf[0]                              |
| Chain_Quality Property                              | 诚实矿工和恶意矿工的出块总数                                 |
| Ratio of dataitems contributed by malicious players | = 主链上有效DataItem数量 / 主链上总DataItem数量              |
| Ratio of blocks contributed by malicious players    | 恶意节点出块比例                                             |
| Upper Bound t/(n-t)                                 | 恶意节点出块占比的上界(n为矿工总数，t为恶意矿工数目)         |
| Double spending success times                       | 双花攻击成功次数                                             |
| Block propagation times                             | 区块传播时间（分布）                                         |
| Count of INV interactions                           | 使用带拓扑的网络（TopologyNetwork和AdhocNetwork）时，所有矿工发送的INV包的总和 |


需要注意的是，在ChainXim中，**主链**定义为：已经达成共识的诚实矿工的本地链的共同前缀（注意：该定义中不要求所有诚实矿工都对主链达成共识，只需要足够多的诚实矿工达成共识即可，在配置文件中consensus_miner_quantile定义了确认一个块在主链上所需要的诚实矿工的比例）。仿真过程中结果、日志、图像都保存在Results/\<date-time\>/目录下，date-time是仿真开始的日期时间。该目录的典型文件结构：
```
Results/20230819-232107/
├── Attack Result
│   └── Attack Log.txt
├── Chain Data
│   ├── chain_data.txt
│   ├── chain_data0.txt
│   ├── chain_data1.txt
│   ├── ......
├── Network Results
│   ├── ......
├── block_interval_distribution.svg
├── blockchain visualisation.svg
├── blockchain_visualization
│   ├── Blockchain Structure.gv
│   └── Blockchain Structure.gv.svg
├── evaluation results.txt
├── events.log
└── parameters.txt
```

输出的仿真结果文件含义如下：

| 文件或目录                      | 功能描述                                                     |
| ------------------------------- | ------------------------------------------------------------ |
| Attack_log.txt                  | 攻击日志                                                     |
| Attack_result.txt               | 攻击结果                                                     |
| Chain Data/                     | 全局链和各矿工本地链的完整数据                               |
| Network Results/                | 网络传输结果，如传播过程（各矿工何时收到某区块）及网络拓扑、路由过程图等 |
| block_interval_distribution.svg | 区块时间分布                                                 |
| blockchain visualisation.svg    | 区块链可视化                                                 |
| blockchain_visualization/       | 借助Graphviz的区块链可视化                                   |
| evaluation results.txt          | 评估结果，内容和仿真结束后终端显示的仿真结果一致             |
| events.log                      | 仿真过程日志，记录重要事件如产生区块、接入网络等             |
| parameters.txt                  | 仿真环境参数                                                 |


## 矿工 Miner
Miner组件定义了矿工类，用于创建矿工并进行相关的操作。其中定义的函数如下表所示：

| 函数                | 输入参数与类型                                               | 返回值类型        | 说明                                                         |
| ------------------- | ------------------------------------------------------------ | ----------------- | ------------------------------------------------------------ |
| _join_network       | network:Network                                              | -                 | 在网络初始化时矿工加入网络，初始化网络接口                   |
| forward             | msgs:list[Message], msg_source_type:str, forward_strategy:str, spec_targets:list, syncLocalChain:bool | -                 | 通过网络接口层将消息转发给其他节点。 msgs需要转发的消息列表; msg_source_type消息来源类型, SELF_GEN_MSG表示由本矿工产生, OUTER_RCV_MSG表示由网络接收; forward_strategy 消息转发策略; spec_targets 如果forward_strategy为SPECIFIC, 则spec_targets为转发的目标节点列表; syncLocalChain 是否向邻居同步本地链，尽量在产生新区块时同步. |
| set_adversary       | _isAdversary:bool                                            | -                 | 设置各矿工是否为攻击者                                       |
| set_auto_forwarding | auto_forwarding:bool                                         | -                 | 设置矿工是否要自动转发接收到的Message                        |
| receive             | source:int, msg:Message                                      | bool              | 处理接收的信息，实际为调用consensus组件中的receive方法，同时在receive_history中记录msg的来源 |
| launch_consensus    | input:any                                                    | Block\|None, bool | 开始共识过程，实际为调用consensus组件中的consensus_process方法，返回新消息new_msg（没有新消息则为None）以及是否有新消息的标识符msg_available |
| BackboneProtocol    | round:int                                                    | Block\|None       | 诚实矿工每轮次执行的操作。首先从网络中接收信息（区块链更新），其次调用挖矿函数尝试生成区块。如果区块链有更新（接收到新区块或产生了新区块），则将新消息返回给环境组件，否则返回空 |

考虑到仿真器的拓展性，miner组件自身定义的函数实际是很少的，主要的函数都在consensus组件与environment组件中定义，该组件实际上为联系各组件的桥梁。miner只能通过网络接口`self._NIC:NetworkInterface`与网络进行交互，网络接口调用`receive`函数将其他节点发送的消息传递给当前节点，当前节点通过`forward`函数将要转发的消息发给网络接口层，网络接口层通过网络层将消息发送给其他节点。

## 区块链数据 Chain Data


本节介绍ChainXim中的基础数据类型。在仿真过程中产生的所有区块数据通过data.BlockHead、data.Block、data.Chain描述。下图为ChainXim中区块链数据结构的示意图。所有Block以多叉树形式组织起来，树上的每一对父节点与子节点通过Block中的parentblock与next属性双向链接，树的根节点与末端节点分别记录于Chain.head以及Chain.last_block。图中Chain对象包含高度为2的区块链，除创世区块`Block 0`以外，共有三个区块，在区块高度1处出现分叉，`Block 0 - Block 1 - Block 3`构成主链，`Block 3`是主链的链尾。

![blockhead-block-chain](doc/blockhead-block-chain.svg)

### 消息类 Message
Message是矿工在挖矿过程中产生的所有消息的基类，目前主要的消息仅有区块Block。Message的属性目前仅包含消息长度size，单位MB。

### BlockHead

BlockHead用于定义区块头中的数据，data.BlockHead为抽象基类，其calculate_blockhash为抽象方法，需要在共识类中定义新的BlockHead并覆盖calculate_blockhash。BlockHead仅包含下表中的属性：

| 属性      | 类型 | 说明                                                         |
| --------- | ---- | ------------------------------------------------------------ |
| prehash   | bytes  | 前一区块的哈希                                               |
| timestamp | int  | 创建区块时的时间戳                                           |
| content   | bytes | 区块中承载的数据，如果DataItem启用即为DataItem序列，如果DataItem禁用则默认为区块生成轮次 |
| miner     | int  | 产生区块的矿工或攻击者的ID                                   |

**注：由于本仿真器更加关心区块在网络中的传播情况，因此，对于区块链中存储的数据（交易，智能合约等），使用content属性对其进行抽象。**

### Block

Block用于定义区块中的数据，除了区块头blockhead以外，还包含下表中的属性：

| 属性             | 类型        | 说明                                                 |
| ---------------- | ----------- | ---------------------------------------------------- |
| name             | str         | 区块的friendly name，格式为字母B+一个标识区块产生顺序的序号 |
| height           | int         | 区块高度                                             |
| blockhash        | bytes       | 区块被构建时自动计算出的区块哈希                     |
| isAdversaryBlock | bool        | 是否是攻击者产生的区块                               |
| isGenesis        | bool        | 是否是创世区块                                       |
| next             | list[Block] | 一个引用子块的列表                                   |
| parentblock      | Block       | 对母块的引用                                         |

**需要注意的是，blockhead属性为只读属性，Block对象被构造后便不可修改。** 除此以外Block具有两个辅助方法：

| 方法                | 输入参数与类型 | 返回值类型 | 说明                                                         |
| ------------------- | -------------- | ---------- | ------------------------------------------------------------ |
| get_height          | -              | int        | 返回Block.height                                             |
| calculate_blockhash | -              | bytes      | 调用blockhead.calculate_blockhash，保存哈希值于blockhash并返回blockhash的值 |

最后，为了使Block对象能够在Network中传输，Block类派生自Message类。

### Chain

Chain主要用于保存区块链的根节点与末端节点，并定义操作区块链所需的一系列函数。Chain包含下表中的属性：

| 属性      | 说明                                                |
| --------- | --------------------------------------------------- |
| head      | 储存区块链的创世区块                                |
| last_block | 对主链末端区块的引用，对于PoW系统主链为多叉树上的最长链 |
| miner_id  | 维护区块链的矿工或攻击者的ID，如为全局区块链则为缺省值None            |

Chain类具有多种方法，可以用于添加新区块、合并链、搜索区块、可视化区块链、保存区块链数据等，见下表：

| 方法                         | 输入参数与类型                                          | 返回值类型  | 说明                                                         |
| ---------------------------- | ------------------------------------------------------- | ----------- | ------------------------------------------------------------ |
| search_block                 | block: Block                                            | Block\|None | 在存储于本地的区块树中搜索目标块，存在返回该区块，不存在返回None |
| search_block_by_hash         | blockhash: bytes                                        | Block\|None | 按照哈希在存储于本地的区块树中搜索目标块，存在返回该区块，不存在返回None |
| get_last_block               | -                                                       | Block       | 返回Chain.last_block                                         |
| set_last_block               | block: Block                                            | -           | 检查block是否在链中，然后设置该block为last_block             |
| add_blocks                   | blocks: Block \| list[block], <br />insert_point: Block | Block       | 深拷贝区块后添加到链中，blocks 可以是list[Block]类型 也可以是Block类型，inset_point 是插入区块的位置 从其后开始添加默认为last_block |
| ShowStructure1               | -                                                       | -           | 以head为根节点，在stdout打印整个多叉树                       |
| ShowStructure                | miner_num:int                                           | -           | 生成blockchain visualisation.svg，显示区块链中每个区块产生的轮次以及父子关系 |
| ShowStructureWithGraphviz    | -                                                       | -           | 在blockchain_visualization目录下借助Graphviz生成区块链可视化图 |
| GetBlockIntervalDistribution | -                                                       | -           | 生成出块时间分布图'block_interval_distribution.svg'          |
| printchain2txt               | chain_data_url:int                                      | -           | 将链中所有块的结构与信息保存到chain_data_url，默认保存到'Chain Data/chain_data.txt' |
| CalculateStatistics          | rounds:int                                              | dict        | 生成区块链统计信息，通过字典返回统计信息，rounds为仿真总轮次数 |

## 共识 Consensus
本节介绍ChainXim的共识层架构，以工作量证明（Proof of Work, PoW）为例解释共识协议在ChainXim中的实现。Consensus类是一个描述ChainXim共识层基本要素的抽象类，在ChainXim中实现共识协议需要在Consensus类基础上扩展出新的共识类。目前已经实现的共识类是PoW，下图为展现PoW与Consensus关系的类图。

![consensus-pow](doc/consensus-pow.svg)

每一个PoW对象包含以下属性：

| 属性          | 类型  | 说明                                                         |
| ------------- | ----- | ------------------------------------------------------------ |
| local_chain   | Chain | 本地链，是某一矿工视角下的区块链，包含主链以及所有该矿工已知的分叉 |
| receive_tape | list  | 接收队列，区块到达矿工时被添加到接收队列中，矿工的回合结束后清空队列 |
| target        | bytes | PoW中哈希计算问题的目标值，当且仅当区块哈希值小于该目标值，区块有效 |
| q             | int   | 单个矿工每轮次可计算哈希次数                                 |

PoW类通过以下方法模拟工作量证明机制中的出块、验证行为，并通过最长链原则解决分叉：

| 方法               | 输入参数与类型                                               | 返回值类型                   | 说明                                                         |
| ------------------ | ------------------------------------------------------------ | ---------------------------- | ------------------------------------------------------------ |
| mining_consensus   | miner_id:int,<br>isadversary:bool,<br>x: Any,<br />round: int | Block, bool \|<br>None, bool | 每个轮次执行一次，修改q次nonce计算区块哈希，<br>如果哈希小于目标值，返回Block对象和True，<br>否则返回None和False |
| local_state_update | -                                                            | Block, bool                  | 逐一验证_receive_tape中的区块，将区块合并到本地链中，<br>最后通过最长链准则确定主链，<br>返回主链的链尾以及一个反映主链是否被更新的标志<br>如果新区块合法但因为中间区块缺失无法并入本地链，则放入缓存中 |
| valid_chain        | lastblock: Block                                             | bool                         | 验证末端为lastblock的链                                      |
| valid_block        | block: Block                                                 | bool                         | 验证block是否有效，即验证区块哈希是否小于目标值              |

### 共识协议与区块

下图展示了Chainxim中与共识相关的继承与派生关系。如图所示，PoW.BlockHead与PoW.Block类是共识类的子类，派生自data.BlockHead与data.Block。Consensus类的子类BlockHead与Block类分别继承自data.BlockHead与data.Block，并重新定义了BlockHead与Block的初始化接口。

![consensus-block](doc/consensus-block.svg)

Consensus.BlockHead与Consensus.Block通过如下接口初始化。

```python
# consensus/consensus_abc.py
class Consensus(metaclass=ABCMeta):
    class BlockHead(data.BlockHead):
        def __init__(self, preblock:data.Block=None, timestamp=0, content=b'', miner_id=-1):
    
    class Block(data.Block):
        def __init__(self, blockhead: data.BlockHead, preblock: data.Block = None, isadversary=False, blocksize_MB=2):
```
和data.Blockhead与data.Block相比，输入参数发生了一定变化，比如prehash换成preblock，去除height、blockhash等，这可以将data.Block以及data.BlockHead的底层细节隐藏起来。
以PoW为例，在构造新的Block对象时，需要先派生出具体共识协议的区块头PoW.BlockHead，然后用区块头blockhead、前一区块preblock、攻击者信息isadversary构造PoW.Block（如有需要，可以加上一些其他参数，如区块大小blocksize_MB），其接口如下。

```python
# consensus/pow.py
class PoW(Consensus):
    class BlockHead(Consensus.BlockHead):
        def __init__(self, preblock: Consensus.Block = None, timestamp=0, content=b'', miner_id=-1,target = bytes(),nonce = 0):
            super().__init__(preblock, timestamp, content, miner_id)
            self.target = target  # 难度目标
            self.nonce = nonce  # 随机数

        def calculate_blockhash(self) -> bytes:
```

可以看到，PoW.BlockHead初始化时除了需要Consensus.BlockHead的输入参数，还增加了target以及nonce；从Consensus.BlockHead继承的输入参数的同时也继承了默认值，新增的入参也需要指定默认值，这些默认值在生成创世区块时会有用。此外，calculate_blockhash方法需要根据各类共识协议中的区块定义重写。

### 共识类的初始化

Consensus初始化时需要矿工ID作为参数，而从Consensus派生出的共识类，初始化时一般需要额外的共识参数，这些参数通过consensus_param承载，consensus_param在Environment对象构造时指定（可参考源代码），在Miner类初始化时传递给共识对象。在PoW中，consensus_param包括以下三项：

|属性|类型|说明|
|-|-|-|
|target|str|PoW中哈希计算问题的十六进制目标值，当且仅当区块哈希值小于该目标值，区块有效。|
|q_ave|int|单个矿工每轮次可计算哈希次数的平均值|
|q_distr|str|单个矿工每轮次可计算哈希次数的分布|

**注：参数q指每个轮次每个矿工计算哈希的最大次数，通过q_distr与q_ave指定。q_distr为`equal`时，所有矿工的q均等于q_ave；当q_distr为一个字符串化的数组时，选择q_distr中下标为miner_id的元素作为q（即按照该数组分配算力占比）。**

共识类初始化时需要初始化本地链Blockchain，并为本地链生成创世区块，生成创世区块时会调用Consensus.create_genesis_block方法，其接口如下：

```python
# consensus/consensus_abc.py
def create_genesis_block(self, chain:Chain, blockheadextra:dict = None, blockextra:dict = None):
```

第一个参数即为通过Chain()产生的空链，后两个字典型参数可为创世区块指定额外参数，在Environment构造时传入的genesis_blockheadextra以及genesis_blockextra会被传递到这个接口。某些特殊的共识协议如果需要指定创世区块的参数，就需要在构造Environment对象时传入字典类型的genesis_blockheadextra以及genesis_blockextra。

通过create_genesis_block生成创世区块时，会先调用self.BlockHead生成创世区块的区块头、通过blockheadextra更新区块头、通过self.Block生成创世区块并赋值给self.head，最后通过blockextra更新区块。

### 消息对象的生命周期

在当前架构中，ChainXim理论上可以支持Message及其派生对象由共识对象(consensus)产生、在网络中传输并被目标矿工的共识对象处理。本小节以PoW为例，解释ChainXim中典型的消息对象——区块如何被产生、传输、接收、验证并更新到目标矿工的本地链中。

下图展示ChainXim中不同模块、不同方法间的调用关系：

![message-lifecycle](doc/message-lifecycle.svg)

其中比较值得关注的是粗体的六个方法，consensus_process调用mining_consensus实现出块，新区块经由launch_consensus调用forward进入矿工的转发队列，每轮次diffuse被调用时会调用Miner._NIC.nic_forward使区块进入模拟网络开始仿真。在矿工接收到新区块时，diffuse调用该矿工的receive方法实现区块接收（接收到的区块暂存于接收缓冲区_receive_tape），local_state_update在每个轮次开始时逐个验证\_receive_tape中的区块并更新到目标矿工的本地链中。需要注意的是消息的具体转发、接收过程对于不同网络类型会略有不同，详见[网络](#网络-Network)一节）

#### 区块产生与传播

PoW.consensus_process被调用后将调用PoW.mining_consensus，进行所谓的“挖矿”操作。由于每个矿工一个轮次内的PoW共识对象只有q次计算哈希的机会，因此每次调用mining_consensus仅以一定概率生成区块并产生PoW.Block对象，未能产生新区块时返回None。如果mining_consensus返回了Block对象，PoW.consensus_process将Block对象添加到本地链，然后返回包含该Block对象的列表。

该列表将被传递到位于Environment.exec的主循环中，然后通过网络类的access_network进入网络模型传播。由于Block类是Message的派生类，其实例可以在网络类中传播。

#### 区块接收

网络类的diffuse方法每个轮次结束时被调用一次，每次调用时会推进网络中数据包的传播进度。网络模型中的Block对象经过一定轮次之后到达其他矿工，此时Miner.receive方法会被调用，进而调用receive_filter方法，该方法会根据消息类型进行分流，对接收到的Block对象调用receive_block添加到_receive_tape中。

#### 更新本地链

在BackboneProtocal调用launch_consensus之前，local_state_update会被调用。对于PoW共识，这个函数的作用是将_receive_tape中缓存的区块逐一验证后合并到本地链；如果并入的链比当前主链更长，就将其设置为主链。验证过程分为两步，第一步验证区块本身的合法性，即区块哈希是否小于目标值，第二部检查区块的母块是否可以从本地链中检索到，如果检索到则将合法新区块添加到本地链，否则放入\_block\_buffer等待其母块被接收到。当\_block\_buffer中的母块在local_state_update中被处理，则调用synthesis_fork从\block_buffer将这个母块之后的分支并入本地链。

### 如何实现新的共识协议

```python
class MyConsensus(Consensus):
```

为了在ChainXim中实现一个共识协议，需要从Consensus类中派生出共识类（本小节以MyConsensus为例），并且至少覆盖以下子类与函数，实现其基本功能：

- BlockHead: 从Consensus.BlockHead派生，定义区块头中与共识协议相关的数据项，需要覆盖calculate_blockhash方法
- mining_consensus: 根据共识协议产生新区块
- local_state_update: 根据接收到的区块更新本地链
- valid_chain: 验证整条区块链是否符合共识协议
- valid_block: 验证单个区块是否符合共识协议

MyConsensus.BlockHead可以参考PoW.BlockHead的写法，重新实现\_\_init\_\_以及calculate_blockhash使BlockHead支持新的共识协议。Block可以直接使用从Consensus继承而来的子类Block，也可以在MyConsensus中派生新的Block子类。PoW类采用是第一种方法，但如果Block中有需要传递的数据但是与哈希计算不直接相关，可以采用第二种方法，将这部分数据通过新的Block子类承载。

```python
    class Block(Consensus.Block):
        def __init__(self, blockhead: chain.BlockHead, preblock: chain.Block = None, isadversary=False, blocksize_MB=2, other_params):
            super().__init__(blockhead, preblock, isadversary, blocksize_MB)
            ...
```

Block对象的构造过程可参考“[共识协议与区块](#共识协议与区块)”。

对于类PoW的共识机制，由于比较简单，因此基本上只需要考虑区块实现即可。但许多共识协议远比工作量证明更加复杂，这种复杂性体现在其共识过程需要产生区块以外的其他消息并在网络中传播，并且除了本地链以外每个矿工可能还会有其他状态量。如果要实现这样的共识协议，需要扩展共识层与网络层可处理的对象。ChainXim中可以通过派生data.Message类实现这一点，比如增加ExtraMessage作为MyConsensus的子类：

```python
    class ExtraMessage(network.Message):
        def __init__(self,size,...):
```

然后在需要ExtraMessage的地方直接构造即可，这样的对象可以在网络层正确传播。为了使ExtraMessage被共识对象正确接收，需要在MyConsensus类中重写receive方法并新增receive_extra_message方法，可以参考以下示例：

```python
    def receive(self,msg: Message):
        if isinstance(msg,Block):
            return self.receive_block(msg)
        elif isinstance(msg,ExtraMessage):
            return self.receive_extra_message(msg)
    def receive_extra_message(self,extra_msg: ExtraMessage):
        if extra_msg_not_received_yet:
            self.receive_tape.append(extra_msg)
            random.shuffle(self.receive_tape) # 打乱接收顺序
            return True
        else:
            return False
```

如果共识协议类似工作量证明机制，可以仿照PoW.mining_consensus，用MyConsensus.mining_consensus实现共识机制中的出块算法，其接口如下：

```python
    def mining_consensus(self, Miner_ID, isadversary, x, round):
```

更具体的写法可以参考PoW.mining_consensus。

但如果是更加复杂的共识协议，需要在不同状态下产生Block以外的消息对象，则需要用MyConsensus.consensus_process覆盖Consensus.consensus_process方法，实现一个有限状态机，示例：

```python
    def consensus_process(self, Miner_ID, isadversary, x, round):
        if self.state == STATE1:
            newblock, mine_success = self.mining_consensus(Miner_ID, isadversary, x, round)
            if mine_success is True:
                self.local_chain.add_blocks(newblock)
                self.local_chain.set_last_block(newblock)
                self.state = NEXT_STATE
                return [newblock], True # 返回挖出的区块
            else:
                return None, False
        elif self.state == STATE2:
            DO_SOMETHING_TO_PRODUCE_EXTRA_MESSAGE
            self.state = NEXT_STATE
            if len(list_of_extra_messages) > 0:
                return list_of_extra_messages, True
            else:
                return None, False
```

其中self.state是控制共识类实例的状态，在STATE2下consensus_process如果产生了新的消息则返回由ExtraMessage构成的列表以及True；如果没有则返回None以及False。self.state可以在\_\_init\_\_中初始化，示例：

```python
    def __init__(self, miner_id, consensus_param):
        super().__init__(miner_id)
        self.state = INITIAL_STATE
        ...
```

MyConsensus.local_state_update需要根据_receive_tape中缓存的Message对象更新共识对象的状态，最典型的就是根据传入的区块更新本地链，其逻辑可以参考以下代码片段：

```python
    def local_state_update(self):
        for message in self.receive_tape:
            if isinstance(message, Consensus.Block):# 处理Block
                if not self.valid_block(message):
                    continue
                prehash = message.blockhead.prehash
                if insert_point := self.local_chain.search_block_by_hash(prehash):
                    conj_block = self.local_chain.add_blocks(blocks=[message], insert_point=insert_point)
                    fork_tip, _ = self.synthesize_fork(conj_block)
                    depthself = self.local_chain.get_height()
                    depth_incoming_block = fork_tip.get_height()
                    if depthself < depth_incoming_block:
                        self.local_chain.set_last_block(fork_tip)
                        new_update = True
                        self.state = NEXT_STATE # 接收到新区块时的状态转移
                else:
                    self.block_buffer.setdefault(prehash, [])
                    self.block_buffer[prehash].append(message)

            elif isinstance(message, ExtraMessage): # 处理ExtraMessage
                DEAL_WITH_OTHER_INCOMING_MESSAGES
                self.state = NEXT_STATE # 接收到其他消息时的状态转移
            elif ...:
                ...
```

上述代码根据_receive_tape中消息的类型分别处理，如果传入的是区块就尝试验证并将其合并到本地链中。一般local_state_update需要调用valid_chain方法验证传入区块所在的链，因此需要在MyConsensus中实现valid_chain与valid_block方法。一般valid_chain方法会核对链上区块的prehash，确认链上区块能否能正确构成哈希链，并调用valid_block验证每个区块的合法性。valid_chain的写法可以参考PoW.valid_chain。

最后，如果需要使共识类MyConsensus可配置，还需要修改_\_init\_\_方法并在system_config.ini中增加配置项。\_\_init\_\_可参考以下范例：

```python
    def __init__(self, miner_id, consensus_param):
        super().__init__(miner_id)
        self.state = INITIAL_STATE # 状态初始化
        self.a = consensus_param['param_a']
        self.b = int(consensus_param['param_b']) # 类型转换
```

\_\_init\_\_修改后，就可以在system_config.ini中的ConsensusSettings部分增加配置项param_a与param_b。需要注意的是，对于consensus.PoW以外的共识类，所有ConsensusSettings下的配置项会以字典形式通过consensus_param原样传递给MyConsensus。如果在system_config.ini中配置如下：

```ini
[ConsensusSettings]
param_a=value_a
param_b=100
```

那么传递给MyConsensus.\_\_init\_\_的consensus_param为`{'param_a':'value_a','param_b':'100'}`。

目前ChainXim在初始化时根据consensus_type配置项的值动态导入共识类，如果需要在仿真中使用MyConsensus类，需要在system_config.ini中配置如下：
```ini
consensus_type=consensus.MyConsensus
```
并在consensus/\_\_init\_\_.py中添加一行（假设MyConsensus类定义于consensus/myconsensus.py）：
```python
from .myconsensus import MyConsensus
```

## 网络接口 Network Interface
在介绍网络模块之前，首先介绍网络接口，定义于`./miner/network_interface`，用于模拟网卡（NIC）的行为，作为矿工和网络之间交互的通道。在矿工初始化时并加入网络时，会根据网络类型在矿工中初始化一个NIC实例。

```python
def _join_network(self, network):
    """初始化网络接口"""
    if (isinstance(network, TopologyNetwork) or 
        isinstance(network, AdHocNetwork)):
        self._NIC = NICWithTp(self)
    else:
        self._NIC = NICWithoutTp(self)
    if isinstance(network, AdHocNetwork):
        self._NIC.withSegments = True
    self._NIC.nic_join_network(network)
```
矿工将共识过程产生的消息（目前仅有区块）通过该NIC实例发送到网络中；而网络也通过该NIC实例，将正在传播的区块发送给目标矿工。
根据网络的类型不同，可以将网络分为两类：不带拓扑信息的抽象网络（SynchronousNetwork、StochPropNetwork、DeterPropNetwork）和带拓扑信息的拟真网络（TopologyNetwork、AdHocNetwork）。对应将Network Interface分为两类：`NICWithoutTp`和`NICWithTp`。这两类网络接口都继承自抽象基类`NetworkInterface`。在具体介绍网络接口前，先介绍一些`./miner/_consts.py`中预先定义的一些常量。


### 网络接口相关常量 _consts.py
网络接口在实现时需要使用一些常量，这些常量预定义在文件`./miner/_consts.py`中，主要分为以下几类：
#### 1. 转发策略
TopologyNetwork、AdHocNetwork中，矿工需要对产生的消息指定转发策略。目前定义了三种：

| 常量                         |  具体值   | 解释                           |
| ---------------------------- | --- | ------------------------------ |
| FLOODING        |  "flooding"    | 泛洪转发，即向所有邻居节点转发 |
| SELFISH          | "selfish"     | 自私转发，即不进行转发操作     |
| SPEC_TARGETS  |   "spec_tagets"  | 指定转发目标                   |

#### 2. 待转发消息来源
消息的来源即该消息是自己产生的还是从外部网络中接收到的。该常量的设置主要是因为在不同网络中对不同来源的消息有不同的处理：无拓扑的抽象网络（SynchronousNetwork、StochPropNetwork、DeterPropNetwork）中仅会转发自己产生的消息；而带拓扑的拟真网络（TopologyNetwork、AdHocNetwork）两种来源的消息都会转发。

| 常量                        | 具体值    | 解释                         |
| --------------------------- | --- | ---------------------------- |
| SELF   |  "self_generated_msg"   | 该消息是自己产生的           |
| OUTER      |   "msg_from_outer"  | 该消息是从外部网络中接收到的 |

#### 3. 信道状态
在TopologyNetwork、AdHocNetwork中用于标记信道状态。

| 常量           | 具体值    | 解释                 |
| -------------- | --- | -------------------- |
| _IDLE   |  "idle"   | 信道空闲             |
| _BUSY  |   "busy"  | 信道中有消息正在传递 |

### 网络接口抽象基类 NetworkInterface
网络接口抽象基类，定义了应当实现的抽象接口。位于`.\network\nic_abc.py`中。首先定义了所有网络接口共同拥有的成员变量，以及各网络接口需要实现的抽象方法。

| 成员变量        | 类型                   | 解释                                                         |
| --------------- | ---------------------- | ------------------------------------------------------------ |
| miner           | Miner                  | 持有该网络接口的矿工                                         |
| miner_id        | int                    | 持有该网络接口的矿工ID                                       |
| _network        | Network                | 环境中的网络实例                                             |
| _receive_buffer | list[Packet]           | 缓存本轮中从网络中接收到的数据包                             |
| _forward_buffer | dict[str, list[Block]] | 缓存将要发送到网络中的消息队列（目前仅有Block）；key表示该消息的来源，OUTER和SELF |

| 成员方法              | 输入参数                                               | 解释                                                         |
| --------------------- | ------------------------------------------------------ | ------------------------------------------------------------ |
| append_forward_buffer | msg:Message, type:str, strategy: str, spec_target:list | 将要转发的消息msg添加到_forward_buffer中，并指定消息类型 type（OUTER/SELF），转发策略strategy（默认FLOODING），指定目标spec_target仅在SPEC_TARGETS策略有效。 |
| nic_join_network      | network:Network                                        | 抽象方法。在矿工初始化并加入网络时，初始化网络接口           |
| nic_receive           | packet: Packet                                         | 抽象方法。接收网络中的数据包，并传递给矿工。                 |
| nic_forward           | list[Packet]                                           | 抽象方法。将_forward_buffer中的消息按照规则发送到网络中。    |

以下方法只有TopologyNetwork、AdHocNetwork两个网络需要实现：

| 成员方法        | 输入参数                             | 解释                                                         |
| --------------- | ------------------------------------ | ------------------------------------------------------------ |
| remove_neighbor | remove_id:int                        | 抽象方法。移除指定的邻居。                                   |
| add_neighbor    | add_id:int                           | 抽象方法。添加指定的邻居。                                   |
| reply_getdata   | inv:INVMsg                           | 抽象方法。回应inv消息，索要缺失的区块。                      |
| get_reply       | msg_name, target:int, err:str, round | 抽象方法。消息成功发送到目标矿工，或发送失败时，原矿工获得消息发送结果。 |


### NICWithoutTp
矿工和网络之间通过网络接口进行交互的大致流程如下：
1. 矿工在有消息需要传播时（通过自身共识产生或从外部网络接收），通过forward函数中将待转发消息写入NIC的_forward_buffer对应的消息队列中；
2. 在每一轮结束时，网络在diffuse时调用每个矿工NIC中的nic_forward函数，将_forward_buffer中的消息接入网络，并按照网络规则进行传播；
3. 网络将消息传递给目标矿工时，会调用目标矿工NIC的nic_receive函数，该函数负责通过矿工receive接口将消息传递给矿工，供共识层处理。

对于不包含拓扑信息的网络接口NICWithoutTp，在上述过程2中，仅转发处理_forward_buffer中由自身产生的消息，即SELF消息队列中的内容。主要的成员方法如下：

| 成员方法        | 输入参数                             | 解释                                                         |
| --------------- | ------------------------------------ | ------------------------------------------------------------ |
| nic_receive           | packet: Packet                                         | 接收网络中的数据包，并传递给矿工。                 |
| nic_forward           | list[Packet]                                           | _forward_buffer中SELF消息队列的内容通过access_netork发送到网络中。    |


### NICWithTp

| 成员方法              | 输入参数                                               | 解释                                                         |
| --------------------- | ------------------------------------------------------ | ------------------------------------------------------------ |
| nic_receive           | packet: Packet                                         | 接收网络中的数据包，并传递给矿工。                 |
| nic_forward           | list[Packet]                                           | _forward_buffer中的消息按照规则发送到网络中，具体过程在后文介绍。    |
| remove_neighbor | remove_id:int                        |移除指定的邻居。                                   |
| add_neighbor    | add_id:int                           |添加指定的邻居。                                   |
| reply_getdata         | inv:INVMsg                           |回应inv消息，索要缺失的区块。                      |
| get_reply       | msg_name, target:int, err:str, round |消息成功发送到目标矿工，或发送失败时，原矿工获得消息发送结果。 |

## 网络 Network
网络层的主要功能是接收环境中产生的新区块，并通过一定的传播规则传输给其他矿工，作为矿工之间连接的通道。网络层由抽象基类Network派生出不同类型的网络。目前实现了抽象概念的同步网络（SynchronousNetwork）、随机性传播网络（StochPropNetwork），确定性传播网络（DeterPropNetwork）和相对真实的拓扑P2P网络（TopologyNetwork）。

### 抽象基类 Network
Network基类规定了三个接口，外部模块只能通过这三个接口与网络模块交互；同时也规定了输入参数，派生类不可以更改


| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
| set_net_param   | \*args, \*\*kargs     | 设置网络参数。在环境类初始化时设置网络参数。main由配置文件加载网络参数信息到环境。    |
| access_network   | new_msg:list[Message], minerid:int,<br>round:int     | 接收所有新产生的消息对象进入网络，等待传播。同时将各消息对象和传播相关信息封装成 [Packet](#BlockPacket)。   |
| diffuse  | round:int     | 最主要的函数。在exec每轮结束时调用，具体实现网络的传播规则    |


在介绍具体的4种网络前，先介绍消息数据包Packet。

### 消息数据包 <span id="BlockPacket">Packet</span>
消息对象通过access_network进入网络后被封装为Packet，除了进入网络的消息对象外还包含传播相关信息。
网络中消息对象以Packet的形式传播，待传播的Packet存储在网络的**network_tape**属性中。
Packet在不同的网络类中有不同的具体实现。如：
- SynchronousNetwork中，仅包含消息对象和产生该消息的矿工id；
- StochPropNetwork中，还包含对应的当前接收概率；
- DeterPropNetwork中，记录了传播向量；
- TopologyNetwork中，记录了消息的来源、目标等。

以TopologyNetwork中的PacketPVNet为例：
    
```python
# network/propvec.py
class PacketPVNet(Packet):
    '''propagation vector网络中的数据包，包含路由相关信息'''
    def __init__(self, payload: Message, source_id: int, round: int, prop_vector:list, outnetobj):
        super().__init__(source_id, payload)
        self.payload = payload
        self.source = source_id
        self.round = round
        self.outnetobj = outnetobj  # 外部网络类实例
        # 传播过程相关
        self.received_miners:list[int] = [source_id]
        self.trans_process_dict = {
            f'miner {source_id}': round
        }
        # 每轮都pop第一个，记录剩余的传播向量
        self.remain_prop_vector = copy.deepcopy(prop_vector)
```


**接下来介绍各种网络如何实现三种接口。**
### 同步网络 SynchronousNetwork
除产生消息的矿工外，所有矿工都在下一轮次开始时接收到新产生的消息

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
| set_net_param   | \*args, \*\*kargs       | 同步网络无需参数    |
| access_network   | new_msg:list[Message], minerid:int,<br>round:int    | 将消息对象、矿工id、当前轮次封装成PacketSyncNet，加入network_tape。 |
| diffuse  | -     | 在下一轮次开始时，所有矿工都收到network_tape中的数据包|



### 随机性传播网络StochPropNetwork
新消息在进入网络后，每轮次以不断增加的概率被各矿工接收（时延），且至多在接收概率达到1后被所有矿工接收（有界）。

**网络参数**：


| 属性 | 说明 |
| -------- | -------- |
| rcvprob_start（float）     | 初始接收概率。即该消息进入网络时，在下一轮被某个矿工接收的概率     |
| rcvprob_inc（float）     | 消息进入网络后，每轮增加的接收概率   |

例如，rcvprob_start=rcvprob_inc=0.2的情况下，新消息在进入网络后，所有其他矿工必定在5轮内接收到消息。

**接口函数**：

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
| set_net_param   | \*args, \*\*kargs      | 设置rcvprob_start，rcvprob_inc    |
| access_network   | new_msg:list[Message], minerid:int,<br>round:int     |消息对象、矿工id、当前轮次封装成PacketBDNet加入network_tape。并初始化该数据包的接收概率，同时记录传播过程 |
| diffuse   | round:int     | network tape中的各个Packet以不断增加概率被各矿工接收，当前接收概率更新到PacketBDNet。在被所有矿工都接收到时，将其在network_tape中删除，并把传播过程保存在network log.txt中。<br>**注：当发送给攻击者时，其他攻击者也立即收到**|

**重要函数**

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
|record_block_propagation_time|- |记录消息传播时间|
|save_trans_process|-|保存传播过程|

### 确定性传播网络 DeterPropNetwork
给定传播向量，网络依照传播向量，每轮次开始时将消息对象发送给固定比例的矿工。

**网络参数**：


| 属性 | 说明 |
| -------- | -------- |
| prop_vector（list）     | 传播向量。例如prop_vector=[0.1, 0.2, 0.4, 0.6, 0.8, 1.0]表示下一轮开始前接收到该消息的矿工比例为0.1，再一轮过后比例为0.2，直到五轮过后全部矿工都接收到该消息。|


**接口函数**：

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
| set_net_param   | \*args, \*\*kargs      | 设置prop_vector   |
| access_network   | new_msg:list[Message], minerid:int,<br>round:int     |所有新消息、矿工id、当前轮次封装成数据包（PacketPVNet）加入network_tape。并初始化该数据包的传播向量，同时记录传播过程 |
| diffuse   | round:int     |  依照传播向量,在每一轮中将数据包传播给固定比例的矿工<br>**注：当发送给攻击者时，其他攻击者也立即收到，此时可能出现比例不一致的情况。** |

**重要函数**

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
|record_block_propagation_time|- |记录消息传播时间|
|save_trans_process|-|保存传播过程|


### 拓扑P2P网络 TopologyNetwork
通过csv文件或随机方式生成网络拓扑和各矿工间的带宽。消息通过矿工的网络接口进入网络后，在指定的来源和目标之间建立链路(Link)进行传播，每条Link的传输时间（轮次）由链路带宽与区块大小决定。同时链路可能以预设的outage_prob概率中断，此时发送方会重新发送消息。

**网络参数**：

| 属性                      | 说明  |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| init_mode (str)    | 网络初始化方法, 'adj'邻接矩阵, 'coo'稀疏的邻接矩阵, 'rand'随机生成。'adj'和'coo'的网络拓扑通过csv文件给定。'rand'需要指定带宽、度等参数 |
|outage_prob(float)|每条链路的中断概率|
| dynamic(bool)  |网络拓扑是否动态变化 |
| avg_tp_change_interval(int)   |dynamic=true时，设置拓扑变化的平均轮次      |
| edge_remove_prob(float)   |dynamic=true时，设置拓扑变化时，已存在的每条边移除的概率      |
| edge_add_prob(float)   |dynamic=true时，设置拓扑变化时，未存在的条边新建立连接的概率      |
|max_allowed_partitions(int)|dynamic=true时,设置拓扑变化时，最大可存在的分区数量|
| ave_degree (int)          | 网络生成方式为'rand'时，设置拓扑平均度                                                                                                    |
| bandwidth_adv（float）    | 攻击者之间的带宽，单位MB/round                                                                                                            |
| save_routing_graph (bool) | 是否保存各消息的路由传播图。建议网络规模较大时关闭                                                                                        |
|enable_resume_transfer (bool)|是否开启链路中断恢复,当enable_resume_transfer=True时,链路发生中断后,发送方会重新发送剩余消息,否则会重新发送整个消息；而在链路因动态拓扑而断开时，若后续恢复仍然会重新发送整个消息|

**接口函数**：

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
| set_net_param   | \*args, \*\*kargs      | 设置如上网络参数 |
| access_network   | new_msg:list[Message], minerid:int,<br>round:int       |将新消息、矿工id和当前轮次封装成Packet，加入network_tape|
| diffuse  | round:int    | diffuse分为**receive_process**和**forward_process**两部分|

- `receive_process` 将传播完成的msg发给接收方;

```python
def receive_process(self,round):
    """接收过程"""
    if len(self._active_links)==0:
        return
    dead_links = []
    for i, link in enumerate(self._active_links):
        # 更新链路delay
        if link.delay > 0:
            link.delay -= 1
        # 判断链路是否中断
        if self.link_outage(round, link):
            dead_links.append(i)
            continue
        if link.delay > 0:
            continue
        # 链路传播完成，target接收数据包
        link.target_miner()._NIC.nic_receive(link.packet)
        link.source_miner()._NIC.get_reply(
            link.get_block_msg_name(),link.target_id(), None, round)
        dead_links.append(i)
    # 清理传播结束的link
    if len(dead_links) == 0:
        return
    self._active_links = [link for i, link in enumerate(self._active_links) 
                        if i not in dead_links]
    dead_links.clear()
```

- `forward_process` 从矿工NIC中取得将要传播的msg进入网络；

```python
def forward_process(self, round):
    """转发过程"""
    for m in self._miners:
        m._NIC.nic_forward(round)
```

**其他重要函数**：

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
| cal_delay   |  msg:Message, sourceid:int, targetid:int    |计算两矿工间的时延，包括传输时延和处理时延两部分。同时向上取整，且最低为1轮。<br>计算公式为：`delay=trans_delay+process_delay， trans_delay=(blocksize*8)/bandwidth` |
| generate_network | -     | 根据网络参数生成网络。|
| write_routing_to_json | -     | 每当一个block传播结束,将其路由结果记录在json文件中，其中包含origin_miner和routing_histroy两信息|
| gen_routing_gragh_from_json | -     | 读取routing_histroy.json文件,并将其转化为routing_gragh.svg图像，保存在Network Routing文件夹中。|
|record_block_propagation_time||记录消息传播时间。|


### 无线自组织网络 AdHocNetwork

在给定正方形区域中随机生成节点位置，设置节点间通信范围，通信范围内的节点会自动建立连接，可以互相传递消息。每一轮次节点进行高斯随机游走，即在x和y坐标加上一个零均值、给定方差的高斯随机变量，并根据节点通信范围，断开旧连接或建立新的连接。
每个消息在传输前会被分段(Segment)，每一段的传输时间都是一轮，接收方NIC只有接收到全部分段后，才会将完整的消息传递给共识层。

**网络参数**：

| 属性                 | 说明                                             |
| -------------------- | ------------------------------------------------ |
| init_mode (str)      | 网络初始化方法，目前仅支持随机生成                                 |
| outage_prob(float)   | 每条链路的中断概率                               |
| segment_size(float)   | 消息分段大小                                     |
| region_width(int)    | 正方形区域的宽度，节点在该区域中进行高斯随机游走 |
| comm_range(int)      | 节点通信距离，在通信距离内的两节点自动建立连接   |
| move_variance(float) | 节点进行高斯随机游走时，指定xy坐标移动距离的方差 |
| outage_prob(float)   | 链路中断概率                                     |
| enable_large_scale_fading(bool) | 是否开启大尺度衰落，当开启时，segment_size将由衰落模型和bandwidth_max来确定 |
| path_loss_level(str) | low/medium/high分别对应衰落系数为0.8/1/1.2 |
| bandwidth_max(float) | MB/round；comm_range/100范围之内的带宽，即能达到的最大带宽 |

**接口函数**：

| 函数 | 参数 | 说明 |
| -------- | -------- | -------- |
| set_net_param   | \*args, \*\*kargs      | 设置如上网络参数 |
| access_network   | new_msg:list[Message], minerid:int,<br>round:int       |将新消息、矿工id和当前轮次封装成Packet，加入network_tape|
| diffuse  | round:int    | diffuse分为**receive_process**和**forward_process**|

### 大尺度衰落

#### 衰落模型

在AdHoc网络中，可以开启大尺度衰落模型来模拟真实无线网络中的路径损耗。当enable_large_scale_fading=True时,系统将根据节点间距离计算实际带宽。

路径损耗模型采用对数距离模型:

$L(d) = L(d_0)+10nlg(d/d_0)$

其中，d为节点间距离，d0为参考距离,设为通信范围的1%，n为路径损耗因子,可通过path_loss_level设置（low: n=0.8, medium: n=1.0, high: n=1.2）

基于路径损耗模型,节点间实际带宽计算公式为:

$B\left(d\right) = B\left(d_0\right)·10^{\left(L(d_0)-L(d)\right)/10} = B\left(d_0\right)·\left(d_0/d\right)^n$

其中，B(d0)为参考距离d0处的带宽,由bandwidth_max参数指定，B(d)为距离d处的实际带宽

segment_size由bandwidth_max和通信距离（Comm_range）决定，为`通信距离/100*bandwidth_max`。每轮可传输的分段数由实际带宽除以segment_size向上取整得到。当发生信道中断时,将中断当前传输的所有分段。

大尺度衰落性能参考：

Comm_range = 30   (Reference distance: d0 = Comm_range/100)

bandwidth_max = 30   (Bandwidth at the reference point)

path_loss_level = low (n=0.8)

<img src="doc/fading_08.png" alt="large_scale_fading" width="600" />

path_loss_level = medium (n=1)

<img src="doc/fading_10.png" alt="large_scale_fading" width="600" />

path_loss_level = high (n=1.2)

<img src="doc/fading_12.png" alt="large_scale_fading" width="600" />

## 攻击层 Attack

攻击者通过感知环境，判断当前形势并作出攻击行为判决，执行当前较优的攻击决策。目前，攻击者部分还未实现动态决策，需要在仿真器运行前修改system_config.ini中的参数以设置不同的攻击策略。（内容等日蚀攻击全部完善之后再继续更新）

### 攻击层与整体的交互逻辑
下图为某一回合攻击模块的运行示例，攻击模块实际进行的部分为下图虚线框内所示。t个攻击者散布在矿工之间（编号可在system_config.ini中指定）。每个轮次中，攻击模块只会被触发一次，每次触发都会进行一次完整的攻击行为（例如，以所有矿工每轮次计算哈希数q均相同的PoW为例，攻击者每次攻击行为可以执行t*q次哈希计算）**当前版本中，每轮次攻击者会在随机位置被触发，主要防止攻击者在固定位置触发影响公平性。** 攻击模块主要与网络和环境进行交互，与环境交互的主要内容为感知当前“局势”与向全局链上传区块两个部分；与网络交互的内容主要是将区块发送至网络。

<img src="doc/attack.png" alt="attack" width="600" />

### 已实现的攻击方式(Attack Type)
- 算力攻击(Honest Mining)
- 自私挖矿(Selfish Mining)
- 双花攻击(Double Spending)
- 日蚀双花攻击(Eclipsed Double Spending)


### 攻击层代码结构(Package Tree)
```
├─ attack
│  ├─ adversary.py
│  ├─ attack_type
│  │  ├─ atomization_behavior.py
│  │  ├─ attack_type.py
│  │  ├─ double_spending.py
│  │  ├─ eclipsed_double_spending.py
│  │  ├─ honest_mining.py
│  │  ├─ selfish_mining.py
│  │  └─ _atomization_behavior.py
│  └─ _adversary.py
```

### _adversary.py & adversary.py

_adversary.py提供Adversary抽象父类，用于adversary.py提供的Adversary继承。环境import文件adversary.py中的Adversary类，并创建对象，随后根据环境传参初始化所有Adversary设置。该Adversary对象作为攻击者全体代表的抽象，执行攻击。

#### >>> _adversary.py & adversary.py中的成员变量

##### 内部成员变量

| 成员变量                | 类型               | 解释                                                                                                         |
| ----------------------- | ------------------ |------------------------------------------------------------------------------------------------------------ |
| __Miner_ID              | int                | 值为-1，不变。在初始化过程中，类似普通矿工Adversary也需要初始化共识consensus，因此需要提供一个不被重复的ID。 |
| __adver_num             | int                | 记录攻击者的数量。                                                                                                             |
| __attack_type           | class: AttackType  |  根据设置创建攻击类型对象，若未设置则默认是HonestMining。                                                                                                            |
| __excute_attack         | class: AttackType  | 用来执行攻击的攻击类型对象。                                           |
| __adver_ids             | list[int]          |记录了攻击者ID的list。                                                                                                              |
| __miner_list             | list[class: Miner] |记录了全体矿工的list。                                                                                                              |
| __global_chain          | class: Chain       |记录了当前全局链对象，环境创建，并传给Adversary。                                                                                                              |
| __adver_consensus_param | dict               |以dict的形式记录了攻击者执行的共识对象需要的参数。                                                                                                              |
| __consensus_type        | class: Consensus   |根据设置创建共识类型对象。                                                                                                              |
| __attack_arg            | dict               |记录了攻击参数。（目前攻击中仅有DoubleSpending需要该参数。                                                                                                              |

#### >>> _adversary.py & adversary.py中的成员方法

##### 内部方法

|成员方法|输入参数（类型）|返回值: 类型|解释|
|---|---|---|---|
|__adver_setter()|**args: any|None|环境创建Adversary对象时，初始化阶段自动执行的成员方法，根据传参设置所有的成员变量。|
|__adver_gener()|None|__adver_list: list[class: Miner]|根据设置，在全体矿工中生成随机或指定的攻击者。|
|__consensus_q_init()|None|None|重新计算攻击者群体抽象对象Adversary的算力q（为所有攻击者的算力累加）。|
|__attack_type_init()|None|None|初始化攻击类型对象的成员变量，由上述的成员变量确定。|

##### 外部方法

|成员方法|输入参数: 类型|返回值: 类型|解释|
|---|---|---|---|
|get_adver_ids()|None|__adver_ids: list[int]|返回记录攻击者ID的list。|
|get_adver_num()|None|__adver_num: int|返回攻击者数量。|
|get_attack_type_name()|None|__attack_type.__class__.__name__: str|返回攻击类型的名字。|
|get_attack_type()|None|__attack_type: AttackType|返回攻击类型的名字。|
|get_eclipsed_ids()|None|__eclipsed_list_ids: list[int]|返回被月蚀攻击的矿工的名字。|
|get_adver_q()|None|__consensus_type.q: int|初始化攻击类型对象的成员变量，由上述的成员变量确定。|
|excute_per_round(round)|round: int|None|Adversary的主要方法，执行攻击，会调用对应攻击类型对象的成员方法。|
|get_info()|None|None or __attack_type.info_getter()|调用对应攻击类型对象的成员方法，获得当前的信息。一般包含成功率（或主链质量）以及对应理论值。|

### _atomization_behavior.py & atomization_behavior.py

_atomization_behavior.py为父类，atomization_behavior.py继承，在后者中实现了具体的原子化行为(Atomization Behavior，下简称AB)。规定父类，是因为AB中有必须实现的行为，通过父类给出一个行为标准，其构成攻击的基础。此外还想添加功能直接在继承类中添加即可。因为该继承类为方法类，没有成员变量，以下详细介绍AB的方法（非表格形式）。

#### 原子化行为(Atomization Behavior)

#### >>> 1. renew()
renew的作用为更新攻击者的所有区块链状态：基准链、攻击链、矿工状态（包括输入和其自身链）等。当前版本的renew仅有round作为输入参数，round可以视为一种环境状态。攻击者的_receive_tape中包含了以攻击者为视角，每回合能够接受到的最新区块。    

renew中攻击者遍历其控制的每一个矿工。所有矿工都如诚实矿工一样执行local_state_update（详见[共识部分](#如何实现新的共识协议)）。根据local_state_update具体结果对字典进行更新。

若存在更新，则将新产生的区块更新到基准链和全局链上。前者作为攻击者攻击的参考基准（攻击者视角下最新的链），后者作为区块链维护者有义务将最新的区块记录在全局中。

总结：renew至少需要以下三部分功能：

* 对每个攻击者矿工进行local_state_update。

* 根据更新结果更新基准链。

* 根据需要将每轮的更新结果进行记录。
  

若开发者想要开发新的攻击模式，可以根据需要调整三部分的具体内容，或增加其他功能，但这三部分功能是不能少的。
（日蚀攻击的判断策略略复杂，这里不赘述，需要的开发者可查阅代码）
    
#### >>> 2. mine()
mine调用当前的共识方法，并执行共识方法对应的挖矿功能（即诚实挖矿）。当前版本的mine会在攻击者中随机选取一个作为当前回合作为挖矿的“代表”。此外，源代码中也提供了通过ID指定矿工挖矿的功能。

若产生区块，则对攻击链（adver_chain）进行更新

并遍历所有攻击者，将区块更新至攻击者的_receive_tape中。目的有二，一是令攻击者直接能共享区块（下一回合收到），二是在下一回合可以将该区块更新到基准链中。

mine模块的内容一般不会有大的改动，因为其主要功能就是调用共识的挖矿功能，并根据结果更新对应的区块链。
#### >>> 3. upload()
向网络上传Adversary的区块。
（具体上传哪些区块的判断逻辑见对应代码段注释）

#### >>> 4. adopt()
adopt用于将基准链（honset_chain）的结果更新到攻击链（adver_chain）上。攻击链可以看作攻击集团共同维护的一条链，而不是各恶意矿工自身的链，因此还要更新每个恶意矿工的本地链。

#### >>> 5. clear()
清除攻击者中所有矿工的输入和通信内容。设计clear的目的意在消除本回合的输入内容对下一回合的影响，因此clear应置于一系列行为之后。

#### >>> 6. wait()
wait是让攻击模块等待至下一回合再继续运行。因此并没有对wait部分设计具体行为，当攻击实例执行这两个操作时也不会做出实际行动。

### attack_type.py & honest_mining.py, selfish_mining.py, eclipsed_double_spending.py
#### >>> attack_type.py中的成员变量
##### 外部变量
未说明的成员变量，其含义与前述一致。

| 成员变量 | 类型 | 说明 |
| -------- | -------- | -------- |
| behavior | class: AtomizationBehavior | 记录AtomizationBehavior类型的方法类对象。 |
| honest_chain | class: Chain | 以Adversary视角更新的诚实链。Adversary除了在其上更新诚实节点的区块外，一般不会进行额外操作，也是Adversary放弃进攻后，接纳并更新adver_chain的参考。 |
| adver_chain | class: Chain | Adversary本地的链，一般与honest_chain不保持一致。 |
| adver_list | list[class: Miner] | -------- |
| eclipsed_list_ids | list[int] | -------- |
| adver_consensus | class: Consensus | -------- |
| attack_arg | dict | -------- |

#### >>> attack_type.py中的成员方法
##### 内部方法

| 成员方法 | 输入参数: 类型 | 返回参数: 类型 | 说明 |
| -------- | -------- | -------- | -------- |
| __set_behavior_init() | None | None | 创建AtomizationBehavior类型的方法类对象。 |

##### 外部方法

| 成员方法 | 输入参数: 类型 | 返回参数: 类型 | 说明 |
| -------- | -------- | -------- | -------- |
| set_init() | adver_list:list[Miner], miner_list:list[Miner], network_type: Network, adver_consensus: Consensus, attack_arg:dict, eclipsed_list_ids:list[int] | None | 对攻击类型对象的所有成员变量赋值。 |

##### 抽象方法

| 成员方法 | 输入参数: 类型 | 返回参数: 类型 | 说明 |
| -------- | -------- | -------- | -------- |
| renew_stage(round) | round: int | newest_block: Block, mine_input: any | 执行更新阶段。 |
| attack_stage(round,mine_input) | round: int | None | 执行攻击阶段。 |
| clear_record_stage(round) | round: int | None | 执行清除和记录阶段。 |
| excute_this_attack_per_round(round) | round: int | None | 执行当前攻击。 |
| info_getter() | None | None | 返回当前攻击信息。 |

#### 以HonestMining为例说明
攻击主要分为三个阶段：renew阶段，attack阶段，和clear and record阶段。
##### >>> renew阶段：

```python
def renew_stage(self,round):
        ## 1. renew stage
    newest_block, mine_input = self.behavior.renew(miner_list = self.adver_list, \
                                 honest_chain = self.honest_chain,round = round)
    return newest_block, mine_input
```
从上面展示的renew阶段源代码可以注意到，renew阶段需要返回两个参数，一个是newest_block一个是mine_input。而renew阶段也以renew()方法为主。

##### >>> attack阶段：
```python
def attack_stage(self,round,mine_input):
        ## 2. attack stage
    current_miner = random.choice(self.adver_list)       
    self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
    attack_mine = self.behavior.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
    if attack_mine:
        self.behavior.upload(network_type = self.network_type, adver_chain = self.adver_chain, \
              current_miner = current_miner, round = round)
    else:
        self.behavior.wait()
```
attack阶段Adversary要根据条件执行adopt(), mine(), upload(), wait()。根据具体的攻击策略判断如何组合这些方法。HonestMining策略非常简单，只要挖出区块就发布，否则就等待。注意到即使是最简单的HonestMining也未必每轮都会与网络交互。
具体到Selfish Mining和Double Spending，因为策略比较复杂，源代码也比较复杂，若需要可以直接查看源代码。

##### >>> clear and record阶段：

```python
def clear_record_stage(self,round):
    ## 3. clear and record stage
    self.behavior.clear(miner_list = self.adver_list)# 清空
    self.__log['round'] = round
    self.__log['honest_chain'] = self.honest_chain.lastblock.name + ' Height:' + str(self.honest_chain.lastblock.height)
    self.__log['adver_chain'] = self.adver_chain.lastblock.name + ' Height:' + str(self.adver_chain.lastblock.height)
    self.resultlog2txt()
```
这个阶段比较简单，主要是调用clear()方法，清空矿工内部的冗余数据，并记录一些需要的信息到日志dict中。


## 评估 Evaluation
```Environment.exec```执行完成后，将执行```Environment.view_and_write```，对仿真结果进行评估与输出。


* view_and_write首先调用view，获取统计数据，并输出结果到命令行

* view会调用global_chain中的```CalculateStatistics```函数，对全局区块链树状结构进行数据统计，并将结果更新到字典变量stat中。

* 之后，将从共同前缀（common prefix）、链质量（chain quality）、链增长（chain growth）三个维度对全局区块链进行数据统计。这三部分由external.py中的对应函数实现。

* 其次，调用network中的```cal_block_propagation_times```函数，获取网络相关的统计参数。

* 最后，```view_and_write```将评估结果输出到文件中。

以下为stat中统计参数的解释，它们和仿真器最后的输出结果相对应(见[仿真器输出](#仿真器输出-Simulator-Output))：

|字典条目|解释/计算方式|
|---|---|
|num_of_generated_blocks|生成的区块总数|
|height_of_longest_chain|仿真中出现的最长链的高度|
|num_of_valid_blocks|主链中的区块总数（主链长度）|
|num_of_stale_blocks|孤块数（不在主链中的区块）|
|stale_rate|孤块率=孤块数/区块总数|
|num_of_forks|（主链上的）分叉数|
|fork_rate|分叉率=主链上有分叉的高度数/主链高度|
|average_block_time_main|主链平均出块时间=总轮数/主链长度|
|block_throughput_main|主链区块吞吐量=主链长度/总轮数|
|throughput_main_MB|=主链区块吞吐量\*区块大小|
|average_block_time_total|总平均出块时间=总轮数/生成的区块总数|
|block_throughput_total|总区块吞吐量=生成的区块总数/总轮数|
|throughput_total_MB|=总区块吞吐量\*区块大小|
|valid_dataitem_throughput|有效DataItem吞吐量|
|block_average_size|每个区块的平均大小（平均DataItem数量*每个DataItem大小）|
|input_dataitem_rate|DataItem的输入速率|
|total_round|运行总轮数|
|common_prefix_pdf|统计共同前缀得到的pdf（统计每轮结束时，所有诚实节点的链的共同前缀与最长链长度的差值得到的概率密度分布）|
|consistency_rate|一致性指标=common_prefix_pdf[0]|
|average_chain_growth_in_honest_miners'_chain|诚实矿工链长的平均增加值|
|chain_quality_property|链质量字典，记录诚实节点和恶意节点的出块数目|
|double_spending_success_times|双花攻击成功次数|
|valid_dataitem_rate|有效的DataItem占全部链上DataItem的比例|
|ratio_of_blocks_contributed_by_malicious_players|恶意节点出块占比|
|upper_bound t/(n-t)|恶意节点出块占比的上界(n为矿工总数，t为恶意矿工数目)|
|block_propagation_times|区块传播时间（分布）|

需要注意的是，上表中的**主链**定义为：**已经达成共识的诚实矿工的本地链的共同前缀**，在确定主链时，ChainXim将所有诚实矿工按照本地链的高度降序排列，然后取前consensus_miner_quantile的诚实矿工的本地链的共同前缀。在共同前缀之后的子区块没有被足够多的诚实矿工确认，因此不视作主链的一部分。

对于分叉率以及废块率，它们的区别是：

- 分叉率只看主链，看主链上出现分叉的区块（即有多个子区块的区块），将这个作为分叉数，除以主链的高度就是分叉率

- 废块率看的是所有在仿真期间产生的废块，囊括了所有以主链上的区块作为父或者祖先区块但是本身不在主链上的区块，废块数量除以在仿真期间产生的总区块数量就是废块率

为了评估攻击者的攻击能力，设计了若干个指标：

- ratio_of_blocks_contributed_by_malicious_players，又称为链质量（Chain Quality）指标，就是恶意节点产生的区块在主链上的比重

- double_spending_success_times，双花攻击的成功次数，一次成功的攻击被定义为：在一次因攻击者行为引发的分叉事件中，最终区块链主链选择了由攻击者引导产生的分支，该被采纳分支的第一个区块必须是由攻击者节点产生的并且分叉长度必须大于由N指定的区块确认延迟。评估时将统计在整个仿真过程中满足此定义的攻击成功总次数。

关于共同前缀、链质量和链增长三个指标的解释如下：

|性质|解释|
|-|-|
|Common Prefix|当恶意节点算力不超过一定比例时，诚实矿工维护的区块链总是有很长的共同前缀（把任意两个诚实矿工的链截掉一段，剩余部分（前缀）总是相同的）|
|Chain Quality|截取诚实矿工链中任意足够长的一段，其中恶意矿工产生的区块占比不会超过t/(n-t)(n为矿工总数，t为恶意矿工数目)|
|Chain Growth|诚实矿工的链总是至少以一定速率增长|

对应external.py中的函数实现如下：

|函数|输入参数|输出参数|说明|
|-|-|-|-|
|common_prefix|prefix1:Block，prefix2:Chain|共同前缀prefix1|计算两条区块链的共同前缀|
|chain_quality|blockchain:Chain|字典cq_dict;指标chain_quality_property|统计恶意节点出块占比|
|chain_growth|blockchain:Chain|区块链高度|获取区块链长度增长（即区块链高度）|

注意，common_prefix和chain_growth均仅实现了对应性质的部分功能：common_prefix只是计算两条区块链的共同前缀，而一致性指标根据每次仿真的日志统计出来而chain_growth仅返回区块链高度，计算链增长速率则在CalculateStatistics函数中完成。


有关以上三个指标更加详细的含义，可以阅读：

* J. A. Garay, A. Kiayias and N. Leonardos, "The bitcoin backbone protocol: Analysis and applications", Eurocrypt, 2015. <https://eprint.iacr.org/2014/765.pdf>
