'''
    全局变量
'''
import logging
import time
from pathlib import Path


def __init__(result_path:Path = None): 
    # current_time = time.strftime("%Y%m%d-%H%M%S")
    RESULT_FOLDER = Path.cwd() / 'Results' / time.strftime("%Y%m%d")
    RESULT_FOLDER.mkdir(parents=True,exist_ok = True)   
    RESULT_PATH=result_path or RESULT_FOLDER  / time.strftime("%H%M%S")
    RESULT_PATH.mkdir(parents=True,exist_ok = True)   
    NET_RESULT_PATH=RESULT_PATH / 'Network Results'
    NET_RESULT_PATH.mkdir(parents=True,exist_ok = True)
    CHAIN_DATA_PATH=RESULT_PATH / 'Chain Data'
    CHAIN_DATA_PATH.mkdir(parents=True,exist_ok = True)
    ATTACK_RESULT_PATH=RESULT_PATH / 'Attack Result'
    ATTACK_RESULT_PATH.mkdir(parents=True,exist_ok = True)
    '''
    初始化
    '''
    global _var_dict
    _var_dict = {}
    _var_dict['MINER_NUM']=0
    _var_dict['POW_TARGET']=''
    _var_dict['AVE_Q']=0
    _var_dict['CONSENSUS_TYPE']='consensus.PoW'
    _var_dict['NETWORK_TYPE']='network.FullConnectedNetwork'
    _var_dict['BLOCK_NUMBER'] = 0
    _var_dict['RESULT_PATH'] = RESULT_PATH
    _var_dict['NET_RESULT_PATH'] = NET_RESULT_PATH
    _var_dict['ATTACK_RESULT_PATH'] = ATTACK_RESULT_PATH
    _var_dict['CHAIN_DATA_PATH'] = CHAIN_DATA_PATH
    _var_dict['BLOCKSIZE'] = 2
    _var_dict['SEGMENTSIZE'] = 0
    _var_dict['LOG_LEVEL'] = logging.INFO
    _var_dict['Show_Fig'] = False
    _var_dict['COMPACT_OUTPUT'] = True
    _var_dict['ATTACK_EXECUTE_TYPE']='execute_sample0'
    _var_dict['CHECK_POINT'] = None
    _var_dict['COMMON_PREFIX_ENABLE'] = False

def set_common_prefix_enable(common_prefix_enable):
    '''设置是否启用common prefix pdf type:bool'''
    _var_dict['COMMON_PREFIX_ENABLE'] = common_prefix_enable

def get_common_prefix_enable():
    '''是否启用common prefix pdf计算'''
    return _var_dict['COMMON_PREFIX_ENABLE']

def set_log_level(log_level):
    '''设置日志级别'''
    _var_dict['LOG_LEVEL'] = log_level

def get_log_level():
    '''获得日志级别'''
    return _var_dict['LOG_LEVEL']

def set_consensus_type(consensus_type):
    '''定义共识协议类型 type:str'''
    _var_dict['CONSENSUS_TYPE'] = consensus_type
def get_consensus_type():
    '''获得共识协议类型'''
    return _var_dict['CONSENSUS_TYPE']

def set_miner_num(miner_num):
    '''定义矿工数量 type:int'''
    _var_dict['MINER_NUM'] = miner_num
def get_miner_num():
    '''获得矿工数量'''
    return _var_dict['MINER_NUM']

def set_PoW_target(PoW_target):
    '''定义pow目标 type:str'''
    _var_dict['POW_TARGET'] = PoW_target
def get_PoW_target():
    '''获得pow目标'''
    return _var_dict['POW_TARGET']

def set_ave_q(ave_q):
    '''定义pow,每round最多hash计算次数 type:int'''
    _var_dict['AVE_Q'] = ave_q
def get_ave_q():
    '''获得pow,每round最多hash计算次数'''
    return _var_dict['AVE_Q']

def get_block_number():
    '''获得产生区块的独立编号'''
    _var_dict['BLOCK_NUMBER'] = _var_dict['BLOCK_NUMBER'] + 1
    return _var_dict['BLOCK_NUMBER']

def get_result_path():
    return _var_dict['RESULT_PATH']

def get_net_result_path():
    return _var_dict['NET_RESULT_PATH']

def get_chain_data_path():
    return _var_dict['CHAIN_DATA_PATH']

def get_attack_result_path():
    return _var_dict['ATTACK_RESULT_PATH']

def set_network_type(network_type):
    '''定义网络类型 type:str'''
    _var_dict['NETWORK_TYPE'] = network_type
def get_network_type():
    '''获得网络类型'''
    return _var_dict['NETWORK_TYPE']

def set_blocksize(blocksize):
    _var_dict['BLOCKSIZE'] = blocksize

def get_blocksize():
    return _var_dict['BLOCKSIZE']

def set_segmentsize(segmentsize):
    _var_dict['SEGMENTSIZE'] = segmentsize

def get_segmentsize():
    return _var_dict['SEGMENTSIZE']

def set_show_fig(show_fig):
    _var_dict['Show_Fig'] = show_fig

def get_show_fig():
    return _var_dict['Show_Fig']

def set_compact_outputfile(compact_outputfile):
    _var_dict['COMPACT_OUTPUT'] = compact_outputfile

def get_compact_outputfile():
    return _var_dict['COMPACT_OUTPUT']

def set_attack_execute_type(attack_execute_type):
    '''定义攻击类型 type:str'''
    _var_dict['ATTACK_EXECUTE_TYPE'] = attack_execute_type

def get_attack_execute_type():
    '''定义攻击类型'''
    return _var_dict['ATTACK_EXECUTE_TYPE']