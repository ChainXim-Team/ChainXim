''' external functions (V,I,R, etc)'''
from array import array
from data import Block, Chain


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

def R(last_block:Block):
    # chain reading functionality
    # 作用：把链的信息读取出来变成一个向量
    # 如果这是个树，就按照前序遍历读取（这是不对的后面可能要修改，但目前对程序无影响）
    if last_block is None:
        xc = array('Q')
    else:
        xc = array('Q')
        block = last_block
        while block:
            xc.extend(reversed(array('Q', block.blockhead.content)))
            block = block.parentblock
    return xc

MAX_SUFFIX = 10 # 最大链后缀回溯距离

def common_prefix(prefix1:Block, prefix2:Block):
    height1 = prefix1.get_height()
    height2 = prefix2.get_height()
    if height1 > height2:
        for _ in range(height1 - height2):
            if prefix1 is None:
                return None
            prefix1 = prefix1.parentblock
    elif height1 < height2:
        for _ in range(height2 - height1):
            if prefix2 is None:
                return None
            prefix2 = prefix2.parentblock
    while prefix1 and prefix2:
        if prefix1.blockhash == prefix2.blockhash:
            break
        prefix1 = prefix1.parentblock
        prefix2 = prefix2.parentblock
    return prefix1
    # while prefix1:
    #     if chain2.search_block(prefix1) is not None:
    #         break
    #     prefix1 = prefix1.parentblock
    # return prefix1

def chain_quality(block:Block, adversary_ids:list[int]):
    '''
    计算链质量指标
    paras:
        blockchain: the blockchain to calculate chain quality
        adversary_ids: the IDs of adversary miners
    return:
        cq_dict字典显示诚实和敌对矿工产生的块各有多少
        chain_quality_property诚实矿工产生的块占总区块的比值
    '''
    if not block:
        xc = []
    else:
        blocktmp = block
        xc = []
        while blocktmp:
            xc.append(blocktmp.blockhead.miner not in adversary_ids)
            blocktmp = blocktmp.parentblock
    adversary_block_num = xc.count(False)
    honest_block_num = xc.count(True)
    cq_dict = {'Honest Block':honest_block_num,'Adversary Block':adversary_block_num}
    chain_quality_property = adversary_block_num/(adversary_block_num+honest_block_num)
    return cq_dict, chain_quality_property


def chain_growth(blockchain:Chain):
    '''
    计算链成长指标
    输入: blockchain
    输出：
    '''
    last_block = blockchain.get_last_block()
    return last_block.get_height()
