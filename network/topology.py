import itertools
import json
import logging
import math
import os
import random
import sys
from collections import defaultdict
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp

import errors
import global_var
from data import Block, Message
from network import Network, Packet

if TYPE_CHECKING:
    from miner import Miner

DIRECT = "direct"
GLOBAL = "global"

logger = logging.getLogger(__name__)

class TPPacket(Packet):
    def __init__(self, payload: Message, round, source: int = None, target: int = None, 
                 type: str = GLOBAL, destination:int=None):
        """
        param
        ----
        payload (Message): 传输的消息
        round(int):进入网络的时间
        source (int: 转发的来源
        target (int): 本次转发的目标 
        type (str): 消息类型，GLOBAL代表转发给全网的消息，DIRECT代表仅转发给特定对象
        destination (int): 类型为DIRECT时的终点
        """
        super().__init__(payload)
        self.round = round
        self.source = source
        self.target = target
        self.type = type
        self.destination = destination


class Link(object):
    '''拓扑网络中的数据包，包含路由相关信息'''
    def __init__(self, packet: TPPacket,  delay:int, outnetobj:"TopologyNetwork"):
        self.packet = packet
        self.delay = delay
        self.rcv_round = 0
        self.outnetobj = outnetobj  # 外部网络类实例


    def get_msg(self):
        return self.packet.payload
    
    def get_msg_name(self):
        if isinstance(self.packet.payload, Block):
            return self.packet.payload.name
        
    def target_id(self):
        return self.packet.target
    
    def target_miner(self):
        return self.outnetobj.miners[self.packet.target]
    
    def source(self):
        return self.packet.source

    def source_miner(self):
        return self.outnetobj.miners[self.packet.source]
    
    
class TopologyNetwork(Network):
    '''拓扑P2P网络'''                        
    def __init__(self, miners):
        super().__init__()
        self.miners:list[Miner] = miners
        self.adv_minerids = [m.miner_id for m in miners if m.isAdversary]
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
        self.moving = False
        self.network_tape:list[Link] = []
        self.active_links:list[Link] = []
        self.received_miners = defaultdict(list)
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
        TTL (int): 数据包的最大生存周期, 为了防止因孤立节点或日蚀攻击,导致该包一直在网络中
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
  

    def access_network(self, new_msgs:list[Message], minerid:int, target:int, round:int):
        '''本轮新产生的消息添加到network_tape.

        param
        -----
        new_msg (list) : The newly generated message 
        minerid (int) : Miner_ID of the miner generated the message.
        round (int) : Current round. 
        '''        
        for msg in new_msgs:
            packet = TPPacket(msg, round, minerid, target)
            if isinstance(msg, Block):
                if self.miners[target].consensus.is_in_local_chain(msg):
                    self.miners[minerid].get_reply(msg.name, target, False, round)
                    continue
            delay = self.cal_delay(msg, minerid, target)
            link = Link(packet, delay, self)
            self.active_links.append(link)
            self.received_miners[link.get_msg_name()].append(minerid)
            # self.miners[minerid].receive(packet)
            # 这一条防止adversary集团的代表，自己没有接收到该消息
            if isinstance(msg, Block):
                logger.info("%s access network: M%d -> M%d, round %d", 
                        msg.name, minerid, target, round)


    def cal_delay(self, msg: Message, source:int, target:int):
        '''计算sourceid和targetid之间的时延'''
        # 传输时延=消息大小除带宽 且传输时延至少1轮
        bw_mean = self.network_graph.edges[source, target]['bandwidth']
        bandwidth = np.random.normal(bw_mean,0.2*bw_mean)
        transmision_delay = math.ceil(msg.size / bandwidth)
        # 时延=处理时延+传输时延
        delay = self.miners[source].processing_delay + transmision_delay
        return delay    
    
    def diffuse(self, round):
        '''传播过程'''
        died_links = []
         # 传播完成，target接收数据包
        if len(self.active_links) != 0:
            for i, link in enumerate(self.active_links):
                if link.delay > 0:
                    link.delay -= 1
                    continue
                link.target_miner().receive(link.packet)
                link.source_miner().get_reply(link.get_msg_name(), 
                                              link.target_id(), True, round)
                if self.received_miners[link.get_msg_name()][-1]!=-1:
                    self.received_miners[link.get_msg_name()].append(link.target_id())
                self.record_block_propagation_time(link.packet, round)
                died_links.append(i)
        
        # 清理传播结束的link
        if len(died_links) != 0:
            self.active_links = [link for i, link in enumerate(self.active_links) 
                                if i not in died_links]
            died_links.clear()

        # forward 过程
        for m in self.miners:
            m.forward(round)
        

    def moving(self, round):
        moving_prob = 0.01
        if random.uniform(0, 1) > moving_prob:
            return
        edges = list(self.network_graph.edges)
        for edge in edges:
            node1, node2 = edge
            self.network_graph.remove_edge(node1, node2)
            self.miners[node1].remove_neighbor(node2)
            self.miners[node1].remove_neighbor(node1)

        



    def record_block_propagation_time(self, packet: TPPacket, r):
        '''calculate the block propagation time'''
        if not isinstance(packet.payload, Block):
            return

        rn = len(set(self.received_miners[packet.payload.name]))
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
            if  self.received_miners[packet.payload.name][-1] != -1:
                self.ave_block_propagation_times[rcv_rate] += r-packet.payload.blockhead.timestamp
                self.block_num_bpt[rcv_rates.index(rcv_rate)] += 1
                # logger.info(f"{packet.payload.name}:{rn},{rcv_rate} at round {r}")
            if rn == mn and self.received_miners[packet.payload.name][-1] != -1:
                self.received_miners[packet.payload.name][-1] = -1

    def cal_block_propagation_times(self):
        rcv_rates = [k for k in self.ave_block_propagation_times.keys()]
        for i ,  rcv_rate in enumerate(rcv_rates):
            total_bpt = self.ave_block_propagation_times[rcv_rate ]
            total_num = self.block_num_bpt[i]
            if total_num == 0:
                continue
            self.ave_block_propagation_times[rcv_rate] = round(total_bpt/total_num, 3)
        
        return self.ave_block_propagation_times

    


    def cal_neighbor_delays(self, msg: Message, minerid:int):
        '''计算minerid的邻居的时延'''
        neighbor_delays = []
        for neighborid in self.miners[minerid].neighbors:
            delay = self.cal_delay(msg, minerid, neighborid)
            neighbor_delays.append(delay)
        return neighbor_delays
    

    def generate_network(self, gen_net_approach, ave_degree=None):
        '''
        根据csv文件的邻接矩'adj'或coo稀疏矩阵'coo'生成网络拓扑    
        '''
        # read from csv finished
        try:
            if gen_net_approach == 'adj':
                self.gen_network_by_adj()
            elif gen_net_approach == 'coo':
                self.gen_network_by_coo()
            elif gen_net_approach == 'rand' and ave_degree is not None:
                self.gen_network_rand(ave_degree)
            else:
                raise errors.NetGenError('网络生成方式错误！')
            
            #检查是否有孤立节点或不连通部分
            if nx.number_of_isolates(self.network_graph) != 0:
                raise errors.NetUnconnetedError(f'Isolated nodes in the network! '
                    f'{list(nx.isolates(self.network_graph))}')
            if nx.number_connected_components(self.network_graph) != 1:
                if gen_net_approach != 'rand':
                    raise errors.NetIsoError('Brain-split in the newtork! ')
                retry_num = 10
                for _ in range(retry_num):
                    self.gen_network_rand(ave_degree)
                    if nx.number_connected_components(self.network_graph) == 1:
                        break
                if nx.number_connected_components(self.network_graph) == 1:
                    raise errors.NetIsoError(f'Brain-split in the newtork! '
                        f'Choose an appropriate degree, current: {ave_degree}')
                
            
            # 邻居节点保存到各miner的neighbor_list中
            for minerid in list(self.network_graph.nodes):
                self.miners[int(minerid)].neighbors = \
                    list(self.network_graph.neighbors(int(minerid)))
                
            # 结果展示和保存
            #print('adjacency_matrix: \n', self.tp_adjacency_matrix,'\n')
            self.draw_and_save_network()
            self.save_network_attribute()
                
        except (errors.NetMinerNumError, errors.NetAdjError, errors.NetIsoError, 
                errors.NetUnconnetedError, errors.NetGenError) as error:
            print(error)
            sys.exit(0)
    
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


    def gen_network_by_adj(self):
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
                    


    def gen_network_by_coo(self):
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

    
    def set_node_pos(self):
        '''使用spring_layout设置节点位置'''
        self.node_pos = nx.spring_layout(self.network_graph, seed=50)

    def draw_and_save_network(self):
        """
        展示和保存网络拓扑图self.network_graph
        """
        self.set_node_pos()
        # plt.ion()
        # plt.figure(figsize=(12,10))
        node_size = 200*3/self.MINER_NUM**0.5
        font_size = 30/self.MINER_NUM**0.5
        line_width = 3/self.MINER_NUM**0.5
        #nx.draw(self.network_graph, self.draw_pos, with_labels=True,
        #  node_size=node_size,font_size=30/(self.MINER_NUM)^0.5,width=3/self.MINER_NUM)
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



    def write_routing_to_json(self, block_packet:Link):
        """
        每当一个block传播结束,将其路由结果记录在json文件中
        json文件包含origin_miner和routing_histroy两种信息
        """
        if not isinstance(block_packet.packet, Block):
            return

        bp = block_packet
        with open(self.NET_RESULT_PATH / 'routing_history.json', 'a+', encoding = 'utf-8') as f:
            f.seek(f.tell() - 1, os.SEEK_SET)
            f.truncate()
            f.write(',')
            bp.routing_histroy = {str(k): bp.routing_histroy[k] for k in bp.routing_histroy}
            json.dump({str(bp.packet.name): {'origin_miner': bp.minerid, 'routing_histroy': bp.routing_histroy}},
                      f, indent=2)
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
        route_graph = nx.DiGraph()

        route_graph.add_nodes_from(self.network_graph.nodes)

        for (source_node, target_node), strounds in routing_histroy_single_block.items():
            route_graph.add_edge(source_node, target_node, trans_histroy=strounds)

        # 画图和保存结果
        # 处理节点颜色
        node_colors = []
        for n, d in route_graph.nodes(data=True):
            if self.miners[n].isAdversary and n != origin_miner:
                node_colors.append("red")
            elif n == origin_miner:
                node_colors.append("green")
            else:
                node_colors.append('#1f78b4')
        node_size = 100*3/self.MINER_NUM**0.5
        nx.draw_networkx_nodes(
            route_graph, 
            pos = self.node_pos, 
            node_size = node_size,
            node_color = node_colors)
        nx.draw_networkx_labels(
            route_graph, 
            pos = self.node_pos, 
            font_size = 30/self.MINER_NUM**0.5,
            font_family = 'times new roman')
        # 对边进行分类，分为单向未传播完成的、双向未传播完成的、已传播完成的
        edges_not_complete_single = [
            (u, v) for u, v, d in route_graph.edges(data=True) 
            if d["trans_histroy"][1] == 0 and (v, u) not in  route_graph.edges()]
        edges_not_complete_double = [
            (u, v) for u, v, d in route_graph.edges(data=True) 
            if d["trans_histroy"][1] == 0 and (v, u) in  route_graph.edges() 
            and u > v]
        edges_complete = [
            ed for ed in [(u, v) for u, v, d in route_graph.edges(data=True) 
            if (u, v)not in edges_not_complete_single 
            and (u, v) not in edges_not_complete_double 
            and (v, u) not in edges_not_complete_double]]
        # 画边
        width = 3/self.MINER_NUM**0.5
        nx.draw_networkx_edges(
            route_graph, 
            self.node_pos, 
            edgelist = edges_complete, 
            edge_color = 'black', 
            width = width,
            alpha = 1,
            node_size = node_size,
            arrowsize = 30/self.MINER_NUM**0.5)
        nx.draw_networkx_edges(
            route_graph, 
            self.node_pos, 
            edgelist = edges_not_complete_single, 
            edge_color = 'black',
            width = width,style='--', 
            alpha = 0.3,
            node_size = node_size,
            arrowsize = 30/self.MINER_NUM**0.5)
        nx.draw_networkx_edges(
            route_graph, 
            self.node_pos, 
            edgelist = edges_not_complete_double, 
            edge_color = 'black',
            width = width,style='--', 
            alpha = 0.3,
            node_size = node_size,
            arrowstyle = '<|-|>',
            arrowsize = 30/self.MINER_NUM**0.5)                      
        # 没有传播到的边用虚线画
        edges_list_extra = []
        for (u, v) in self.network_graph.edges:
            if (((u, v) not in route_graph.edges) and 
                ((v, u) not in route_graph.edges)):
                route_graph.add_edge(u, v, trans_histroy=None)
                edges_list_extra.append((u, v))
        nx.draw_networkx_edges(
            route_graph, 
            pos = self.node_pos, 
            edgelist = edges_list_extra, 
            edge_color = 'black',
            width = 3/self.MINER_NUM**0.5,
            alpha = 0.3, 
            style = '--', 
            arrows = False)
        # 处理边上的label，对单向的双向和分别处理
        if self.show_label:
            # 单向
            edge_labels = {
                (u, v): f'{u}-{v}:{d["trans_histroy"]}' 
                        for u, v, d in route_graph.edges(data=True)
                        if (v, u) not in route_graph.edges()}
            # 双向
            edge_labels.update(dict(
                [((u, v), f'{u}-{v}:{d["trans_histroy"]}\n\n'
                          f'{v}-{u}:{route_graph.edges[(v, u)]["trans_histroy"]}')
                          for u, v, d in route_graph.edges(data=True) 
                          if v > u and (v, u) in route_graph.edges()]))
            nx.draw_networkx_edge_labels(
                route_graph, 
                self.node_pos, 
                edge_labels = edge_labels, 
                font_size = 7*2/self.MINER_NUM**0.5,
                font_family = 'times new roman')
        #保存svg图片
        NET_RESULT_PATH = global_var.get_net_result_path()
        plt.savefig(NET_RESULT_PATH / (f'routing_graph{blockname}.svg'))
        plt.close()

