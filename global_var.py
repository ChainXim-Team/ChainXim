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
    _var_dict['blocks_generated'] = 0
    _var_dict['double_spending_strategy'] = 2
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
    _var_dict['VTNUM'] = 3
    _var_dict['unref_tx'] = []
    _var_dict['unref_prp'] = []
    _var_dict['VOTE_COUNT'] = {}
    _var_dict['ARRIVE_TIME'] = {}
    _var_dict['ARRIVE_TIME_TX'] = {}
    _var_dict['ARRIVE_TIME_PRP'] = {}
    _var_dict['TXPOOL'] = []
    _var_dict['TX_NUM'] = 0
    _var_dict['TX_NUM_HO'] = 0
    _var_dict['Throughput count'] = {}
    _var_dict['Confirmed_height'] = []
    _var_dict['adver_ids'] = []
    _var_dict['attack_flag_doublespending'] = False
    _var_dict['attack_flag_balanceattack'] = False
    _var_dict['balanceattack_height'] = []
    _var_dict['DELAYED_SELF_RECEIVE'] = False
    _var_dict['balanceattack_height_vt'] = {}
    _var_dict['global_prpchain'] = None
    _var_dict['ds_try_times'] = 0
    _var_dict['ds_success_times'] = 0
    _var_dict['depth'] = 1
    _var_dict['stop_onetime_double_spending'] = True
    _var_dict['onetime_double_spending'] = False
    _var_dict['ds_height'] = 0
    _var_dict['threshold_chain_index'] = None
    _var_dict['threshold_chain_flag'] = 0
    _var_dict['custom_vote_threshold'] = None  # 自定义得票阈值

def get_threshold_chain_flag():
    return _var_dict['threshold_chain_flag']

def set_threshold_chain_flag(flag):
    _var_dict['threshold_chain_flag'] = flag

def get_threshold_num():
    return _var_dict['threshold_chain_index']

def set_threshold_num(num):
    _var_dict['threshold_chain_index'] = num

def set_custom_vote_threshold(threshold):
    """设置自定义得票阈值"""
    _var_dict['custom_vote_threshold'] = threshold

def get_custom_vote_threshold():
    """获取自定义得票阈值，如果未设置则返回默认值（VTNUM的一半加1）"""
    return _var_dict['custom_vote_threshold']

def get_vote_threshold():
    """获取当前有效的得票阈值"""
    return get_custom_vote_threshold()

def get_ds_height():
    return _var_dict['ds_height']

def set_ds_height(height):
    _var_dict['ds_height'] = height


def add_block_generated():
    _var_dict['blocks_generated'] += 1

def get_blocks_generated():
    return _var_dict['blocks_generated']

def get_onetime_double_spending_flag():
    """更新区块到达的轮次"""
    return _var_dict['onetime_double_spending']

def set_onetime_double_spending(status):
    """更新区块到达的轮次"""
    _var_dict['stop_onetime_double_spending'] = status

def get_onetime_double_spending():
    """更新区块到达的轮次"""
    return _var_dict['stop_onetime_double_spending']

def set_arrive_time_tx(block_name, round):
    """更新区块到达的轮次"""
    _var_dict['ARRIVE_TIME_TX'][block_name] = round

def set_arrive_time_prp(block_name, round):
    """更新区块到达的轮次"""
    _var_dict['ARRIVE_TIME_PRP'][block_name] = round

def get_ar_time_tx():
    return _var_dict['ARRIVE_TIME_TX']

def get_ar_time_prp():
    return _var_dict['ARRIVE_TIME_PRP']



def get_depth():
    return _var_dict['depth']

def set_depth(x):
    _var_dict['depth'] = x

def set_vtnum(n):
    '''获得网络类型'''
    _var_dict['VTNUM'] = n

def set_double_spending_strategy(double_spending_strategy):
    _var_dict['double_spending_strategy'] = double_spending_strategy

def get_double_spending_strategy():
    return _var_dict['double_spending_strategy']

def get_ds_try_times():
    return _var_dict['ds_try_times']

def add_ds_try_times():
    _var_dict['ds_try_times'] += 1

def get_ds_success_times():
    return _var_dict['ds_success_times']

def add_ds_success_times():
    _var_dict['ds_success_times'] += 1

def set_global_prpchain(prpchain):
    '''设置日志级别'''
    _var_dict['global_prpchain'] = prpchain

def get_global_prpchain():
    '''设置日志级别'''
    return _var_dict['global_prpchain']

def set_height_BA_vt(height):
    '''设置日志级别'''
    _var_dict['balanceattack_height_vt'] = height

def get_height_BA_vt():
    '''设置日志级别'''
    return _var_dict['balanceattack_height_vt']

def set_height_BA(height):
    '''设置日志级别'''
    _var_dict['balanceattack_height'].append(height)

def remove_height_BA(height):
    _var_dict['balanceattack_height'].remove(height)

def clear_height_BA(height):
    _var_dict['balanceattack_height'] = []

def get_height_BA():
    '''设置日志级别'''
    return _var_dict['balanceattack_height']

def set_attack_flag_BA(flag):
    '''设置日志级别'''
    _var_dict['attack_flag_balanceattack'] = flag

def get_attack_flag_BA():
    '''设置日志级别'''
    return _var_dict['attack_flag_balanceattack']

def set_attack_flag_ds(flag):
    '''设置日志级别'''
    _var_dict['attack_flag_doublespending'] = flag

def get_attack_flag_ds():
    '''设置日志级别'''
    return _var_dict['attack_flag_doublespending']

def set_adver_ids(id):
    '''设置日志级别'''
    _var_dict['adver_ids'] = id

def get_adver_ids():
    '''设置日志级别'''
    return _var_dict['adver_ids']

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
    '''定义网络类型 type:str'''
    _var_dict['ATTACK_EXECUTE_TYPE'] = attack_execute_type

def get_attack_execute_type():
    '''获得网络类型'''
    return _var_dict['ATTACK_EXECUTE_TYPE']

def get_vtnum():
    '''获得网络类型'''
    return _var_dict['VTNUM']

def get_unreftx():
    return _var_dict['unref_tx']

def get_unrefprp():
    return _var_dict['unref_prp']

def clear_unreftx():
    _var_dict['unref_tx'] = []

def clear_unrefprp():
    _var_dict['unref_prp'] = []

def remove_unreftx(item):
    '''Remove a specific item from _var_dict['unref_tx']'''
    if item in _var_dict['unref_tx']:
        _var_dict['unref_tx'].remove(item)

def remove_unrefprp(item):
    '''Remove a specific item from _var_dict['unref_prp']'''
    if item in _var_dict['unref_prp']:
        _var_dict['unref_prp'].remove(item)

def get_vtcount():
    return _var_dict['VOTE_COUNT']

def write_vtcount(vote_count):
    _var_dict['VOTE_COUNT'] = vote_count

def set_arrive_time(block_name, round):
    """更新区块到达的轮次"""
    _var_dict['ARRIVE_TIME'][block_name] = round

def get_txnum():
    return _var_dict['TX_NUM']

def set_txho(txho):
    _var_dict['TX_NUM_HO'] = txho

def add_tx(tx):
    _var_dict['TXPOOL'].append(tx)

def get_txpool():
    return _var_dict['TXPOOL']

def get_ar_time():
    return _var_dict['ARRIVE_TIME']

def set_thcount(i, nm):
    """更新区块到达的轮次"""
    _var_dict['Throughput count'][i] = nm

def get_txnum():
    return _var_dict['TX_NUM']

def rec_tx():
    _var_dict['TX_NUM'] = _var_dict['TX_NUM'] + 1

def set_cfheight(i):
    """更新区块到达的轮次"""
    _var_dict['Confirmed_height'].append(i)

def get_cfheight():
    return _var_dict['Confirmed_height']

def set_delayed_self_receive(flag: bool):
    _var_dict['DELAYED_SELF_RECEIVE'] = bool(flag)

def get_delayed_self_receive() -> bool:
    return _var_dict.get('DELAYED_SELF_RECEIVE', True)

