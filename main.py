import configparser
import logging
import time

import numpy as np

import global_var
from environment import Environment


def get_time(f):
    def inner(*arg, **kwarg):
        s_time = time.time()
        res = f(*arg, **kwarg)
        e_time = time.time()
        print('耗时：{}秒'.format(e_time - s_time))
        return res
    return inner

@get_time
def run(Z:Environment, total_round: int, max_height: int, process_bar_type):
    Z.exec(total_round, max_height, process_bar_type)
    return Z.view_and_write()

def config_log(env_config:dict):
    """配置日志"""
    level_str = env_config.get('log_level', 'info')
    if level_str == 'error':
        global_var.set_log_level(logging.ERROR)
    elif level_str == 'warning':
        global_var.set_log_level(logging.WARNING)
    elif level_str == 'info':
        global_var.set_log_level(logging.INFO)
    elif level_str == 'debug':
        global_var.set_log_level(logging.DEBUG)
    else:
        raise ValueError("config error log_level must be set as " +
                         "error/warning/info/debug, cur setting:%s", level_str)
    logging.basicConfig(filename=global_var.get_result_path() / 'events.log',
                        level=global_var.get_log_level(), filemode='w')


def main(**args):
    '''主程序'''
    # 读取配置文件
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option
    config.read('system_config.ini',encoding='utf-8')
    env_config = dict(config['EnvironmentSettings'])
    #设置全局变量
    miner_num = args.get('miner_num') or int(env_config['miner_num'])
    network_type = args.get('network_type') or env_config['network_type']
    global_var.__init__(args.get('result_path'))
    global_var.set_consensus_type(
        args.get('consensus_type') or env_config['consensus_type'])
    global_var.set_network_type(network_type)
    global_var.set_miner_num(miner_num)
    global_var.set_blocksize(
        args.get('blocksize') or int(env_config['blocksize']))
    global_var.set_show_fig(
        args.get('show_fig') or config.getboolean('EnvironmentSettings','show_fig'))
    global_var.set_compact_outputfile(
        config.getboolean('EnvironmentSettings','compact_outputfile')
        if not args.get('no_compact_outputfile') else False)
    
    # 配置日志
    config_log(env_config)
    
    # 设置PoW共识协议参数
    consensus_settings = dict(config['ConsensusSettings'])
    if global_var.get_consensus_type() == 'consensus.PoW':
        target = args.get('target') or consensus_settings['target']
        global_var.set_PoW_target(target)
        q_ave = args.get('q_ave') or int(consensus_settings['q_ave'])
        global_var.set_ave_q(q_ave)
        q_distr = args.get('q_distr') or consensus_settings['q_distr']
        if q_distr == 'rand':
            q_distr = get_random_q_gaussian(miner_num,q_ave)
        consensus_param = {'target':target, 'q_ave':q_ave, 'q_distr':q_distr}
    else:
        consensus_param = {}
        for key, value in consensus_settings.items():
            consensus_param[key] = args.get(key) or value

    # 设置网络参数
    network_param = {}
    # BoundedDelayNetwork
    if network_type == 'network.BoundedDelayNetwork':
        bdnet_settings = dict(config["BoundedDelayNetworkSettings"])
        network_param = {
            'rcvprob_start': (args.get('rcvprob_start') 
                              if args.get('rcvprob_start') is not None  
                              else float(bdnet_settings['rcvprob_start'])),
            'rcvprob_inc': (args.get('rcvprob_inc') 
                            if args.get('rcvprob_inc') is not None
                            else float(bdnet_settings['rcvprob_inc'])),
            'stat_prop_times': (args.get('stat_prop_times') or 
                                eval(bdnet_settings['stat_prop_times']))
        }
    # PropVecNetwork
    elif network_type == 'network.PropVecNetwork':
        pvnet_settings = dict(config["PropVecNetworkSettings"])
        network_param = {'prop_vector':(args.get('prop_vector') or 
                                        eval(pvnet_settings['prop_vector']))}
    # TopologyNetwork
    elif network_type == 'network.TopologyNetwork':
        net_setting = 'TopologyNetworkSettings'
        bool_params  = ['show_label', 'save_routing_graph', 'dynamic']
        float_params = ['ave_degree', 'bandwidth_honest', 'bandwidth_adv',
                        'outage_prob','avg_tp_change_interval','edge_add_prob',
                        'edge_remove_prob','max_allowed_partitions']
        for bparam in bool_params:
            network_param.update({bparam: args.get(bparam) or 
                                 config.getboolean(net_setting, bparam)})
        for fparam in float_params:
            network_param.update({fparam: args.get(fparam) or 
                                  config.getfloat(net_setting, fparam)})
        network_param.update({
            'init_mode': (args.get('init_mode') or 
                          config.get(net_setting, 'init_mode')),
            'stat_prop_times': (args.get('stat_prop_times') or 
                                eval(config.get(net_setting, 'stat_prop_times'))),
            'rand_mode': (args.get('rand_mode') or
                          config.get(net_setting, 'rand_mode'))
        })
    # AdHocNetwork
    elif network_type == 'network.AdHocNetwork':
        net_setting = 'AdHocNetworkSettings'
        bool_params  = []
        float_params = ['ave_degree', 'region_width', 'comm_range',
                        'move_variance','outage_prob'] # 'min_move', 'max_move'
        for bparam in bool_params:
            network_param.update({bparam: args.get(bparam) or 
                                 config.getboolean(net_setting, bparam)})
        for fparam in float_params:
            network_param.update({fparam: args.get(fparam) or 
                                  config.getfloat(net_setting, fparam)})
        network_param.update({
            'init_mode': (args.get('init_mode') or 
                          config.get(net_setting, 'init_mode')),
            'stat_prop_times': (args.get('stat_prop_times') or 
                                eval(config.get(net_setting, 'stat_prop_times')))
        })
        global_var.set_segmentsize(config.getfloat(net_setting, "segment_size"))

    # 设置attack参数
    attack_setting = dict(config['AttackSettings'])
    global_var.set_attack_execute_type(args.get('attack_type') or 
                                       attack_setting['attack_type'])
    attack_param = {
        'adver_num'    : (args.get('adver_num') if args.get('adver_num') is not None 
                          else int(attack_setting['adver_num'])),
        'attack_type'  : (args.get('attack_type') if args.get('attack_type') is not None
                          else attack_setting['attack_type']),
        'attack_arg'   : attack_setting.get('attack_arg') if attack_setting.get('attack_arg') is not None
                          else None,
        'adversary_ids': (args.get('adver_lists') if args.get('adver_lists') is not None
                          else eval(attack_setting.get('adver_lists') or 'None')),
    }


    # 生成环境
    genesis_blockheadextra = {}
    genesis_blockextra = {}

    Z = Environment(attack_param, consensus_param, network_param,
                    genesis_blockheadextra, genesis_blockextra)
    total_round = args.get('total_round') or int(env_config['total_round'])
    max_height = (args.get('total_height') or 
                  int(env_config.get('total_height') or 2**31 - 2))
    process_bar_type = (args.get('process_bar_type') 
                        or env_config.get('process_bar_type'))

    return run(Z,  total_round, max_height,process_bar_type)

def get_random_q_gaussian(miner_num,q_ave):
    '''
    随机设置各个节点的hash rate,满足均值为q_ave,方差为1的高斯分布
    且满足全网总算力为q_ave*miner_num
    '''
    # 生成均值为ave_q，方差为0.2*q_ave的高斯分布
    q_dist = np.random.normal(q_ave, 0.2*q_ave, miner_num)
    # 归一化到总和为total_q，并四舍五入为整数
    total_q = q_ave * miner_num
    q_dist = total_q / np.sum(q_dist) * q_dist
    q_dist = np.round(q_dist).astype(int)
    # 修正，如果和不为total_q就把差值分摊在最小值或最大值上
    if np.sum(q_dist) != total_q:
        diff = total_q - np.sum(q_dist)
        for _ in range(abs(diff)):
            sign_diff = np.sign(diff)
            idx = np.argmin(q_dist) if sign_diff > 0 else np.argmax(q_dist)
            q_dist[idx] += sign_diff
    return str(list(q_dist))


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    program_description = 'ChainXim, a blockchain simulator developed by XinLab\
, simulates and assesses blockchain system with various consensus protocols\
under different network conditions. Security evaluation of blockchain systems \
could be performed with attackers designed in the simulator'
    parser = argparse.ArgumentParser(description=program_description)
    # EnvironmentSettings
    env_setting = parser.add_argument_group('EnvironmentSettings','Settings for Environment')
    env_setting.add_argument('--process_bar_type', help='Set the style of process bar: round/height',type=str)
    env_setting.add_argument('--total_round', help='Total rounds before simulation stops.', type=int)
    env_setting.add_argument('--total_height', help='Total block height generated before simulation stops.', type=int)
    env_setting.add_argument('--miner_num', help='The total miner number in the network.', type=int)
    env_setting.add_argument('--consensus_type',help='The consensus class imported during simulation',type=str)
    env_setting.add_argument('--network_type',help='The network class imported during simulation',type=str)
    env_setting.add_argument('--blocksize', help='The size of each block in MB.',type=float)
    env_setting.add_argument('--show_fig', help='Show figures during simulation.',action='store_true')
    env_setting.add_argument('--no_compact_outputfile', action='store_true',
                             help='Simplify log and result outputs to reduce disk space consumption. True by default.')
    # ConsensusSettings
    consensus_setting = parser.add_argument_group('ConsensusSettings', 'Settings for Consensus Protocol')
    consensus_setting.add_argument('--q_ave', help='The average number of hash trials in a round.',type=int)
    consensus_setting.add_argument('--q_distr', help='distribution of hash rate across all miners.\
                        \'equal\': all miners have equal hash rate;\
                        \'rand\': q satisfies gaussion distribution.',type=str)
    consensus_setting.add_argument('--difficulty', help='The number of zero prefix of valid block hash.\
                    A metric for Proof of Work difficulty.',type=int)
    # AttackModeSettings
    attack_setting = parser.add_argument_group('AttackModeSettings','Settings for Attack')
    attack_setting.add_argument('-t',help='The total number of attackers. If t non-zero and adversary_ids not specified, then attackers are randomly selected.',type=int)
    attack_setting.add_argument('--attack_execute_type', help='The name of attack type defined in attack mode.',type=str)
    # BoundedDelayNetworkSettings
    bound_setting = parser.add_argument_group('BoundedDelayNetworkSettings','Settings for BoundedDelayNetwork')
    bound_setting.add_argument('--rcvprob_start', help='Initial receive probability when a block access network.',type=float)
    bound_setting.add_argument('--rcvprob_inc',help='Increment of rreceive probability per round.', type=float)
    # TopologyNetworkSettings
    topology_setting = parser.add_argument_group('TopologyNetworkSettings','Settings for TopologyNetwork')
    gen_net_approach_help_text = '''Options:coo/adj/rand.
    coo: load adjecent matrix from network/topolpgy_coo.csv in COOrdinate format.
    adj: load adjecent matrix from network/topolpgy.csv.
    rand: randomly generate a network.'''
    topology_setting.add_argument('--gen_net_approach',help=gen_net_approach_help_text,type=str)
    topology_setting.add_argument('--show_label',help='Show edge labels on network and routing graph.',
                                  action='store_true')
    topology_setting.add_argument('--save_routing_graph',help='Genarate routing graph at the end of simulation or not.',
                                  action='store_true')
    rand_mode_help_text = '''Options:homogeneous/binomial.
    homogeneous: try to keep the degree of each node the same.
    binomial: set up edges with probability ave_degree/(miner_num-1). '''
    topology_setting.add_argument('--rand_mode',help=rand_mode_help_text,type=str)
    topology_setting.add_argument('--ave_degree',help='Set the average degree of the network.',type=float)
    topology_setting.add_argument('--bandwidth_honest',
                                  help='Set bandwidth between honest miners and between the honest and adversaries(MB/round)',
                                  type=float)
    topology_setting.add_argument('--bandwidth_adv',help='Set bandwidth between adversaries(MB/round)')
    topology_setting.add_argument('--outage_prob',help='The outage probability of each link.',type=float)
    topology_setting.add_argument('--dynamic',help='Whether the network topology can dynamically change.',action='store_true')
    parser.add_argument('--result_path',help='The path to output results', type=str)

    args = vars(parser.parse_args())
    args['result_path'] = args['result_path'] and Path(args['result_path'])
    if difficulty := args.get('difficulty'):
        target_bin = int('F'*64, 16) >> difficulty
        args['target'] = f"{target_bin:0>64X}"
    else:
        args['target'] = None

    main(**args)
