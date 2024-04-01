import logging
import random
from collections import defaultdict

from data import Block, Message
from network import (
    ERR_OUTAGE,
    AdHocNetwork,
    GetDataMsg,
    INVMsg,
    Network,
    Packet,
    Segment,
    TopologyNetwork,
    TPPacket,
)

from .._consts import _IDLE, FLOODING, OUTER, SELF
from .nic_abc import NetworkInterface

logger = logging.getLogger(__name__)


class NICWithTp(NetworkInterface):
    def __init__(self, miner) -> None:
        super().__init__(miner)
        self._neighbors:list[int] = []

        self._forward_strategy = FLOODING
        

        # 暂存本轮收到的数据包
        self._rcv_packet_buffer:list[Packet]  = []
        self._segment_buffer = defaultdict(list[Message])

        # 输出队列(拓扑网络)
        self._output_queues = defaultdict(list[Message])
        self._channel_states = {}

    def nic_join_network(self, network):
        self._network = network
        self.init_queues()

    def init_queues(self):
        if len(self._neighbors) == 0:
            return
        # 初始化发送队列
        for neighbor in self._neighbors:
            self._output_queues[neighbor] = []
            self._channel_states[neighbor] = _IDLE

    def remove_neighbor(self, remove_id:int):
        """断开连接，从neighbor列表移除
        """
        if remove_id not in self._neighbors:
            logger.warning("M%d: removing neighbour M%d Failed! not connected", 
                           self.miner_id, remove_id)
            return
        self._neighbors = [n for n in self._neighbors if n != remove_id]
        # self._output_queues.pop(remove_id, None)
        # self._channel_states.pop(remove_id, None)
        if self._channel_states[remove_id] != _IDLE:
            self._output_queues[remove_id].insert(0, self._channel_states[remove_id])
        self._channel_states.pop(remove_id, None)
        
        # logger.info("M%d: removed neighbour M%d", self.miner_id, remove_id)

    def add_neighbor(self, add_id:int, round):
        if add_id in self._neighbors:
            logger.warning("M%d: adding neighbour M%d Failed! already connected", 
                           self.miner.miner_id,add_id)
            return
        self._neighbors.append(add_id)
        self._channel_states[add_id] = _IDLE
        if add_id not in self._output_queues.keys():
            self._output_queues[add_id] = []
        inv = INVMsg(self.miner.miner_id, add_id, 
                     self.miner.get_local_chain().get_last_block())
        self.ready_to_forward(inv, add_id, round)
        # logger.info("M%d: added neighbour M%d", self.miner.miner_id, add_id)


    def nic_receive(self, packet: Packet):
        '''处理接收到的消息，直接调用consensus.receive'''
        self._rcv_packet_buffer.append(packet)
        payload = packet.payload
        if not isinstance(payload, Segment):
            return self.miner.receive(payload)
        
        if not isinstance(payload.msg, Block):
            raise TypeError("Segment not contains a block!")

        block_name = payload.msg.name
        # 如果这个段中的区块已经收到过了，就不再处理
        if self.miner.in_local_chain(payload.msg):
            return False
        self._segment_buffer[block_name].append(payload.seg_id)
        if len(set(self._segment_buffer[block_name])) != payload.msg.segment_num:
            return False
        self._segment_buffer.pop(block_name)
        # logger.info("M%d: All %d segments of %s collected", self.miner.miner_id, 
        #             payload.msg.segment_num, payload.msg.name)
        self.miner.receive(payload)

    def _get_segids_not_rcv(self, block:Block):
        seg_ids = self._segment_buffer[block.name]
        return [sid for sid in seg_ids if sid not in list(range(block.segment_num))]


    def inv_rpc(self, inv:INVMsg, round:int ):
        """
        在转发前发送inv消息，包含自己将要发送的区块
        """
        # 发送的消息列表包含inv消息与期望的getDataReply，
        # 回应的getData会写入该Reply中
        getDataReply = GetDataMsg(require=False)
        self._network.access_network(
            [inv, getDataReply], self.miner.miner_id,  round, inv.target)
        # logger.info("round %d, Sending  inv , get reqblocks %s", round, 
        # str([b.name for b in getDataReply.req_blocks])) 
        return getDataReply
    

    def nic_forward(self, round):
        forward_msgs:list[Message] = []
        forward_msgs.extend(self._forward_buffer[SELF])
        forward_msgs.extend(self._forward_buffer[OUTER])
        if len(forward_msgs) == 0:
            return
        logger.info("round %d, Forwarding  %s ", 
                    round,  str([m.name for m in forward_msgs])) 
        
        targets = self.select_target()

        for msg in forward_msgs:
            out_msg = 'inv' if  isinstance(msg, Block) else msg
            for target in  targets:
                self._output_queues[target].append(out_msg)
            # logger.info("round %d, Sending  %s neighbor %s, outputqueue %s", 
            #         round,  out_msg,str(self._neighbors), str(self._output_queues))
            
        for neighbor in self._neighbors:
            que = self._output_queues[neighbor]
            if len(que) == 0:
                continue
            msg = que.pop(0)
            if msg == "inv":
                inv = INVMsg(self.miner.miner_id, neighbor, 
                             self.miner.get_local_chain().get_last_block())
                self.ready_to_forward(inv, neighbor, round)
                
                while msg == "inv" and len(self._output_queues[neighbor]) != 0:
                    msg = self._output_queues[neighbor].pop(0)
                
                if msg == "inv" and len(self._output_queues[neighbor]) == 0:
                    continue
            
            self._channel_states[neighbor] = msg
            self.send_data([msg], neighbor, round)
        
        self.clear_forward_buffer()

    
    def ready_to_forward(self, inv:INVMsg, target:int, round:int):
        """在新建连接时先根据本地最新区块新建"""
        if inv.target != target:
            raise ValueError("Inv not match the target!")
        
        getDataReply  = self.inv_rpc(inv, round)
        if not getDataReply.require:
            return
        
        if inv.target not in self._output_queues.keys():
            self._output_queues[inv.target] = []
        # 将需要的分段加入输出队列
        if not self.withSegments:
            for req_b in getDataReply.req_blocks:
                self._output_queues[inv.target].append(req_b)
            return
        for (req_b, segids) in getDataReply.req_segs:
            random.shuffle(segids)
            for sid in segids:
                self._output_queues[inv.target].append(Segment(req_b, sid))
        # 将完整区块分段后加入输出队列
        for req_b in getDataReply.req_blocks:
            segids = list(range(req_b.segment_num))
            random.shuffle(segids)
            for sid in segids:
                self._output_queues[inv.target].append(Segment(req_b, sid))
            


    def getdata(self, inv:INVMsg):
        """
        接收到inv消息后，检查自己是否需要该区块，返回getData
        """
        getData = GetDataMsg(self.miner.miner_id, inv.source, [inv.block])
        getData.require = not self.miner.in_local_chain(inv.block)

        if isinstance(self._network, AdHocNetwork):
            # 返回需要的区块列表

            if getData.require is False:
                return getData
            
            getData.require = False
            # inv高度低于本地直接返回
            inv_h =  inv.block.get_height()
            loc_chain = self.miner.get_local_chain()
            loc_h = loc_chain.get_last_block().get_height()
            if inv_h < loc_h:
                return getData
            getData.require = True
            getData.req_blocks = []
            req_b = inv.block
            while req_b is not None and not loc_chain.search_block(req_b):
                if self.withSegments and req_b.name in self._segment_buffer.keys():
                    # 已经收到部分分段，请求需要的分段
                    sids_notrcv = self._get_segids_not_rcv(req_b)
                    getData.req_segs.append((req_b, sids_notrcv))
                else:
                    getData.req_blocks.append(req_b)
                req_b = req_b.parentblock
        return getData
    
    def send_data(self, msgs:list[Message], target:int,round:int):
        """
        inv没问题后发送数据
        """
        self._network.access_network(msgs, self.miner_id, round, target)
    


            
    def select_target(self):
        if self._forward_strategy == FLOODING:
            return self.select_target_flooding()


    def select_target_flooding(self, block_msg:Block=None):
        """
        泛洪转发，转发给不包括source的邻居节点
        """
        targets = []
        msg_from = -1
        if block_msg is not None:
            for packet in self._rcv_packet_buffer:
                if not isinstance(packet.payload, Block):
                    continue
                if block_msg.name == packet.payload.name:
                    msg_from = packet.source
                    break
        
        for neighbor in self._neighbors:
            if neighbor == msg_from:
                continue
            targets.append(neighbor)
        return targets

    
    def get_reply(self, msg_name, target:int, err:str, round):
        """
        消息发送完成后，用于接收是否发送成功的回复
        """
        # 传输成功即将信道状态置为空闲
        if err is None:
            logger.info("round %d, M%d -> M%d: Forward  %s success!", 
                    round, self.miner_id, target, msg_name)
            self._channel_states[target]=_IDLE
            return
        # 信道中断将msg重新放回队列，等待下轮重新发送
        if err == ERR_OUTAGE:
            logger.info("round %d, M%d -> M%d: Forward  %s failed: link outage", 
                    round, self.miner_id, target, msg_name,)
            sending_msg = self._channel_states[target] 
            self._channel_states[target] = _IDLE
            self._output_queues[target].insert(0, sending_msg)
            return
        logger.error("round %d, M%d -> M%d: Forward  %s unkonwn ERR!", 
                    round, self.miner_id, target, msg_name)