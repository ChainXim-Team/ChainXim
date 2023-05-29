''' external functions (V,I,R, etc)'''
from typing import List

import global_var
from chain import Block, Chain


def V(xc:list):
    # content validation functionality
    # 这个函数的主要功能是检测区块链的内容（划重点，内容）是否符合要求
    # 比如交易信息有无重复等
    # 但因为这个框架不考虑账本内容，所以直接返回True即可
    return True

def I(round, input_tape:list):
    # insert functionality
    # bitcoin backbone 和 blockchain,round,RECEIVE 均无关
    if round <= 0:
        print('round error')
    if not input_tape:
        x = 0
    else:
        x = 0
        for instruction in input_tape:
            if instruction[0] == "INSERT":
                x = instruction[1]
                break
    return x

def R(blockchain:Chain):
    # chain reading functionality
    # 作用：把链的信息读取出来变成一个向量
    # 如果这是个树，就按照前序遍历读取（这是不对的后面可能                                                                                                                                                                                                                                                                                                                                                                                                     要修改，但目前对程序无影响）
    if blockchain is None:
        xc = []
    else:
        q = [blockchain.head]
        xc = []
        while q:
            block = q.pop(0)
            if block is None:
                print("block is None!")
                return
            xc.append(block.content)
            for i in block.next:
                q.append(i)
    return xc

def common_prefix(prefix1:Block, chain2:Chain):
    while prefix1:
        if chain2.search_chain(prefix1):
            break
        else:
            prefix1 = prefix1.last
    return prefix1

def chain_quality(blockchain:Chain):
    '''
    计算链质量指标
    para:blockchain
    return:cq_dict字典显示诚实和敌对矿工产生的块各有多少
        chain_quality_property诚实矿工产生的块占总区块的比值
    '''
    if not blockchain.head:
        xc = []
    else:
        blocktmp = blockchain.last_block()
        xc = []
        while blocktmp:
            xc.append(blocktmp.isAdversaryBlock)
            blocktmp = blocktmp.last
    cq_dict = {'Honest Block':0,'Adversary Block':0}
    for item in xc:
        if item is True:
            cq_dict.update({'Adversary Block':xc.count(item)})
        else:
            cq_dict.update({'Honest Block':xc.count(item)})
    adversary_block_num = xc.count(True)
    honest_block_num = xc.count(False)
    chain_quality_property = adversary_block_num/(adversary_block_num+honest_block_num)
    return cq_dict, chain_quality_property


def chain_growth(blockchain:Chain):
    '''
    计算链成长指标
    输入: blockchain
    输出：
    '''
    last_block = blockchain.last_block()
    return last_block.BlockHeight()



def printchain2txt(miner,chain_data_url='chain_data.txt'):
    '''
    前向遍历打印链中所有块到文件
    param:
        blockchain
        chain_data_url:打印文件位置,默认'chain_data.txt'
    '''
    #chain_data_url='chain_data.txt'
    CHAIN_DATA_PATH=global_var.get_chain_data_path()
    if not miner.Blockchain.head:
        with open(CHAIN_DATA_PATH / chain_data_url,'w+') as f:
            print("empty chain",file=f)
        return

    
"""    with open(CHAIN_DATA_PATH /chain_data_url,'w+') as f:
        print("Blockchian maintained BY Miner",miner.Miner_ID,file=f)    

        # 打印主链
        blocklist = miner.Blockchain.InversShowBlock()
        blocklist.reverse()
        for i in blocklist:
            print("{}→→→→".format(i.name),end="",file=f)
        print('\n',file=f)

        #打印链信息
        q:List[Block] = [miner.Blockchain.head]
        blocklist = []
        while q:
            block = q.pop(0)
            blocklist.append(block)
            print("blockname:",block.name,file=f)
            #print("is_adversary_block:",block.blockhead.is_adversary_block,file=f)
            print("isAdversaryBlock:",block.isAdversaryBlock,'\n'
            "prehash:",block.blockhead.prehash,'\n'
            "blockhash:",block.blockhead.blockhash,'\n'
            "target:",block.blockhead.target,'\n'
            "nonce:",block.blockhead.nonce,'\n'
            "height:",block.blockhead.height,'\n'
            "Miner:",block.blockhead.miner,'\n'
            "timestamp:",block.blockhead.timestamp,'\n'
            "content:",block.content,'\n',
            "blocksize",block.blocksize_MB,'byte','\n',file=f)
            if not block.blockextra:
                for k,v in block.blockextra:
                    print(f'{k}:',v,'\n',file=f)
            for i in block.next:
                q.append(i)
        
        #打印区块链参数
        print('\nChain Evaluation:\n',file=f)
        #chain_quality
        cq_dict,chain_quality_property=chain_quality(miner.Blockchain)
        print('Chain_Quality:',cq_dict,
        '\nChain_Quality_Property:',chain_quality_property,
        file=f)"""


# def print_chain_property2txt(blockchain:Chain,chain_property_url='chain_data.txt'):
#     '''
#     打印链参数到文件
#     param:
#         blockchain
#         chain_data_url:打印文件位置,默认与printchain2txt相同为'chain_data.txt'
#     '''
#     #chain_property_url='chain_data.txt'
#     printtype='a'
#     f=open(chain_property_url,printtype)
#     print('\nChain Evaluation:\n',file=f)
#     #chain_quality
#     cq_dict,chain_quality_property=chain_quality(blockchain)
#     print('Chain_Quality:',cq_dict,
#     '\nChain_Quality_Property:',chain_quality_property,
#     file=f
#     )

