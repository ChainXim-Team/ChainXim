from Environment import Environment
import time
import logging
import global_var
import configparser


def get_time(f):
    def inner(*arg, **kwarg):
        s_time = time.time()
        res = f(*arg, **kwarg)
        e_time = time.time()
        print('耗时：{}秒'.format(e_time - s_time))
        return res
    return inner

# 读取配置文件
config = configparser.ConfigParser()
config.optionxform = lambda option: option
config.read('system_config.ini',encoding='utf-8')
environ_settings = dict(config['EnvironmentSettings'])

# 设置全局变量
global_var.__init__()
global_var.set_consensus_type(environ_settings['consensus_type'])
global_var.set_network_type(environ_settings['network_type'])
global_var.set_miner_num(int(environ_settings['miner_num']))
global_var.set_ave_q(int(environ_settings['q_ave']))
global_var.set_blocksize(int(environ_settings['blocksize']))
global_var.set_show_fig(False)
global_var.save_configuration()


# 配置日志文件
logging.basicConfig(filename=global_var.get_result_path() / 'events.log',
                    level=global_var.get_log_level(), filemode='w')

# 设置网络参数
network_param = {}
if environ_settings['network_type'] == 'network.TopologyNetwork':
    net_setting = 'TopologyNetworkSettings'
    bool_params = ['show_label', 'save_routing_graph']
    float_params = ['ave_degree', 'bandwidth_honest', 'bandwidth_adv']
    for bparam in bool_params:
        network_param.update({bparam: config.getboolean(net_setting, bparam)})
    for fparam in float_params:
        network_param.update({fparam: config.getfloat(net_setting, fparam)})
    network_param.update({'TTL':config.getint(net_setting, 'TTL'),
            'gen_net_approach': config.get(net_setting, 'gen_net_approach')})
elif environ_settings['network_type'] == 'network.BoundedDelayNetwork':
    net_setting = 'BoundedDelayNetworkSettings'
    network_param = {k:float(v) for k,v in dict(config[net_setting]).items()}

# 设置attack参数
attack_setting = dict(config['AttackModeSettings'])
adversary_ids = eval(attack_setting['adversary_ids'])
global_var.set_attack_excute_type(attack_setting['attack_excute_type'])
t = int(attack_setting['t'])

# 生成环境
q_ave = int(environ_settings['q_ave'])
q_distr = environ_settings['q_distr']
target = environ_settings['target']
genesis_blockextra = {}
Z = Environment(t, q_ave, q_distr, target, adversary_ids, 
                        network_param, genesis_blockextra)

@get_time
def run():
    Z.exec(int(environ_settings['total_round']))

    Z.view()

run()
