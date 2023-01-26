'''
    全局变量
'''
import os
import time
# MINER_NUM = 10
def __init__(): 
    current_time = time.strftime("%Y%m%d-%H%M%S")
    RESULT_PATH=os.getcwd()+'\\'+'Results'+'\\'+current_time
    os.makedirs(RESULT_PATH) 
    NET_RESULT_PATH=RESULT_PATH+'\\'+'Network Results'
    os.makedirs(NET_RESULT_PATH) 
    '''
    初始化
    '''
    global _var_dict
    _var_dict = {}
    _var_dict['MINER_NUM']=0
    _var_dict['POW_TARFET']=''
    _var_dict['POW_QMAX']=0
    _var_dict['CONSENSUS_TYPE']='consensus.PoW'
    _var_dict['NETWORK_TYPE']='network.FullConnectedNetwork'
    _var_dict['BLOCK_NUMBER'] = 0
    _var_dict['RESULT_PATH'] = RESULT_PATH
    _var_dict['NET_RESULT_PATH'] = NET_RESULT_PATH
    _var_dict['Attack'] = False
    _var_dict['Blocksize'] = 2

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
    _var_dict['POW_TARFET'] = PoW_target
def get_PoW_target():
    '''获得pow目标'''
    return _var_dict['POW_TARFET']

def set_qmax(PoW_qmax):
    '''定义pow,每round最多hash计算次数 type:int'''
    _var_dict['POW_QMAX'] = PoW_qmax
def get_qmax():
    '''获得pow,每round最多hash计算次数'''
    return _var_dict['POW_QMAX']

def get_block_number():
    '''获得产生区块的独立编号'''
    _var_dict['BLOCK_NUMBER'] = _var_dict['BLOCK_NUMBER'] + 1
    return _var_dict['BLOCK_NUMBER']

def get_result_path():
    return _var_dict['RESULT_PATH']

def get_net_result_path():
    return _var_dict['NET_RESULT_PATH']

def set_network_type(network_type):
    '''定义网络类型 type:str'''
    _var_dict['NETWORK_TYPE'] = network_type
def get_network_type():
    '''获得网络类型'''
    return _var_dict['NETWORK_TYPE']

def activate_attacktion():
    _var_dict['Attack'] = True

def set_blocksize(blocksize):
    _var_dict['Blocksize'] = blocksize

def get_blocksize():
    return _var_dict['Blocksize']

def set_show_fig(show_fig):
    _var_dict['Show_Fig'] = show_fig

def get_show_fig():
    return _var_dict['Show_Fig']