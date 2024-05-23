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

from .._consts import _IDLE, FLOODING, INV, OUTER, SELF, SELFISH, SPEC_TARGETS
from .nic_abc import NetworkInterface

logger = logging.getLogger(__name__)


class NICWithTp(NetworkInterface):
    def __init__(self, miner) -> None:
        super().__init__(miner)
        self._neighbors:list[int] = []

        # self._default_forward_strategy = FLOODING
        

        # 暂存本轮收到的数据包
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
        if self._channel_states[remove_id] != _IDLE:
            self._output_queues[remove_id].insert(0, self._channel_states[remove_id])
        if len(self._output_queues[remove_id]) == 0:
            self._output_queues.pop(remove_id, None)
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
        # logger.info("round%d, M%d: added neighbour M%d", 
        #             round, self.miner.miner_id, add_id)
        self.ready_to_forward(add_id, round)
       


    def nic_receive(self, packet: Packet):
        '''处理接收到的消息，直接调用consensus.receive'''
        self._receive_buffer.append(packet)
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
        return self.miner.receive(payload.msg)

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
        # forward_msgs:list[Message] = []
        # forward_msgs.extend(self._forward_buffer[SELF])
        # forward_msgs.extend(self._forward_buffer[OUTER])
        if (len(self._forward_buffer[SELF]) != 0 or 
            len(self._forward_buffer[OUTER]) != 0) :
        
            for [msg, strategy, spec_tgts] in self._forward_buffer[SELF]:
                # INV消息代表后续会同步链的所有新区块，只有泛洪转发会
                out_msg = INV if isinstance(msg, Block) and strategy == FLOODING else msg
                targets = self.select_target(out_msg, strategy, spec_tgts)
                if out_msg != INV and isinstance(out_msg, Block) and self.withSegments:
                    segs = self.seg_blocks(msg)
                    for target in  targets:
                        self._output_queues[target].extend(segs)
                else:
                    for target in  targets:
                        self._output_queues[target].append(out_msg)
                
                
            for [msg, strategy, spec_tgts] in self._forward_buffer[OUTER]:
                targets = self.select_target(msg, strategy, spec_tgts)
                if isinstance(msg, Block) and self.withSegments:
                    segs = self.seg_blocks(msg)
                    for target in  targets:
                        self._output_queues[target].extend(segs)
                else:
                    for target in  targets:
                        self._output_queues[target].append(msg)
            
            # logger.info("round %d, M%d, neighbors %s, outputqueue %s", 
            #             round,  self.miner_id, str(self._neighbors), str(dict(self._output_queues)))
            
        for neighbor in self._neighbors:
            if self._channel_states[neighbor] != _IDLE:
                continue
            que = self._output_queues[neighbor]
            if len(que) == 0:
                continue
            while len(self._output_queues[neighbor]) > 0:
                msg = que.pop(0)
                to_send = msg
                if isinstance(to_send,Block):
                    to_send = to_send.name
                if isinstance(to_send,Segment):
                    to_send = str((to_send.msg.name,to_send.seg_id))
                # logger.info("round %d, M%d->M%d, try to send %s", 
                #         round, self.miner_id, neighbor, to_send)
                if msg == "inv":
                    self.ready_to_forward(neighbor, round)
                    while len(self._output_queues[neighbor]) != 0:
                        msg = self._output_queues[neighbor].pop(0)
                        if msg != "inv":
                            break
                    
                    if msg == "inv" and len(self._output_queues[neighbor]) == 0:
                        break
                
                if (isinstance(msg, Block) and 
                    not self.pre_ask(neighbor, msg, round)):
                    continue

                self._channel_states[neighbor] = msg
                self.send_data([msg], neighbor, round)
                break
        
        self.clear_forward_buffer()

    def seg_blocks(self, block:Block):
        segids = list(range(block.segment_num))
        random.shuffle(segids)
        return [Segment(block, sid) for sid in segids]
    
    def pre_ask(self, target, msg:Block, round):
        """在发送某个区块前，询问其本地是否已经有该区块了"""
        inv = INVMsg(self.miner_id, target, msg, isSingleBlock=True)
        getDataReply  = self.inv_rpc(inv, round)
        # logger.info("round%d, M%d->M%d: %s require: %s", 
        #             round, self.miner_id, target, msg, getDataReply.require)
        return getDataReply.require
    
    def ready_to_forward(self, target:int, round:int):
        """新建连接或挖出新区块时和邻居对齐整链，所以inv消息包含本地lastblock"""
        
        inv = INVMsg(self.miner_id, target, 
                    self.miner.get_local_chain().get_last_block())
        
        getDataReply  = self.inv_rpc(inv, round)
        if not getDataReply.require:
            return
        
        if inv.target not in self._output_queues.keys():
            self._output_queues[inv.target] = []
        # logger.info("round%d, M%d -> M%d: getData %s", round, target, self.miner_id, 
        #             str([req_b.name for req_b in getDataReply.req_blocks]))
        if not self.withSegments:
            for req_b in getDataReply.req_blocks:
                self._output_queues[inv.target].append(req_b)
            return
        # 将需要的分段加入输出队列
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

        if inv.isSingleBlock:
            return getData
        
        if getData.require is False:
            return getData
        
        # 返回需要的区块列表
        getData.require = False
        # inv高度低于本地直接返回
        inv_h =  inv.block.get_height()
        loc_chain = self.miner.get_local_chain()
        loc_h = loc_chain.get_last_block().get_height()
        if inv_h < loc_h:
            if not self.miner.isAdversary:
                return getData
            else:
                getData.require = True
                getData.req_blocks = [inv.block]
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
    


            
    def select_target(self, msg:Message=None, strategy:str=FLOODING, spec_tgts:list=None):
        if strategy == FLOODING:
            return self.select_target_flooding(msg)
        if strategy == SPEC_TARGETS:
            if spec_tgts is None or len(spec_tgts) == 0:
                raise ValueError("Please specify the targets(SPEC_TARGETS)")
            return self.select_target_spec(msg, spec_tgts)
        if strategy == SELFISH:
            return []


    def select_target_flooding(self, block_msg:Block=None):
        """
        泛洪转发，转发给不包括source的邻居节点
        """
        targets = []
        msg_from = -1
        if block_msg is not None and block_msg != INV and isinstance(block_msg, Block):
            for packet in self._receive_buffer:
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
    

    def select_target_spec(self, block_msg:Block=None, spec_tgts:list = None):
        """
        泛洪转发，转发给不包括source的邻居节点
        """
        targets = [t for t in spec_tgts if t in self._neighbors]
        msg_from = -1
        if block_msg is not None and block_msg != INV and isinstance(block_msg, Block):
            for packet in self._receive_buffer:
                if not isinstance(packet.payload, Block):
                    continue
                if block_msg.name == packet.payload.name:
                    msg_from = packet.source
                    break
        targets = [t for t in spec_tgts if t in self._neighbors and t != msg_from]
        return targets

    
    def get_reply(self, msg_name, target:int, err:str, round):
        """
        消息发送完成后，用于接收是否发送成功的回复
        """
        # 传输成功即将信道状态置为空闲
        if err is None:
            # logger.info("round %d, M%d -> M%d: Forward  %s success!", 
            #         round, self.miner_id, target, msg_name)
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
        # logger.error("round %d, M%d -> M%d: Forward  %s unkonwn ERR!", 
        #             round, self.miner_id, target, msg_name)