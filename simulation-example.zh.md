## 精选示例 Featured Examples
本示例展示了ChainXim仿真系统不同网络模块以及攻击模块运行所得的部分结果，通过构建各模块协同运行的场景，系统验证了仿真结果与理论模型的拟合度。该示例主要提供了六个互不交叉的模块化组合仿真实例，每个实例均多维度展示了ChainXim仿真结果的合理性。

### 1. 同步网络中矿工数量与出块时间的关系

这个例子演示了同步网络模块的运行方式，同步网络假设所有消息都能在发出后立刻被全网同步，是最简单的网络模型，出块频率也相对稳定。其具体参数设置如下：

* 仿真次数：600000轮

* 矿工数：10-80

* 共识类型：PoW/VirtualPoW/SolidPoW

* 难度：0000FF...

* q_ave = 10

* 网络参数：SynchronousNetwork


使用配置文件[synchronous_noadv.ini](conf/synchronous_noadv.ini)，执行以下命令（需要相应修改矿工数和共识类型），即可快速复现不同共识下各个点的仿真结果：

```bash
python main.py -c conf/synchronous_noadv.ini --total_round 600000 --consensus_type consensus.PoW --miner_num 10
```

下图展示了网络中矿工数量与平均出块间隔之间的关系，随着矿工数量增多，系统出块间隔将持续降低。几种不同的PoW共识核心机理相同，只有应用场景的区别，因此它们得到的结果基本一致：

![block_time](doc/block_time.png)



### 2. 不同网络最大时延下的分叉率、孤块率与一致性

这个例子演示了随机性传播网络模块的运行方式，随机性传播网络给所有消息设置了初始接收参数，规定消息在发出后第一轮会以一定概率被矿工接收，若未收到，则后续每一轮各矿工接收概率将提升增长参数规定的数值，初始接收参数和增长参数事实上共同规定了网络的最大时延。其具体参数设置如下：

* 轮数：3000000

* 矿工数：20

* 共识类型：PoW

* q_ave:10

* 难度：000FFF...

* 网络类型：StochPropNetwork

* 网络参数：rcvprob_start=rcvprob_inc=1/最大轮数

使用配置文件[stochprop_noadv.ini](conf/stochprop_noadv.ini)，执行以下命令（需要相应修改rcvprob_start和rcvprob_inc）：

```bash
python main.py -c conf/stochprop_noadv.ini --total_round 3000000 --rcvprob_start 0.05 --rcvprob_inc 0.05
```

下图展示了系统分叉率与孤块率随最大传播时延的变化情况，两种指标都反映了系统不一致的情况，只是在统计方式上略有差异。可见两者都随时延增大而增大，且彼此差异较小：

---
分叉率/孤块率随最大传播时延的变化示意图

![latency-fork](doc/latency-fork.png)

下图展示了系统一致性随最大传播时延的变化情况，Common Prefix[0]、[1]、[2]分别代表共同前缀PDF的前三个分量,其中序数代表共同前缀与主链长度的差值（详见“仿真器输出”一节），可见一致性指标总是随时延增大而下降。

---
一致性指标随最大传播时延的变化示意图

![cp_bounded_delay](doc/cp_bounded_delay.png)

本例的绘图代码详见文件[result_plot.py](util/result_plot.py)


### 3. 不同单轮哈希算力下的增长率

这个例子演示了确定性传播网络模块的运行方式，确定性传播网络给消息设置了接收向量，规定消息在发出后各个轮次会被相应比例的矿工接收。由于传播函数完全确定，这一网络各性能指标变化情况会更加稳定。其具体参数设置如下：

* 轮数：4000000

* 矿工数：20

* 共识类型：PoW/VirtualPoW/SolidPoW

* q_ave:2-16

* 难度：000FFF...

* 网络类型：DeterPropNetwork

* 网络参数：prop_vector=[0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]


使用配置文件[deterprop_noadv.ini](conf/deterprop_noadv.ini)，执行以下命令（需要相应修改q_ave和共识类型）：

```bash
python main.py -c conf/deterprop_noadv.ini --total_round 4000000 --consensus_type consensus.PoW --q_ave 10
```

下图展示了系统吞吐量随单一节点平均算力的变化情况。可以看到其将随算力提高而相应增大：

![miningpower-throughput](doc/miningpower-throughput.png)

### 4. 不同挖矿难度目标下的分叉率

这个例子演示了拓扑网络模块的运行方式，拓扑网络考虑具体的节点与边。将节点连接设置为环形拓扑，并假设每条边上的消息都能在一轮内传完，则网络的消息传播情况易于确定，此时可以通过理论模型得到分叉率的近似解进行对照验证。其具体参数设置如下：

* 轮数：4000000

* 矿工数：32

* 共识类型：PoW/VirtualPoW/SolidPoW

* q_ave:1

* 区块大小：0MB

* 难度：0000FF...-000FFF... (difficulty=12~16)

* 网络类型：TopologyNetwork

* 网络参数：init_mode=coo; 采用环形拓扑


使用配置文件[topology_noadv.ini](conf/topology_noadv.ini)，执行以下命令（需要相应修改difficulty和共识类型）：

```bash
python main.py -c conf/topology_noadv.ini --total_round 4000000 --consensus_type consensus.PoW --difficulty 12
```

下图展示了分叉率随难度目标的变化情况。难度目标即为哈希函数输出需要小于的数值，因此其增大会导致系统出块率增大，分叉率也随之增大：

![target-fork](doc/target-fork.png)

图中的理论曲线由以下公式得到：

$$ f=1 - (1 - t)^{mq\sum_{n=1}^{d} i_n} $$

$t$即为图中横坐标展示的难度目标，$m$为矿工数量，$q$即为q_ave，表示平均每个矿工每一轮进行哈希查询的次数。
$i_n$表示在区块发出后的第n个轮次，收到该区块的矿工在全网的占比。

### 5. 不同区块大小下的吞吐量与分叉率

这个例子演示了无线自组织网络模块的运行方式，无线自组织网络下节点可以自由运动，链路连接情况也会因此而改变。这一网络下，区块大小会直接影响到整个网络的消息传播时延。其具体参数设置如下：

* 轮数：4000000

* 矿工数：40

* 共识类型：PoW

* q_ave:10

* 区块大小：2-20MB

* 难度：0000FF...

* 网络类型：AdHocNetwork

* 网络参数：ave_degree=3, region_width=100, comm_range=30, move_variance=5, outage_prob=0.01, 
bandwidth_max=100, enable_large_scale_fading = True, path_loss_level = low/medium/high

使用配置文件[adhoc_noadv.ini](conf/adhoc_noadv.ini)，执行以下命令（需要相应修改区块大小与路径损失）：

```bash
python main.py -c conf/adhoc_noadv.ini --total_round 4000000 --path_loss_level low --blocksize 2
```
下图展示了吞吐量随区块大小的变化情况，区块增大会导致时延变长，从而降低区块链的增长率，致使以MB为单位的吞吐量的增长逐渐减缓。更大的路径损失也会导致吞吐量的下降：

---
吞吐量随区块大小的变化示意图

![blocksize-throughput](doc/blocksize-throughput.png)

下图展示了分叉率随区块大小的变化情况，更差的网络时延条件以及更大的路径损失会导致更高的分叉率：

---
分叉率随区块大小的变化示意图

![blocksize-fork](doc/blocksize-fork.png)

### 6. 不同攻击向量下的攻击者出块占比示意图

这个例子依次演示了四种可用攻击模块的运行方式：

#### a. 算力攻击（honest mining）

算力攻击实际上为攻击者联合算力进行诚实挖矿，网络中攻击者块的占比将近似等于攻击者的算力占比，这一占比可能会因为网络时延情况不同而存在细微差异：

##### **不同网络对算力攻击的影响示意图**

![honestmining-network](doc/honestmining-network.png)

对于算力攻击和自私挖矿，一次攻击成功的定义为攻击者产出区块，并被网络接受。
图中纵坐标为链质量指标，即攻击者产出区块在主链中的占比与1之差。

**参数设置如下：**

- 仿真次数：3000000轮
- 矿工数：100
- 共识类型：PoW
- 难度：000FFF...
- q_ave = 1
- 网络参数：blocksize=4; TopologyNetwork中带宽均为2, 且开启动态拓扑; AdhocNetwork中最大带宽为40;
    其余网络参数为默认参数。

使用配置文件[pow_doublespending.ini](conf/pow_doublespending.ini)，执行以下命令（需要相应修改攻击者数量和网络类型）：

```bash
python main.py -c conf/pow_doublespending.ini --total_round 3000000 --q_ave 1 --attack_type HonestMining --network_type network.SynchronousNetwork --adver_num 5
```

---
#### b. 区块截留攻击（selfish mining）

发动区块截留攻击的矿工选择延迟发布自己挖出的区块以期获得更大利益，在时延较大的情况下，这样的攻击方式更容易成功：

##### **不同网络对区块截留攻击的影响示意图**

![selfishmining-network](doc/selfishmining-network.png)

同步网络下，这一攻击的链质量可以理论求得，而在其它网络下，链质量会依照各自网络的时延情况产生高低不一的下降。

**参数设置如下：**

- 仿真次数：3000000轮
- 矿工数：100
- 共识类型：PoW
- 难度：0000FF...
- q_ave = 10
- 网络参数：与算力攻击一样

使用配置文件[pow_doublespending.ini](conf/pow_doublespending.ini)，执行以下命令（需要相应修改攻击者数量和网络类型）：

```bash
python main.py -c conf/pow_doublespending.ini --total_round 3000000 --difficulty 16 --q_ave 10 --attack_type SelfishMining --network_type network.SynchronousNetwork --adver_num 5
```

图中的理论曲线由以下公式得到：

$$ R=\frac{4\alpha^{2}(1-\alpha)^{2}-\alpha^{3}}{1-\alpha(1+(2-\alpha)\alpha)} $$

其中$\alpha$表示攻击者的占比。

---
#### c. 双花攻击（double spending）

双花攻击使得交易历史被回滚的成功率也将受到网络时延影响，这一影响是复杂且值得思考的：

##### **不同网络对双花攻击的影响示意图**

![doublespending-netork](doc/doublespending-netork.png)

与自私挖矿的结果有些许类似，时延条件越差的网络，攻击成功率就越高。

**参数设置如下：**

- 仿真次数：3000000轮
- 矿工数：100
- 共识类型：PoW
- 难度：000FFF...
- q_ave = 3
- 网络参数：与算力攻击一样
- 攻击参数：Ng=3, N=1 

使用配置文件[pow_doublespending.ini](conf/pow_doublespending.ini)，执行以下命令（需要相应修改攻击者数量和网络类型）：

```bash
python main.py -c conf/pow_doublespending.ini --total_round 3000000 --network_type network.SynchronousNetwork --adver_num 5
```

除了时延，攻击者的策略也是影响双花攻击成功率的一个重要因素。它们可以选择落后几个块才放弃攻击，或者是等待几个块才发布自己的区块：

---
##### **不同策略对双花攻击的影响与理论对比示意图**

![double_spending](doc/doublespending.png)

同步网络下，这一攻击的成功率可以理论求得，可见等待确认的区块数量越少，攻击越容易成功。

**参数设置如下：**

- 仿真次数：5000000轮
- 矿工数：20
- 共识类型：PoW
- 难度：000FFF...
- q_ave = 1
- 网络类型：SynchronousNetwork
- 攻击参数：Ng=10, N=1/3/6 

使用配置文件[synchronous_doublespending.ini](conf/synchronous_doublespending.ini)，执行以下命令（需要相应修改攻击者数量和N）：

```bash
python main.py -c conf/synchronous_doublespending.ini --total_round 5000000 -N 1 --adver_num 5
```

图中的理论曲线由以下公式得到：

$$P(N,N_g,\beta)=1-\sum_{n=0}^{N}\begin{pmatrix}n+N-1\\
n
\end{pmatrix}\left(\frac{1}{1+\beta}\right)^{N}\left(\frac{\beta}{1+\beta}\right)^{n}\left(\frac{1-\beta^{N-n+1}}{1-\beta^{Ng+1}}\right)$$

$N$为攻击者等待确认区块的数量，即攻击者会等待诚实链高度增长$N$个区块后才会选择发布与否。
$N_g$表示当攻击者落后诚实链$N_g$个区块时放弃当前攻击。
$\beta$为攻击者与诚实矿工算力之比，$0\leqslant\beta\leqslant1$。

---
#### d. 日蚀攻击（eclipsed double spending）

发动日蚀攻击的节点会控制被攻击节点的消息接收情况，使它们只能收到自己的块。为模拟这一攻击，网络拓扑需要专门设计。两个作为示例的拓扑如下图所示：

![eclipse_topology1](doc/eclipse_topology1.svg)

![eclipse_topology2](doc/eclipse_topology2.svg)

可以看到各拓扑中被攻击节点只与攻击者链接，便于攻击者发动攻击，而攻击者与其它所有节点则是全连接，便于与全连接拓扑网络进行对照仿真。

##### **受日蚀攻击影响下的双花攻击示意图**

![eclipse_doublespending](doc/eclipse_doublespending.png)

攻击顺利进行时，被攻击节点只会在攻击节点的区块后挖掘，可以视为其算力完全被攻击者所用。因此，这种情况下双花攻击的成功率会等于两者算力之和在全连接网络下发动攻击的成功率。
本例的绘图代码详见文件[result_plot.py](util/result_plot.py)

**参数设置如下：**

- 仿真次数：5000000轮
- 矿工数：10
- 共识类型：PoW
- 难度：0000FF...
- q_ave = 10
- 网络类型：TopologyNetwork
- 区块大小：0MB

先在全连接网络条件下进行仿真，执行以下命令：

````bash
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --adver_list "(0,)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --adver_list "(0,1)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --adver_list "(0,1,2)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --adver_list "(0,1,2,3)"
````

然后使用配置文件[topology_eclipsed.ini](conf/topology_eclipsed.ini)，执行以下命令（需要相应修改攻击者ID、被日蚀攻击的矿工ID和网络拓扑）：

```bash
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --topology_path conf/topologies/eclipse_0_1.csv --eclipse_target "(0,)" --adver_list "(1,)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --topology_path conf/topologies/eclipse_0_12.csv --eclipse_target "(0,)" --adver_list "(1,2)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --topology_path conf/topologies/eclipse_0_123.csv --eclipse_target "(0,)" --adver_list "(1,2,3)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --topology_path conf/topologies/eclipse_01_2.csv --eclipse_target "(0,1)" --adver_list "(2,)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --topology_path conf/topologies/eclipse_01_23.csv --eclipse_target "(0,1)" --adver_list "(2,3)"
python main.py -c conf/topology_eclipsed.ini --total_round 5000000 --topology_path conf/topologies/eclipse_012_3.csv --eclipse_target "(0,1,2)" --adver_list "(3,)"
```

