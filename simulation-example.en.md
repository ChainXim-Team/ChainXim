## Simulation Examples
In this document, we perform experiments with ChainXim, depict the results, and compare some of them with theoretical values.

### Relationship between the Number of Miners and Block Time in Synchronous Network

**Parameter settings:**

* Simulation rounds: 200000 rounds

* Number of miners: 10-80

* Consensus type: PoW/VirtualPoW/SolidPoW

* Difficulty: 0000FF...

* q_ave = 10

* Network parameters: SynchronousNetwork

![block_time](doc/block_time.png)


### Fork Rate, Stale Block Rate, and Consistency under Different Maximum Delays

- Rounds: 1000000
- Number of miners: 20
- Consensus type: PoW
- q_ave: 10
- Difficulty: 000FFF...
- Network types: StochPropNetwork
- Network parameters: rcvprob_start=rcvprob_inc=1/maximum rounds

---
Fork rate/Stale block rate variation with maximum propagation delay

![latency-fork](doc/latency-fork.png)

---
Consistency metrics variation with maximum propagation delay

![cp_bounded_delay](doc/cp_bounded_delay.png)

In the figure, Common Prefix[0], [1], [2] represent the first three components of the common prefix PDF, where the ordinal number represents the difference between the common prefix and the main chain length (see the "Simulator Output" section for details).


### Growth Rate under Different Single-Round Mining Power

- Rounds: 1500000
- Number of miners: 20
- Consensus type: PoW/VirtualPoW/SolidPoW
- q_ave: 2-16
- Difficulty: 000FFF...
- Network types: DeterPropNetwork
- Network parameters: prop_vector=[0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]

![miningpower-throughput](doc/miningpower-throughput.png)


### Fork Rate under Different Mining Difficulty Targets

- Rounds: 1000000
- Number of miners: 32
- Consensus type: PoW/VirtualPoW/SolidPoW
- q_ave: 1
- Difficulty: 0000FF...-000FFF...
- Network types: TopologyNetwork
- Network parameters: init_mode=coo; use round topology

![target-fork](doc/target-fork.png)

The theoretical curve in the figure is obtained by the following formula:

$$ f=1 - (1 - t)^{mq\sum_{n=1}^{d} i_n} $$

Here, $t$ represents the difficulty target shown on the horizontal axis of the graph, $m$ is the number of miners, and $q$ is the q_ave, denoting the average number of hash queries performed by each miner per round. $i_n$ represents the proportion of miners in the entire network that receive the block in the nth round after the block is propagated.


### Common Prefix Property of Blockchain under Topology Network

- Rounds: 16189
- Number of miners: 10
- Consensus type: PoW
- Difficulty: 000FFF...
- Network type: TopologyNetwork
- Network parameters: init_mode=adj；bandwidth_honest=0.5

At the end of each round, the height difference of the local chains of all nodes relative to the common prefix and its impact on the Common Prefix PDF are shown in the figure below. The time axis below is the round in which the chain tail switch event occurred, the upper x-axis is the block height/common prefix followed by the block length (suffix length), and the y-axis is the miner ID. The heat value in the figure indicates the cumulative number of times each miner's local chain tail reaches the suffix length relative to the common prefix. BXX in the figure refers to the block number, representing the state of the miner's local chain tail in the current round, and the lower x-axis indicates the height of these blocks. Click Play to start the animation, where you can observe the block being generated to extend the common prefix, then propagating to other miners, and finally causing the common prefix height to increase by 1.

<style>
	.iframe-body-sty{position: relative;overflow: hidden;height:850px;width: 850px;background-color: white;
    transform: scale(0.8); transform-origin:0 0; margin-bottom: -170px}
</style>

<div class="iframe-body-sty">
<iframe
 height=850px
 width=850px
 src="/chainxim-documentation/doc/cp_pdf.html"  
 frameborder=0 
 display:block>
 </iframe>
</div>


### Throughput and Fork Rate under Different Block Sizes

- Rounds: 1000000
- Number of miners: 40
- Consensus type: PoW
- q_ave: 10
- Blocksize: 2-20MB
- Difficulty: 0000FF...
- Network type: AdHocNetwork
- Network parameters: ave_degree=3, region_width=100, comm_range=30, move_variance=5, outage_prob=0.01, 
bandwidth_max=100, enable_large_scale_fading = True, path_loss_level = low/medium/high

---
Throughput variation with block size

![blocksize-throughput](doc/blocksize-throughput.png)

---
Fork rate variation with block size

![blocksize-fork](doc/blocksize-fork.png)


### Attacker's Block Proportion under Different Attack Vectors

#### 1. Honest Mining Attack

##### **Impact of Different Networks on Honest Mining Attack**

![honestmining-network](doc/honestmining-network.png)

Definition of a successful attack is that the attacker produces a block and is accepted by the network. The vertical axis represents the chain quality, defined as the difference between 1 and the proportion of blocks produced by the attackers that are included in the main chain.

**Parameter settings:**

* Rounds: 1000000 rounds

* Number of miners: 100

* Consensus type: PoW

* Difficulty: 000FFF...

* q_ave = 1

* Network parameters: `blocksize=4`, the bandwidth of the edges in `TopologyNetwork` is `2MB/round` with dynamic topology enabled, and bandwidth_max=40 in `AdhocNetwork`. Other network parameters are set to default values.

---
#### 2. Selfish Mining Attack
##### **Impact of Different Networks on Selfish Mining Attack**

![selfishmining-network](doc/selfishmining-network.png)

The vertical axis represents the chain quality metric, i.e., the proportion of blocks produced by the attacker in the main chain

**Parameter settings:**

* Simulation rounds: 1000000 rounds

* Number of miners: 100

* Consensus type: PoW

* Difficulty: 0000FF...

* q_ave = 10

* Network parameters: identical to that of honest mining

The theoretical curve in the figure is obtained by the following formula:

$$ R=\frac{4\alpha^{2}(1-\alpha)^{2}-\alpha^{3}}{1-\alpha(1+(2-\alpha)\alpha)} $$

---
#### 3. Double Spending Attack

##### **Impact of Different Networks on Double Spending Attack**

![doublespending-netork](doc/doublespending-netork.png)

**Parameter settings:**

* Simulation rounds: 3000000 rounds

* Number of miners: 100

* Consensus type: PoW

* Difficulty: 000FFF...

* q_ave = 3

* Network parameters: identical to that of honest mining

* Attack parameters: Ng=3, N=1

---
##### **Impact of Different Strategies on Double Spending Attack and Theoretical Comparison**

![double_spending](doc/doublespending.png)

**Parameter settings:**

* Simulation rounds: 5000000 rounds

* Number of miners: 20

* Consensus type: PoW

* Difficulty: 000FFF...

* q_ave = 1

* Network parameters: SynchronousNetwork

* Attack parameters: Ng=10, N=1/3/6

The theoretical curve in the figure is obtained by the following formula:

$$P(N,N_g,\beta)=1-\sum_{n=0}^{N}\begin{pmatrix}n+N-1\\
n
\end{pmatrix}\left(\frac{1}{1+\beta}\right)^{N}\left(\frac{\beta}{1+\beta}\right)^{n}\left(\frac{1-\beta^{N-n+1}}{1-\beta^{Ng+1}}\right)$$

$N$ is the number of blocks the attacker waits for confirmation, i.e., the attacker will wait for the honest chain to grow by $N$ blocks before deciding whether to publish.
$N_g$ indicates that the attacker abandons the current attack when it is $N_g$ blocks behind the honest chain.
$\beta$ is the ratio of the attacker's hash power to that of the honest miners, $0\leqslant\beta\leqslant1$.

---

#### 4. Eclipsed Double Spending

##### **Double Spending Attack under Eclipse Attack**

![eclipse_doublespending](doc/eclipse_doublespending.png)

**Parameter settings:**

* Simulation rounds: 1000000 rounds

* Number of miners: 10

* Consensus type: PoW

* Difficulty: 0000FF...

* q_ave = 10

* Network type: TopologyNetwork

* Block size: 0 MB

* Network Parameters: The network topologies used are similar to those shown in the following two figures:

  ![eclipse_topology1](doc/eclipse_topology1.svg)

  ![eclipse_topology2](doc/eclipse_topology2.svg)

  In all topologies, the attacked node is only connected to the attacker, while the attacker is fully connected to all other nodes.
        

