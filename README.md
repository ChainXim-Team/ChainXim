 # 简介
 ChainXim是一款由XinLab开发的区块链仿真器，用于对不同网络、不同共识协议下的区块链进行仿真验证，可以通过设计网络攻击者辅助评估区块链的安全性能。目前仿真器还处于内部测试阶段。

# 安装 
 **Dependency**
 - python >= 3.7
 - graphviz
 - scipy
 - matplotlib > 3.5.1
 - networkx > 2.8.7
 - pandas

# 简单运行
在test.py中调整仿真参数
```shell
cd <project_directory>
python test.py
```
将会在Results文件夹生成仿真区块数据，包括每个矿工的区块链记录、区块链可视化矢量图、区块链攻击者日志、路由历史、网络矢量图、区块传播示意图。

# 文件结构
- test.py: 仿真器的主程序
- Environment.py: 环境类与相关函数
- Miner.py: 矿工类与相关函数
- chain.py: 包括块头、区块、区块链的类与相关函数
- consensus.py: 抽象共识类、PoW类与相关函数
- BitcoinBackboneProtocol.py: 核心共识函数
- Network.py: 网络类，包括网络拓扑与传播相关的函数
- Attack.py: 攻击者类与相关函数
- functions.py: 包含计算哈希（SHA256）在内的一些函数
- external.py: 一些外部函数