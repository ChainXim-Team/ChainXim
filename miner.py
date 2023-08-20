from chain import Block, Chain
from consensus import Consensus
from functions import for_name
from external import I
# from external import validate
import global_var
from network import Message

class Miner(object):

    def __init__(self, Miner_ID, consensus_params:dict):
        self.Miner_ID = Miner_ID #矿工ID
        self.isAdversary = False
        #共识相关
        self.consensus:Consensus = for_name(global_var.get_consensus_type())(Miner_ID, 
                                                                             consensus_params)    # 共识
        #输入内容相关
        self.input_tape = []
        #网络相关
        self.neighbor_list = []
        self.processing_delay=0    #处理时延

        #保存矿工信息
        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        with open(CHAIN_DATA_PATH / f'chain_data{str(self.Miner_ID)}.txt','a') as f:
            print(f"Miner {self.Miner_ID}\n"
                  f"consensus_params: {consensus_params}", file=f)


    def set_adversary(self, isAdversary:bool):
        '''
        设置是否为对手节点
        isAdversary=True为对手节点
        '''
        self.isAdversary = isAdversary

    def receive(self, msg: Message):
        '''处理接收到的消息，直接调用consensus.receive'''
        return self.consensus.receive(msg)

    def launch_consensus(self, input):
        '''开始共识过程\n
        return:
            new_msg 由共识类产生的新消息，没有就返回None type:list[Message]/None
            msg_available 如果有新的消息产生则为True type:Bool
        '''
        new_msg, msg_available = self.consensus.consensus_process(self.Miner_ID,self.isAdversary,input)
        return new_msg, msg_available  # 返回挖出的区块，

    def BackboneProtocol(self, round):
        chain_update, update_index = self.consensus.maxvalid()
        input = I(round, self.input_tape)  # I function
        new_msg, msg_available = self.launch_consensus(input)
        if update_index or msg_available:
            return new_msg
        else:
            return None  #  如果没有更新 返回空告诉environment回合结束
        
    # def ValiChain(self, blockchain: Chain = None):
    #     '''
    #     检查是否满足共识机制\n
    #     相当于原文的validate
    #     输入:
    #         blockchain 要检验的区块链 type:Chain
    #         若无输入,则检验矿工自己的区块链
    #     输出:
    #         IsValid 检验成功标识 type:bool
    #     '''
    #     if blockchain is None:#如果没有指定链则检查自己
    #         IsValid=self.consensus.valid_chain(self.Blockchain.lastblock)
    #         if IsValid:
    #             print('Miner', self.Miner_ID, 'self_blockchain validated\n')
    #         else:
    #             print('Miner', self.Miner_ID, 'self_blockchain wrong\n')
    #     else:
    #         IsValid = self.consensus.valid_chain(blockchain)
    #         if not IsValid:
    #             print('blockchain wrong\n')
    #     return IsValid
