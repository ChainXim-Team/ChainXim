import json
import sys
import math
# sys.path.append("D:\Files\gitspace\chain-xim")
import os
import logging
import itertools

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp

import miner
import errors
import global_var
from chain import Block
from network.network_abc import Network

logger = logging.getLogger(__name__)

class BlockPacketTpNet(object):
    '''拓扑网络中的区块数据包，包含路由相关信息'''
    def __init__(self, newblock: Block, minerid, round, TTL, outnetobj:"TopologyNetwork"):
        self.block = newblock
        self.minerid = minerid
        self.round = round
        self.TTL = TTL  # 剩余存活时间
        self.outnetobj = outnetobj  # 外部网络类实例
        # 路由过程相关
        self.received_miners = [minerid]
        # links: save link information [scm(source miner), tgm(target miner), delay]
        self.links = [[minerid, mi, d] for mi, d in
                    zip(self.outnetobj.miners[minerid].neighbor_list,
                    self.outnetobj.cal_neighbor_delays(newblock, minerid))]
        # 路由结果记录相关
        self.routing_histroy = {(minerid, tgm): [round, 0] for tgm in
                                self.outnetobj.miners[minerid].neighbor_list}
        


class TopologyNetwork(Network):
    '''拓扑P2P网络'''                        
    def __init__(self, miners: list[miner.Miner]):
        super().__init__()
        self.miners = miners
        # parameters, set by set_net_param()
        self.show_label = None
        self.gen_net_approach = None
        self.save_routing_graph = None
        self.ave_degree = None
        self.bandwidth_honest = 0.5 # default 0.5 MB
        self.bandwidth_adv = 5 # default 5 MB
        self.TTL = 1000
        # 拓扑图，初始默认全不连接
        self.tp_adjacency_matrix = np.zeros((self.MINER_NUM, self.MINER_NUM))
        self.network_graph = nx.Graph(self.tp_adjacency_matrix)
        self.node_pos = None #后面由set_node_pos生成
        self.network_tape:list[BlockPacketTpNet] = []
        # status
        self.ave_block_propagation_times = {}
        self.block_num_bpt = []
        # 结果保存路径
        NET_RESULT_PATH = global_var.get_net_result_path()
        with open(NET_RESULT_PATH / 'routing_history.json', 'a+',  encoding='utf-8') as f:
            f.write('[')
            json.dump({"B0": {}}, f, indent=4)
            f.write(']')


    def set_net_param(self, gen_net_approach = None, TTL = None, ave_degree = None, 
                        bandwidth_honest = None, bandwidth_adv = None,
                        save_routing_graph = None, show_label = None,
                        block_prop_times_statistic = None):
        ''' 
        set the network parameters

        param
        -----  
        gen_net_approach (str): 生成网络的方式, 'adj'邻接矩阵, 'coo'稀疏矩阵, 'rand'随机
        TTL (int): 区块的最大生存周期, 为了防止因孤立节点或日蚀攻击,导致该块一直在网络中
        ave_degree (int): ; If 'rand', set the average degree
        bandwidth_honest(float): bandwidth between honest miners and between the honest and adversaries(MB/round)
        bandwidth_adv (float): bandwidth between adversaries(MB/round)
        save_routing_graph (bool): Genarate routing graph at the end of simulation or not.
        show_label (bool): Show edge labels on network and routing graph or not. 
        '''
        if show_label is not None:
            self.show_label = show_label
        if bandwidth_honest is not None: # default 0.5 MB/round
            self.bandwidth_honest = bandwidth_honest 
        if bandwidth_adv is not None: # default 5 MB/round
            self.bandwidth_adv = bandwidth_adv 
        if gen_net_approach is not None:
            if  gen_net_approach == 'rand' and ave_degree is not None:
                self.gen_net_approach = gen_net_approach
                self.ave_degree = ave_degree
                self.generate_network(gen_net_approach, ave_degree)
            else:
                self.gen_net_approach = gen_net_approach
                self.edge_prob = None
                self.generate_network(gen_net_approach)
        if TTL is not None:
            self.TTL = TTL
        if save_routing_graph is not None:
            self.save_routing_graph = save_routing_graph
        for rcv_rate in block_prop_times_statistic:
            self.ave_block_propagation_times.update({rcv_rate:0})
            self.block_num_bpt = [0 for _ in range(len(block_prop_times_statistic))]
  

    def access_network(self, newblock, minerid, round):
        '''本轮新产生的块添加到network_tape.

        param
        -----
        newblock (Block) : The newly mined block 
        minerid (int) : Miner_ID of the miner generated the block. 
        round (int) : Current round. 
        '''
        block_packet = BlockPacketTpNet(newblock, minerid, round, self.TTL, self)
        self.network_tape.append(block_packet)
        self.miners[minerid].consensus.receive_block(newblock)  
        # 这一条防止adversary集团发出区块的代表，自己的链上没有该区块
        logger.info("access network miner:%d %s at round %d", minerid, newblock.name, round)


    def diffuse(self, round):
        '''传播过程
        传播的思路类似图的遍历:
        block_packet(以下用bp)中links记录路由过程中的各链路(link),元素[scm, tgm ,delay]
        每轮delay值减1,直到delay为0,该link传播完成, 将对应的index添加到trans_complete_links,
        使用receiveBlock(bp.block)使tgm接收该块,并把tgm添加到bp.reiceved_miners中,
        此时tgm(即forward中的current_miner)变为下一个传播链路的scm,对应的scm为from_miner。

        此时来到forward():
        >>选择接下来传播的target
            current_miner选择接下来要传给的next_targets,计算cal_delay,
            生成链路[current_miner,nexttg,nextd],并添加到bp.next_miners_and_delays中;
        >>记录路由:
            bp.routing_histroy字典,键值对(scm,tgm):[begin_round,complete_round],
            对于新加入的link,将begin_round设为当前round,complete_round设为0;
            对于完成的link,将对应的complete_round设为当前ruond。

        当本轮中该bp的所有操作完成后,将trans_complete_links中对应的link从links中删除。
        最后,当bp.reiceved_miners中包含了所有的矿工或超过了TTL,表示该block传播完成,
        将其从network_tape中删除,并在json文件中记录其路由。
        '''
        died_packets = []  # record the finished-propagation blocks
        if self.network_tape:
            for i, bp in enumerate(self.network_tape):
                # judge whether all the miners have received the block,
                # 'diffuse' only applies to networks without isolated nodes or subnets
                if len(set(bp.received_miners)) < self.MINER_NUM and bp.TTL > 0:
                    trans_complete_links = []  # record the completed transmission links
                    rcv_success = False
                    for j, [scm, tgm, delay] in enumerate(bp.links):
                        if delay <= 0:
                            rs = self.receive_forward(scm, tgm, bp, round)
                            rcv_success = rs or rcv_success
                            trans_complete_links.append(j)
                        else:
                            bp.links[j][2] -= 1
                    # delete the complete links
                    if trans_complete_links:
                        bp.links = [n for j, n in enumerate(bp.links) 
                                    if j not in trans_complete_links]
                    trans_complete_links.clear()
                    bp.TTL -= 1
                    # if rcv_success:
                    #     self.record_block_propagation_time(bp, round)
                else:# 所有人都收到了或该bp的生存周期结束，该block传播结束
                    died_packets.append(i)# 该block加入died_packets
                    self.write_routing_to_json(bp)# 将路由结果记录在json文件中
                
            if died_packets:# 在network_tape中清理掉传播结束的块
                self.network_tape = [n for i, n in enumerate(self.network_tape) 
                                     if i not in died_packets]
                died_packets.clear()


    def receive_forward(self, from_miner, current_miner, block_packet: BlockPacketTpNet, round):
        '''接收并转发区块
        收到一个包,本地链上没有,就添加到receive_tape中并转发给接下来的目标
        否则不对该包进行处理
        '''
        receive_success = self.miners[current_miner].consensus.receive_block(block_packet.block)
        # if the block not in local chain, receive.
        if  receive_success is True:
            # record the miner received the block
            block_packet.received_miners.append(current_miner)
            self.record_block_propagation_time(block_packet, round)
            # logger.info(f"{block_packet.block.name}:{len(block_packet.received_miners)} at round {round}") 
            # execute forward strategy
            self.normal_forward(from_miner, current_miner, block_packet, round)
        return receive_success

    def record_block_propagation_time(self, block_packet: BlockPacketTpNet, r):
        '''calculate the block propagation time'''
        bp = block_packet
        rn = len(set(bp.received_miners))
        mn = self.MINER_NUM

        def is_closest_to_percentage(a, b, percentage):
            return a == math.floor(b * percentage)

        rcv_rate = -1
        rcv_rates = [k for k in self.ave_block_propagation_times.keys()]
        for p in rcv_rates:
            if is_closest_to_percentage(rn, mn, p):
                rcv_rate = p
                break
        if rcv_rate != -1 and rcv_rate in rcv_rates:
            logger.info(f"{bp.block.name}:{rn},{rcv_rate} at round {r}")
            self.ave_block_propagation_times[rcv_rate] += r-bp.round
            self.block_num_bpt[rcv_rates.index(rcv_rate)] += 1

    def cal_block_propagation_times(self):
        rcv_rates = [k for k in self.ave_block_propagation_times.keys()]
        for i ,  rcv_rate in enumerate(rcv_rates):
            total_bpt = self.ave_block_propagation_times[rcv_rate ]
            total_num = self.block_num_bpt[i]
            if total_num == 0:
                continue
            self.ave_block_propagation_times[rcv_rate] = round(total_bpt/total_num, 3)
        return self.ave_block_propagation_times


    def normal_forward(self, from_miner, cur_miner, block_packet: BlockPacketTpNet, round):
        '''一般转发策略。接下来转发的目标为除了from_miner和本地链中已包含该块的所有neighbor矿工。
        param:
        from_miner:该block_packet的来源     type:int  (MinerID)
        current_miner:当前的矿工            type:int  (MinerID)
        block_packet:当前处理的区块数据包    type:BlockPacketTpNet
        round:当前轮数                      type:int
        '''
        # 选择接下来赚翻的目标--除了from_miner和已包含该块的所有neighbor矿工
        bp = block_packet
        next_targets = [mi for mi in self.miners[cur_miner].neighbor_list 
                        if mi != from_miner and mi not in block_packet.received_miners]
        next_delays = []
        for nexttg in next_targets:
            next_delays.append(self.cal_delay(bp.block, cur_miner, nexttg))
        bp.links.extend([cur_miner, nexttg, nextd] for nexttg, nextd in zip(next_targets, next_delays))

        # 记录路由
        bp.routing_histroy.update({(cur_miner, nexttg): [round, 0] for nexttg in next_targets})
        bp.routing_histroy[(from_miner, cur_miner)][1] = round


    def cal_delay(self, block:Block, sourceid, targetid):
        '''计算sourceid和targetid之间的时延'''
        # 传输时延=块大小除带宽 且传输时延至少1轮
        bw_mean = self.network_graph.edges[sourceid, targetid]['bandwidth']
        bandwidth = np.random.normal(bw_mean,0.2*bw_mean)
        transmision_delay = math.ceil(block.blocksize_MB / bandwidth)
        # 时延=处理时延+传输时延
        delay = self.miners[sourceid].processing_delay + transmision_delay
        return delay


    def cal_neighbor_delays(self, block, minerid):
        '''计算minerid的邻居的时延'''
        neighbor_delays = []
        for neighborid in self.miners[minerid].neighbor_list:
            delay = self.cal_delay(block, minerid, neighborid)
            neighbor_delays.append(delay)
        return neighbor_delays
    

    def generate_network(self, gen_net_approach, ave_degree=None):
        '''
        根据csv文件的邻接矩'adj'或coo稀疏矩阵'coo'生成网络拓扑    
        '''
        # read from csv finished
        try:
            if gen_net_approach == 'adj':
                self.gen_network_adj()
            elif gen_net_approach == 'coo':
                self.gen_network_coo()
            elif gen_net_approach == 'rand' and ave_degree is not None:
                self.gen_network_rand(ave_degree)
            else:
                raise errors.NetGenError('网络生成方式错误！')
            #检查是否有孤立节点或不连通部分
            if nx.number_of_isolates(self.network_graph) == 0:
                if nx.number_connected_components(self.network_graph) == 1:
                    # 邻居节点保存到各miner的neighbor_list中
                    for minerid in list(self.network_graph.nodes):
                        self.miners[minerid].neighbor_list = list(self.network_graph.neighbors(int(minerid)))
                    # 结果展示和保存
                    #print('adjacency_matrix: \n', self.tp_adjacency_matrix,'\n')
                    self.draw_and_save_network()
                    self.save_network_attribute()
                else:
                    raise errors.NetUnconnetedError('网络存在不连通部分!')
            else:
                raise errors.NetIsoError(f'网络存在孤立节点! {list(nx.isolates(self.network_graph))}')
        except (errors.NetMinerNumError, errors.NetAdjError, errors.NetIsoError, 
                errors.NetUnconnetedError, errors.NetGenError) as error:
            print(error)
            sys.exit(0)
    

    def save_network_attribute(self):
        '''保存网络参数'''
        network_attributes={
            'miner_num':self.MINER_NUM,
            'Generate Approach':self.gen_net_approach,
            'Generate Edge Probability':self.ave_degree/self.MINER_NUM if self.gen_net_approach == 'rand' else None,
            'Diameter':nx.diameter(self.network_graph),
            'Average Shortest Path Length':round(nx.average_shortest_path_length(self.network_graph), 3),
            'Degree Histogram': nx.degree_histogram(self.network_graph),
            "Average Degree": sum(dict(nx.degree(self.network_graph)).values())/len(self.network_graph.nodes),
            'Average Cluster Coefficient':round(nx.average_clustering(self.network_graph), 3),
            'Degree Assortativity':round(nx.degree_assortativity_coefficient(self.network_graph), 3),
        }
        NET_RESULT_PATH = global_var.get_net_result_path()
        with open(NET_RESULT_PATH / 'Network Attributes.txt', 'a+', encoding='utf-8') as f:
            f.write('Network Attributes'+'\n')
            print('Network Attributes')
            for k,v in network_attributes.items():
                f.write(str(k)+': '+str(v)+'\n')
                print(' '*4 + str(k)+': '+str(v))
            print('\n')


    def gen_network_rand(self, ave_degree):
        """采用Erdős-Rényi算法生成随机图"""
        edge_prop = ave_degree/self.MINER_NUM
        self.network_graph = nx. gnp_random_graph(self.MINER_NUM, edge_prop)
        # 防止出现孤立节点
        if nx.number_of_isolates(self.network_graph) > 0:
            iso_nodes = list(nx.isolates(self.network_graph))
            not_iso_nodes = [nd for nd in list(self.network_graph.nodes) if nd not in iso_nodes]
            targets = np.random.choice(not_iso_nodes, len(iso_nodes))
            for m1, m2 in zip(iso_nodes, targets):
                self.network_graph.add_edge(m1, m2)
        # 将攻击者集团的各个矿工相连
        for m1,m2 in itertools.combinations(range(self.MINER_NUM), 2):
            if self.miners[m1].isAdversary and self.miners[m2].isAdversary:
                if not self.network_graph.has_edge(m1, m2):
                    self.network_graph.add_edge(m1, m2)
        # 设置带宽（MB/round）
        bw_honest = self.bandwidth_honest
        bw_adv = self.bandwidth_adv
        bandwidths = {(u,v):(bw_adv if self.miners[u].isAdversary
                      and self.miners[v].isAdversary else bw_honest)
                      for u,v in self.network_graph.edges}
        nx.set_edge_attributes(self.network_graph, bandwidths, "bandwidth")
        self.tp_adjacency_matrix = nx.adjacency_matrix(self.network_graph).todense()


    def gen_network_adj(self):
        """
        如果读取邻接矩阵,则固定节点间的带宽0.5MB/round
        bandwidth单位:bit/round
        """
        # 读取csv文件的邻接矩阵
        self.read_adj_from_csv_undirected()
        # 根据邻接矩阵生成无向图
        self.network_graph = nx.Graph()
        # 生成节点
        self.network_graph.add_nodes_from([i for i in range(self.MINER_NUM)])
        # 生成边
        for m1 in range(len(self.tp_adjacency_matrix)): 
            for m2 in range(m1, len(self.tp_adjacency_matrix)):
                if self.tp_adjacency_matrix[m1, m2] == 1:
                    self.network_graph.add_edge(m1, m2)
        # 设置带宽（MB/round）
        bw_honest = self.bandwidth_honest
        bw_adv = self.bandwidth_adv
        bandwidths = {(u,v):(bw_adv if self.miners[u].isAdversary
                      and self.miners[v].isAdversary else bw_honest)
                      for u,v in self.network_graph.edges}
        nx.set_edge_attributes(self.network_graph, bandwidths, "bandwidth")
                    


    def gen_network_coo(self):
        """如果读取'coo'稀疏矩阵,则带宽由用户规定"""
        # 第一行是行(from)
        # 第二行是列(to)(在无向图中无所谓from to)
        # 第三行是bandwidth:bit/round
        tp_coo_dataframe = pd.read_csv('network_topolpgy_coo.csv', header=None, index_col=None)
        tp_coo_ndarray = tp_coo_dataframe.values
        row = np.array([int(i) for i in tp_coo_ndarray[0]])
        col = np.array([int(i) for i in tp_coo_ndarray[1]])
        bw_arrary = np.array([float(eval(str(i))) for i in tp_coo_ndarray[2]])
        tp_bw_coo = sp.coo_matrix((bw_arrary, (row, col)), shape=(10, 10))
        adj_values = np.array([1 for _ in range(len(bw_arrary) * 2)])
        self.tp_adjacency_matrix = sp.coo_matrix((adj_values, (np.hstack([row, col]), np.hstack([col, row]))),
                                                    shape=(10, 10)).todense()
        print('edges: \n', tp_bw_coo)
        self.network_graph.add_nodes_from([i for i in range(self.MINER_NUM)])
        for edge_idx, (src, tgt) in enumerate(zip(row, col)):
            self.network_graph.add_edge(src, tgt, bandwidth=bw_arrary[edge_idx])


    def read_adj_from_csv_undirected(self):
        """读取无向图的邻接矩阵adj"""
        # 读取csv文件并转化为ndarray类型,行是from 列是to
        topology_ndarray  = pd.read_csv('network_topolpgy.csv', header=None, index_col=None).values
        # 判断邻接矩阵是否规范
        if np.isnan(topology_ndarray).any():
            raise errors.NetAdjError('无向图邻接矩阵不规范!(存在缺失)')
        if topology_ndarray.shape[0] != topology_ndarray.shape[1]:  # 不是方阵
            raise errors.NetAdjError('无向图邻接矩阵不规范!(row!=column)')
        if len(topology_ndarray) != self.MINER_NUM:  # 行数与环境定义的矿工数量不同
            raise errors.NetMinerNumError('矿工数量与环境定义不符!')
        if not np.array_equal(topology_ndarray, topology_ndarray.T):
            raise errors.NetAdjError('无向图邻接矩阵不规范!(不是对称阵)')
        if not np.all(np.diag(topology_ndarray) == 0):
            raise errors.NetAdjError('无向图邻接矩阵不规范!(对角元素不为0)')
        # 生成邻接矩阵
        self.tp_adjacency_matrix = np.zeros((len(topology_ndarray), len(topology_ndarray)))
        for i in range(len(topology_ndarray)):
            for j in range(i, len(topology_ndarray)):
                if topology_ndarray[i, j] != 0:
                    self.tp_adjacency_matrix[i, j] = self.tp_adjacency_matrix[j, i] = 1

    def set_node_pos(self):
        '''使用spring_layout设置节点位置'''
        self.node_pos = nx.spring_layout(self.network_graph, seed=50)
        for node1,node2 in itertools.combinations(self.network_graph.nodes,2):
            ...


    def node_moving(self):
        '''节点随机移动'''
        ...

    def euclidean_distance(self, node1, node2):
        return np.linalg.norm(node1['pos'],self.network_graph.nodes[node2]['pos'])
        


    def draw_and_save_network(self):
        """
        展示和保存网络拓扑图self.network_graph
        """
        #plt.ion()
        self.set_node_pos()
        # plt.figure(figsize=(12,10))
        node_size = 200*3/self.MINER_NUM**0.5
        font_size = 30/self.MINER_NUM**0.5
        line_width = 3/self.MINER_NUM**0.5
        #nx.draw(self.network_graph, self.draw_pos, with_labels=True,node_size=node_size,font_size=30/(self.MINER_NUM)^0.5,width=3/self.MINER_NUM)
        node_colors = ["red" if self.miners[n].isAdversary else '#1f78b4'  
                            for n,d in self.network_graph.nodes(data=True)]
        nx.draw_networkx_nodes(self.network_graph, pos = self.node_pos, 
                                node_color = node_colors, node_size=node_size)
        nx.draw_networkx_labels(self.network_graph, pos = self.node_pos, 
                                font_size = font_size, font_family = 'times new roman')
        edge_labels = {}
        for src, tgt in self.network_graph.edges:
            bandwidth = self.network_graph.get_edge_data(src, tgt)['bandwidth']
            edge_labels[(src, tgt)] = f'BW:{bandwidth}'
        nx.draw_networkx_edges(self.network_graph, pos=self.node_pos, 
                                        width = line_width, node_size=node_size)
        if self.show_label:
            nx.draw_networkx_edge_labels(self.network_graph, self.node_pos, edge_labels=edge_labels, 
                            font_size=12/self.MINER_NUM**0.5, font_family='times new roman')

        RESULT_PATH = global_var.get_net_result_path()
        plt.savefig(RESULT_PATH / 'network topology.svg')
        #plt.pause(1)
        plt.close()
        #plt.ioff()



    def write_routing_to_json(self, block_packet):
        """
        每当一个block传播结束,将其路由结果记录在json文件中
        json文件包含origin_miner和routing_histroy两种信息
        """
        bp = block_packet
        with open(self.NET_RESULT_PATH / 'routing_history.json', 'a+', encoding = 'utf-8') as f:
            f.seek(f.tell() - 1, os.SEEK_SET)
            f.truncate()
            f.write(',')
            bp.routing_histroy = {str(k): bp.routing_histroy[k] for k in bp.routing_histroy}
            json.dump({str(bp.block.name): {'origin_miner': bp.minerid, 'routing_histroy': bp.routing_histroy}}, f,
                      indent=2)
            f.write(']')


    def gen_routing_gragh_from_json(self):
        """
        读取Result->Network Routing文件夹下的routing_histroy.json,并将其转化为routing_gragh
        """
        if self.save_routing_graph is False:
            print('Fail to generate routing gragh for each block from json.')
        elif self.save_routing_graph is True:  
            print('Generate routing gragh for each block from json...')
            NET_RESULT_PATH = global_var.get_net_result_path()
            with open(NET_RESULT_PATH / 'routing_history.json', 'r', encoding = 'utf-8') as load_obj:
                a = json.load(load_obj)
                for v_dict in a:
                    for blockname, origin_routing_dict in v_dict.items():
                        if blockname != 'B0':
                            for k, v in origin_routing_dict.items():
                                if k == 'origin_miner':
                                    origin_miner = v
                                if k == 'routing_histroy':
                                    rh = v
                                    rh = {tuple(eval(ki)): rh[ki] for ki, _ in rh.items()}
                            self.gen_routing_gragh(blockname, rh, origin_miner)
                            print(f'\rgenerate routing gragh of {blockname} successfully', end="", flush=True)
            print('Routing gragh finished')
            

    def gen_routing_gragh(self, blockname, routing_histroy_single_block, origin_miner):
        """
        对单个区块生成路由图routing_gragh
        """
        # 生成有向图
        trans_process_graph = nx.DiGraph()

        trans_process_graph.add_nodes_from(self.network_graph.nodes)

        for (source_node, target_node), strounds in routing_histroy_single_block.items():
            trans_process_graph.add_edge(source_node, target_node, trans_histroy=strounds)

        # 画图和保存结果
        # 处理节点颜色
        node_colors = []
        for n, d in trans_process_graph.nodes(data=True):
            if self.miners[n].isAdversary and n != origin_miner:
                node_colors.append("red")
            elif n == origin_miner:
                node_colors.append("green")
            else:
                node_colors.append('#1f78b4')
        node_size=100*3/self.MINER_NUM**0.5
        nx.draw_networkx_nodes(trans_process_graph, pos=self.node_pos, node_size=node_size,node_color=node_colors)
        nx.draw_networkx_labels(trans_process_graph, pos=self.node_pos, font_size=30/self.MINER_NUM**0.5,font_family='times new roman')
        # 对边进行分类，分为单向未传播完成的、双向未传播完成的、已传播完成的
        edges_not_complete_single = [(u, v) for u, v, d in trans_process_graph.edges(data=True) if d["trans_histroy"][1] == 0 
                and (v, u) not in  trans_process_graph.edges()]
        edges_not_complete_double = [(u, v) for u, v, d in trans_process_graph.edges(data=True) if d["trans_histroy"][1] == 0 
                and (v, u) in  trans_process_graph.edges() and u>v]
        edges_complete = [ed for ed in [(u, v) for u, v, d in trans_process_graph.edges(data=True) if
                          (u, v)not in edges_not_complete_single and (u, v) not in edges_not_complete_double 
                          and (v, u) not in edges_not_complete_double]]
        # 画边
        width=3/self.MINER_NUM**0.5
        nx.draw_networkx_edges(trans_process_graph, self.node_pos, edgelist=edges_complete, edge_color='black', 
                               width=width,alpha=1,node_size=node_size,arrowsize=30/self.MINER_NUM**0.5)
        nx.draw_networkx_edges(trans_process_graph, self.node_pos, edgelist=edges_not_complete_single, edge_color='black',
                               width=width,style='--', alpha=0.3,node_size=node_size,arrowsize=30/self.MINER_NUM**0.5)
        nx.draw_networkx_edges(trans_process_graph, self.node_pos, edgelist=edges_not_complete_double, edge_color='black',
                               width=width,style='--', alpha=0.3,node_size=node_size,arrowstyle='<|-|>',arrowsize=30/self.MINER_NUM**0.5)                      
        # 没有传播到的边用虚线画
        edges_list_extra = []
        for (u, v) in self.network_graph.edges:
            if ((u, v) not in trans_process_graph.edges) and ((v, u) not in trans_process_graph.edges):
                trans_process_graph.add_edge(u, v, trans_histroy=None)
                edges_list_extra.append((u, v))
        nx.draw_networkx_edges(trans_process_graph, pos=self.node_pos, edgelist=edges_list_extra, edge_color='black',
                                width=3/self.MINER_NUM**0.5,alpha=0.3, style='--', arrows=False)
        # 处理边上的label，对单向的双向和分别处理
        if self.show_label:
            edge_labels = {(u, v): f'{u}-{v}:{d["trans_histroy"]}' for u, v, d in trans_process_graph.edges(data=True) if
                        (v, u) not in trans_process_graph.edges()}
            edge_labels.update(dict(
                [((u, v), f'{u}-{v}:{d["trans_histroy"]}\n\n{v}-{u}:{trans_process_graph.edges[(v, u)]["trans_histroy"]}')
                for u, v, d in trans_process_graph.edges(data=True) if v > u and (v, u) in trans_process_graph.edges()]))
            nx.draw_networkx_edge_labels(trans_process_graph, self.node_pos, edge_labels=edge_labels, font_size=5*2/self.MINER_NUM**0.5,
                                font_family='times new roman')
            
        #保存svg图片
        NET_RESULT_PATH = global_var.get_net_result_path()
        plt.savefig(NET_RESULT_PATH / (f'routing_graph{blockname}.svg'))
        plt.close()


    def calculate_stats(self):
        stats = {
            "average_network_delay" : 0
        }
        delay_list = []
        RECEIVED_RATIO = 1 # 网络中收到区块的矿工数量相对所有矿工数量之比如果超过这一常量，计算网络延迟
        miner_num = len(self.miners)
        NET_RESULT_PATH = global_var.get_net_result_path()
        with open(NET_RESULT_PATH / 'routing_history.json', 'r', encoding = 'utf-8') as load_obj:
            a = json.load(load_obj)
            for v_dict in a[1:]:
                for _, origin_routing_dict in v_dict.items():
                    routing_history = origin_routing_dict["routing_histroy"]
                    miner_received = 0
                    access_network_time = 0
                    for transmision,time_span in routing_history.items():
                        arrival_time = time_span[1]
                        if tuple(eval(transmision))[0] == origin_routing_dict["origin_miner"]:
                            access_network_time = time_span[0]
                        if arrival_time:
                            miner_received += 1
                            if miner_received + 1>= miner_num * RECEIVED_RATIO:
                                delay_list.append(arrival_time - access_network_time)
        stats['average_network_delay'] = sum(delay_list)/len(delay_list)
        return stats
if __name__ == '__main__':
    # rn = 5
    # mn = 23
    # block_propagation_times = {
    #         '10%': 0,
    #         '20%': 0,
    #         '30%': 0,
    #         '40%': 0,
    #         '50%': 0,
    #         '60%': 0,
    #         '70%': 0,
    #         '80%': 0,
    #         '90%': 0,
    #         '100%': 0
    #     }
    # def is_closest_to_percentage(a, b, percentage):
    #     return a == round(b * percentage)

    # rcv_rate = -1
    # for i in range(10):
    #     if is_closest_to_percentage(rn, mn, 0.1*(i+1)):
    #         rcv_rate = 0.1*(i+1)
    #         break
    # if rcv_rate > 0:
    #     bpt_key = f'{int(rcv_rate * 100)}%'
    #     block_propagation_times[bpt_key] += 1
    
    # print(block_propagation_times)
    bw_mean = 4300000
    bandwidth = np.random.normal(bw_mean,100000)
    print(bandwidth)