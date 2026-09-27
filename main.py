
import random

import configparser
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from typing import Optional
import global_var
from environment import Environment


# ---------------------------------------------------------------------------
# Pre-mining DoubleSpending batch test configuration
#
# Set ``enabled`` to True, edit the parameter sets below, and run:
#     python main.py
# Each parameter set writes to a different TXT file under ``output_dir``.
# ``max_workers`` is the maximum number of main.py processes running at once.
# ---------------------------------------------------------------------------
PREMINING_DOUBLE_SPENDING_TEST = {
    'enabled': True,
    'max_workers': 4,
    'output_dir': 'Results/premining_parallel',
    'config': 'system_config.ini',
    'keep_run_results': False,
    'defaults': {
        'trials': 5000,
        'seed': 10000,
        # Keep the honest side fixed. miner_num is calculated automatically
        # as honest_num + adver_num for every parameter set.
        'honest_num': 10,
        'start_height': 1,
        'attack_height': 30,
        'Ng': 20,
        'N': 3,
        'total_round': 500000,
    },
    'parameter_sets': [
        {
            'adver_num': 4,
        },
        {
            'adver_num': 5,
        },
        {
            'adver_num': 6,
        },
        {
            'adver_num': 7,
        },
    ],
}


def get_time(f):
    def inner(*arg, **kwarg):
        s_time = time.time()
        res = f(*arg, **kwarg)
        e_time = time.time()
        print('耗时：{}秒'.format(e_time - s_time))
        return res
    return inner

@get_time
def run_with_timing(Z:Environment, stop_condition: dict,
        process_bar_type, post_verification:bool, quantile: float):
    Z.exec(stop_condition, process_bar_type, post_verification)
    # return Z.view_and_write(quantile)
    return Z.view(quantile)

def run(env: Environment, stop_condition: dict,
        process_bar_type, post_verification:bool, quantile: float):
    """运行环境"""
    env.exec(stop_condition, process_bar_type, post_verification)
    return env.view(quantile)

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
                        level=global_var.get_log_level(), filemode='w', force=True)

def parse_config(**args):
    '''配置环境'''
    # 读取配置文件
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option
    config.read(args.get('config'),encoding='utf-8')
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
        args.get('blocksize') or float(env_config['blocksize']))
    global_var.set_show_fig(
        args.get('show_fig') or config.getboolean('EnvironmentSettings','show_fig'))
    global_var.set_compact_outputfile(
        config.getboolean('EnvironmentSettings','compact_outputfile')
        if not args.get('no_compact_outputfile') else False)
    global_var.set_common_prefix_enable(
        config.getboolean('EnvironmentSettings','common_prefix_enable'))
    
    # 配置日志
    config_log(env_config)
    
    # 设置PoW共识协议参数
    consensus_settings = dict(config['ConsensusSettings'])
    if global_var.get_consensus_type() in ['consensus.PoW', 'consensus.VirtualPoW', 'consensus.SolidPoW', 'consensus.PoS']:
        q_ave = args.get('q_ave') or float(consensus_settings['q_ave'])
        global_var.set_ave_q(q_ave)
        q_distr = args.get('q_distr') or consensus_settings['q_distr']
        if q_distr == 'rand':
            q_distr = get_random_q_gaussian(miner_num,q_ave)
        elif isinstance(q_distr, str) and q_distr != 'equal':
            q_distr = eval(q_distr)
        assert q_distr == 'equal' or isinstance(q_distr, list) and len(q_distr) == miner_num, \
               "q_distr should be 'equal' or a list with length equal to miner_num"
        
        average_block_time = args.get('average_block_time') or float(consensus_settings['average_block_time'])
        if average_block_time == 0 or global_var.get_consensus_type() == 'consensus.PoS':
            target = args.get('target') or consensus_settings['target']
            global_var.set_PoW_target(target)
        else:
            if isinstance(q_distr, str) and q_distr == 'equal':
                target =  f"{2**256//int(miner_num*q_ave*average_block_time):064x}"
            else:
                target = f"{2**256//int(sum(q_distr)*average_block_time):064x}"
            global_var.set_PoW_target(target)
        consensus_param = {'target':target, 'q_ave':q_ave, 'q_distr':q_distr, 'N': args.get('N') or int(consensus_settings['N'])}
        precompute_threshold = consensus_settings.get('precompute_threshold')
        if precompute_threshold is not None and global_var.get_consensus_type() == 'consensus.PoS':
            consensus_param.update({'precompute_threshold': int(precompute_threshold)})
    else:
        consensus_param = {}
        for key, value in consensus_settings.items():
            consensus_param[key] = args.get(key) or value
        if 'N' in consensus_param:
            consensus_param['N'] = int(consensus_param['N'])

    # 设置网络参数
    network_param = {}
    # StochPropNetwork
    if network_type == 'network.StochPropNetwork':
        bdnet_settings = dict(config["StochPropNetworkSettings"])
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
    # DeterPropNetwork
    elif network_type == 'network.DeterPropNetwork':
        pvnet_settings = dict(config["DeterPropNetworkSettings"])
        network_param = {'prop_vector':(args.get('prop_vector') or 
                                        eval(pvnet_settings['prop_vector']))}
    # TopologyNetwork
    elif network_type == 'network.TopologyNetwork':
        net_setting = 'TopologyNetworkSettings'
        bool_params  = ['show_label', 'save_routing_graph', 'save_routing_history',
                        'dynamic','enable_resume_transfer']
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
            'topology_path': (args.get('topology_path') or 
                              config.get(net_setting, 'topology_path', fallback=None)),
            'stat_prop_times': (args.get('stat_prop_times') or 
                                eval(config.get(net_setting, 'stat_prop_times'))),
            'rand_mode': (args.get('rand_mode') or
                          config.get(net_setting, 'rand_mode'))
        })
    # AdHocNetwork
    elif network_type == 'network.AdHocNetwork':
        net_setting = 'AdHocNetworkSettings'
        bool_params  = ['enable_large_scale_fading']
        float_params = ['ave_degree', 'region_width', 'comm_range','move_variance',
                        'outage_prob','segment_size','bandwidth_max'] # 'min_move', 'max_move'
        for bparam in bool_params:
            network_param.update({bparam: args.get(bparam) or 
                                 config.getboolean(net_setting, bparam)})
        for fparam in float_params:
            network_param.update({fparam: args.get(fparam) or 
                                  config.getfloat(net_setting, fparam)})
        network_param.update({
            'init_mode': (args.get('init_mode') or config.get(net_setting, 'init_mode')),
            'stat_prop_times': (args.get('stat_prop_times') or eval(config.get(net_setting, 'stat_prop_times'))),
            'path_loss_level': (args.get('path_loss_level') or config.get(net_setting, 'path_loss_level')),
        })
        # global_var.set_segmentsize(config.getfloat(net_setting, "segment_size"))

    # 设置attack参数
    attack_setting = dict(config['AttackSettings'])
    global_var.set_attack_execute_type(args.get('attack_type') or attack_setting.get('attack_type', 'HonestMining'))
    attack_arg = eval(attack_setting.get('attack_arg')) if attack_setting.get('attack_arg') is not None else {}
    if attack_arg is None:
        attack_arg = {}
    if args.get('premining_enabled') is not None:
        attack_arg['premining_enabled'] = args.get('premining_enabled')
    for key in ('premining_end_condition', 'premining_target_height',
                'premining_target_round', 'premining_start_height'):
        if args.get(key) is not None:
            attack_arg[key] = args.get(key)

    attack_param = {
        'adver_num'    : (args.get('adver_num') if args.get('adver_num') is not None 
                          else int(attack_setting['adver_num'])),
        'attack_type'  : (args.get('attack_type') if args.get('attack_type') is not None
                          else attack_setting.get('attack_type', 'HonestMining')),
        'attack_arg'   : attack_arg,
        'adversary_ids': (args.get('adver_lists') if args.get('adver_lists') is not None
                          else eval(attack_setting.get('adver_lists') or 'None')),
    }
    attack_param['attack_arg'].update(args.get('attack_arg', {}))
    attack_param['attack_arg'].update({'N': consensus_param.get('N', 1)})

    # 设置dataitem相关的配置
    dataitem_setting = dict(config['DataItemSettings'])
    dataitem_param = {
        'dataitem_enable': args.get('dataitem_enable') or config.getboolean('DataItemSettings','dataitem_enable'),
        'max_block_capacity': (args.get('max_block_capacity') or 
                               int(dataitem_setting['max_block_capacity'])),
        'dataitem_size': (args.get('dataitem_size') or 
                          int(dataitem_setting['dataitem_size'])),
        'dataitem_input_interval': (args.get('dataitem_input_interval') or 
                                    int(dataitem_setting['dataitem_input_interval'])),
    }

    # 生成环境
    genesis_blockheadextra = args.get('genesis_blockheadextra') or {}
    genesis_blockextra = args.get('genesis_blockextra') or {}

    Z = Environment(attack_param, consensus_param, network_param,
                    genesis_blockheadextra, genesis_blockextra, dataitem_param)
    stop_condition = {
        'total_round': args.get('total_round') or int(env_config['total_round']),
        'max_height': (args.get('total_height') or 
                       int(env_config.get('total_height') or 2**31 - 2))
    }
    process_bar_type = (args.get('process_bar_type') 
                        or env_config.get('process_bar_type'))

    runtime_configurations = {
        'stop_condition': stop_condition,
        'process_bar_type': process_bar_type,
        'post_verification': args.get('disable_post_verification'),
        'quantile': config.getfloat('EnvironmentSettings','consensus_miner_quantile')
    }
    return Z, runtime_configurations

def main(**args):
    '''主程序'''
    env, runtime_configurations = parse_config(**args)
    if args.get('no_save_results'):
        stats = run(env, **runtime_configurations)
    else:
        stats = run_with_timing(env, **runtime_configurations)

    # Give subprocess-based experiments a stable, machine-readable result.
    # The regular evaluation output is intentionally left unchanged.
    if result_summary := args.get('result_summary'):
        result_summary = Path(result_summary)
        result_summary.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            'attack_success': int(stats.get('attack_success', 0)),
            'attack_fail': int(stats.get('attack_fail', 0)),
            'attack_times': int(stats.get('Attack times', 0)),
            'total_round': int(stats.get('total_round', 0)),
            'premining_end_lead': stats.get('Premining End Lead'),
        }
        with result_summary.open('w', encoding='utf-8') as result_file:
            json.dump(summary, result_file, ensure_ascii=False, indent=2)
            result_file.write('\n')
    return stats
    
def experiment(trail_num, seed:Optional[int] = None, **args):
    '''
    重复运行仿真达到停止条件后就停止，然后计算双花攻击成功率
    trail_num: 仿真重复次数
    '''
    if trail_num <= 0:
        raise ValueError('trail_num must be a positive integer')

    seed = 0 if seed is None else seed * trail_num
    result_path = args.get('result_path')
    metric_sums = {}
    metric_counts = {}
    import random
    import numpy as np

    for trail_idx in range(trail_num):
        # 随机化创世区块，保证仿真独立性
        cur_seed = seed + trail_idx
        args['genesis_blockheadextra'] = {'prehash': cur_seed.to_bytes(32, 'little'), 'content': cur_seed.to_bytes(4, 'little')}
        if result_path:
            args['result_path'] = result_path / f'trail_{trail_idx}' # 每次仿真结果输出到不同的文件夹，避免文件被覆盖

        random.seed(cur_seed)
        np.random.seed(cur_seed)

        env, runtime_configurations = parse_config(**args)
        runtime_configurations['stop_condition'].update({'max_attack_attempts': 1}) # 攻击一次即停止仿真
        stats = run(env, **runtime_configurations)

        for key, value in stats.items():
            # 只处理可平均的数值类型
            if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
                metric_sums[key] = metric_sums.get(key, 0.0) + float(value)
                metric_counts[key] = metric_counts.get(key, 0) + 1
            else:
                # TODO: 处理 list/ndarray/dict 等复杂类型的聚合逻辑
                continue

    averaged_stats = {
        key: (metric_sums[key] / metric_counts[key])
        for key in metric_sums
        if metric_counts.get(key, 0) > 0
    }

    return averaged_stats


def _append_premining_record(record_file: Path, line: str):
    """Append and close immediately so completed trials survive interruption."""
    with record_file.open('a', encoding='utf-8', newline='\n') as output:
        output.write(line + '\n')


def _safe_parameter_name(name: str) -> str:
    safe_name = re.sub(r'[^0-9A-Za-z._-]+', '_', str(name)).strip('._')
    return safe_name or 'premining_case'


def _read_single_attack_summary(summary_file: Path) -> dict:
    try:
        with summary_file.open('r', encoding='utf-8') as input_file:
            summary = json.load(input_file)
        success = int(summary['attack_success'])
        failure = int(summary['attack_fail'])
        attack_times = int(summary['attack_times'])
        premining_end_lead = int(summary['premining_end_lead'])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Cannot read single-attack result: {summary_file}') from exc

    if attack_times != 1 or success + failure != 1:
        raise RuntimeError(
            'Simulation ended before exactly one attack completed '
            f'(success={success}, failure={failure}, attack_times={attack_times})'
        )
    summary['outcome'] = 'SUCCESS' if success == 1 else 'FAILURE'
    summary['premining_end_lead'] = premining_end_lead
    return summary


def _run_premining_trial(job: dict) -> dict:
    """Start one fresh main.py process and return its single attack outcome."""
    run_dir = Path(job['run_dir'])
    run_dir.mkdir(parents=True, exist_ok=False)
    case_file = run_dir / 'case.json'
    summary_file = run_dir / 'single_attack_result.json'
    log_file = run_dir / 'main.log'

    main_args = dict(job['main_args'])
    main_args.update({
        'result_path': str(run_dir),
        'result_summary': str(summary_file),
        'no_save_results': True,
        'seed': job['seed'],
    })
    with case_file.open('w', encoding='utf-8', newline='\n') as output:
        json.dump(main_args, output, ensure_ascii=False, indent=2)
        output.write('\n')

    command = [sys.executable, str(Path(__file__).resolve()),
               '--attack-case-json', str(case_file)]
    process_env = os.environ.copy()
    process_env['PYTHONIOENCODING'] = 'utf-8'
    with log_file.open('wb') as log_output:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parent,
            stdout=log_output,
            stderr=subprocess.STDOUT,
            env=process_env,
            check=False,
        )
    if completed.returncode != 0:
        try:
            log_tail = '\n'.join(
                log_file.read_text(encoding='utf-8', errors='replace').splitlines()[-30:]
            )
        except OSError:
            log_tail = '(simulation log unavailable)'
        raise RuntimeError(
            f"main.py exited with code {completed.returncode}:\n{log_tail}"
        )

    result = _read_single_attack_summary(summary_file)
    result.update({
        'case_name': job['case_name'],
        'trial': job['trial'],
        'seed': job['seed'],
    })
    return result


def _prepare_premining_case(raw_case: dict, defaults: dict,
                            output_dir: Path, default_config: Path) -> dict:
    case = dict(defaults)
    case.update(raw_case)

    trials = int(case.pop('trials', case.pop('runs', 1)))
    if trials <= 0:
        raise ValueError('trials must be a positive integer')

    attack_height = case.pop(
        'attack_height', case.get('premining_target_height')
    )
    if attack_height is None:
        raise ValueError('Each parameter set requires attack_height')
    attack_height = int(attack_height)
    start_height = int(case.pop(
        'start_height', case.get('premining_start_height', 1)
    ))
    if attack_height < 0 or start_height < 0 or start_height > attack_height:
        raise ValueError(
            f'Invalid height range: start_height={start_height}, '
            f'attack_height={attack_height}'
        )

    attack_arg = dict(case.pop('attack_arg', {}) or {})
    ng = case.pop('Ng', case.pop('ng', None))
    if ng is not None:
        attack_arg['Ng'] = int(ng)

    difficulty = case.pop('difficulty', None)
    if difficulty is not None:
        difficulty = int(difficulty)
        if difficulty <= 0:
            raise ValueError('difficulty must be a positive integer')
        target_bin = int('F' * 64, 16) >> difficulty
        case['target'] = f'{target_bin:0>64X}'

    seed = int(case.pop('seed', 0))
    if seed < 0:
        raise ValueError('seed must be a non-negative integer')

    case.pop('name', None)
    case.pop('record_file', None)
    if case.get('adver_num') is None:
        raise ValueError('Each parameter set requires adver_num')
    adver_num = int(case['adver_num'])
    if adver_num <= 0:
        raise ValueError('adver_num must be a positive integer')
    case['adver_num'] = adver_num

    # ``miner_num`` in ChainXim means total miners.  ``honest_num`` is a
    # batch-test convenience option that keeps the honest side fixed while
    # the attacker count changes.
    honest_num = case.pop('honest_num', None)
    if honest_num is not None:
        honest_num = int(honest_num)
        if honest_num <= 0:
            raise ValueError('honest_num must be a positive integer')
        case['miner_num'] = honest_num + adver_num
    elif case.get('miner_num') is not None:
        case['miner_num'] = int(case['miner_num'])
        honest_num = case['miner_num'] - adver_num
        if honest_num <= 0:
            raise ValueError('miner_num must be greater than adver_num')

    case_name = f'adver_{adver_num}'
    record_file = (output_dir / f'adver_{adver_num}.txt').resolve()

    config_value = Path(case.get('config') or default_config)
    if not config_value.is_absolute():
        config_value = Path.cwd() / config_value
    config_value = config_value.resolve()
    if not config_value.is_file():
        raise FileNotFoundError(f'Configuration file not found: {config_value}')

    case.update({
        'config': str(config_value),
        'attack_type': 'DoubleSpending',
        'attack_arg': attack_arg,
        'premining_enabled': True,
        'premining_end_condition': 'height',
        'premining_target_height': attack_height,
        'premining_start_height': start_height,
    })
    case.pop('result_path', None)
    case.pop('result_summary', None)
    case.pop('no_save_results', None)

    return {
        'name': case_name,
        'trials': trials,
        'seed': seed,
        'honest_num': honest_num,
        'adver_num': adver_num,
        'record_file': record_file,
        'main_args': case,
    }


def premining_double_spending_attack(parameter_sets: list[dict], *,
        max_workers: int = 1, output_dir='Results/premining_double_spending',
        default_config='system_config.ini', defaults: Optional[dict] = None,
        keep_run_results: bool = False) -> dict:
    """Run fixed-height pre-mining DoubleSpending parameter sets in parallel.

    Each trial starts a fresh ``main.py`` process and stops after exactly one
    completed attack. Every parameter set owns one TXT record file. Results
    are appended as soon as its trials finish, while other trials continue.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not parameter_sets:
        raise ValueError('parameter_sets must contain at least one case')
    max_workers = int(max_workers)
    if max_workers <= 0:
        raise ValueError('max_workers must be a positive integer')

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    default_config = Path(default_config)
    defaults = dict(defaults or {})
    prepared_cases = [
        _prepare_premining_case(item, defaults, output_dir, default_config)
        for item in parameter_sets
    ]

    names = [item['name'] for item in prepared_cases]
    if len(names) != len(set(names)):
        raise ValueError('Every parameter set must have a unique name')
    record_files = [item['record_file'] for item in prepared_cases]
    if len(record_files) != len(set(record_files)):
        raise ValueError('Every parameter set must use a different record_file')

    started_at = time.strftime('%Y-%m-%d %H:%M:%S')
    states = {}
    for item in prepared_cases:
        item['record_file'].parent.mkdir(parents=True, exist_ok=True)
        display_args = dict(item['main_args'])
        item['record_file'].write_text(
            'Premining DoubleSpending attack statistics\n'
            f"parameter_set={item['name']}\n"
            f"honest_miners={item['honest_num']}\n"
            f"adversary_miners={item['adver_num']}\n"
            f'started_at={started_at}\n'
            f"trials_requested={item['trials']}\n"
            f"parameters={json.dumps(display_args, ensure_ascii=False, sort_keys=True)}\n"
            '\n'
            'trial seed result premining_end_lead successes failures errors completed success_rate\n',
            encoding='utf-8', newline='\n'
        )
        states[item['name']] = {
            'successes': 0,
            'failures': 0,
            'errors': 0,
            'lead_counts': {},
            'remaining': item['trials'],
            'record_file': item['record_file'],
        }

    temp_context = None
    if keep_run_results:
        run_root = output_dir / ('run_data_' + time.strftime('%Y%m%d-%H%M%S'))
        run_root.mkdir(parents=True, exist_ok=False)
    else:
        temp_context = tempfile.TemporaryDirectory(prefix='chainxim-premining-')
        run_root = Path(temp_context.name)

    future_jobs = {}
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for case in prepared_cases:
                for trial in range(1, case['trials'] + 1):
                    job = {
                        'case_name': case['name'],
                        'trial': trial,
                        'seed': case['seed'] + trial - 1,
                        'main_args': case['main_args'],
                        'run_dir': str(
                            run_root / _safe_parameter_name(case['name']) /
                            f'trial_{trial:06d}'
                        ),
                    }
                    future_jobs[executor.submit(_run_premining_trial, job)] = job

            for future in as_completed(future_jobs):
                job = future_jobs[future]
                state = states[job['case_name']]
                try:
                    result = future.result()
                    outcome = result['outcome']
                    if outcome == 'SUCCESS':
                        state['successes'] += 1
                    else:
                        state['failures'] += 1
                    end_lead = int(result['premining_end_lead'])
                    state['lead_counts'][end_lead] = (
                        state['lead_counts'].get(end_lead, 0) + 1
                    )
                    error_text = ''
                except Exception as exc:
                    outcome = 'ERROR'
                    end_lead = None
                    state['errors'] += 1
                    error_text = str(exc).replace('\r', ' ').replace('\n', ' | ')

                state['remaining'] -= 1
                completed_attacks = state['successes'] + state['failures']
                success_rate = (
                    state['successes'] / completed_attacks
                    if completed_attacks else 0.0
                )
                _append_premining_record(
                    state['record_file'],
                    f"{job['trial']} {job['seed']} {outcome} "
                    f"{end_lead if end_lead is not None else '-'} "
                    f"{state['successes']} {state['failures']} {state['errors']} "
                    f'{completed_attacks} {success_rate:.6%}'
                    + (f' error={error_text}' if error_text else '')
                )
                print(
                    f"[{job['case_name']}] trial {job['trial']} {outcome}; "
                    f'success rate: {success_rate:.2%}',
                    flush=True,
                )

                if state['remaining'] == 0:
                    _append_premining_record(state['record_file'], '')
                    _append_premining_record(state['record_file'], 'Final summary')
                    _append_premining_record(
                        state['record_file'],
                        f"successful_attacks={state['successes']}"
                    )
                    _append_premining_record(
                        state['record_file'],
                        f"failed_attacks={state['failures']}"
                    )
                    _append_premining_record(
                        state['record_file'], f"errors={state['errors']}"
                    )
                    _append_premining_record(
                        state['record_file'],
                        f'total_attacks={completed_attacks}'
                    )
                    _append_premining_record(
                        state['record_file'],
                        f'success_rate={success_rate:.6%}'
                    )
                    _append_premining_record(state['record_file'], '')
                    _append_premining_record(
                        state['record_file'],
                        'Premining end lead probability'
                    )
                    _append_premining_record(
                        state['record_file'], 'lead_blocks count probability'
                    )
                    for lead, count in sorted(state['lead_counts'].items()):
                        probability = count / completed_attacks
                        _append_premining_record(
                            state['record_file'],
                            f'{lead} {count} {probability:.6%}'
                        )
    finally:
        if temp_context is not None:
            temp_context.cleanup()

    summaries = {
        name: {
            'successes': state['successes'],
            'failures': state['failures'],
            'errors': state['errors'],
            'success_rate': (
                state['successes'] / (state['successes'] + state['failures'])
                if state['successes'] + state['failures'] else 0.0
            ),
            'premining_end_lead_probability': {
                lead: count / (state['successes'] + state['failures'])
                for lead, count in sorted(state['lead_counts'].items())
            },
            'record_file': str(state['record_file']),
        }
        for name, state in states.items()
    }
    if any(item['errors'] for item in summaries.values()):
        raise RuntimeError(
            'One or more trials failed; see the corresponding TXT record files'
        )
    return summaries


def get_random_q_gaussian(miner_num,q_ave):
    '''
    随机设置各个节点的hash rate,满足均值为q_ave的高斯分布
    且满足全网总算力为q_ave*miner_num
    '''
    # 生成均值为ave_q，方差为0.2*q_ave的高斯分布
    q_dist = np.random.normal(q_ave, 0.2*q_ave, miner_num)
    # 归一化到总和为total_q，并四舍五入为整数
    total_q = int(round(q_ave * miner_num))
    q_dist = total_q / np.sum(q_dist) * q_dist
    q_dist = np.round(q_dist).astype(int)
    # 修正，如果和不为total_q就把差值分摊在最小值或最大值上
    diff = int(total_q - np.sum(q_dist))
    if diff != 0:
        sign_diff = 1 if diff > 0 else -1
        for _ in range(abs(diff)):
            idx = np.argmin(q_dist) if sign_diff > 0 else np.argmax(q_dist)
            q_dist[idx] += sign_diff
    return q_dist.tolist()


if __name__ == '__main__':
    import argparse
    program_description = 'ChainXim, a blockchain simulator developed by XinLab\
, simulates and assesses blockchain system with various consensus protocols \
under different network conditions. Security evaluation of blockchain systems \
could be performed with attackers designed in the simulator'
    parser = argparse.ArgumentParser(description=program_description)
    parser.add_argument('--config', '-c', help='The path to the config file.', type=str, default='system_config.ini')
    # EnvironmentSettings
    env_setting = parser.add_argument_group('EnvironmentSettings','Settings for Environment')
    env_setting.add_argument('--process_bar_type', help='Set the style of process bar: round/height',type=str)
    env_setting.add_argument('--total_round', help='Total rounds before simulation stops.', type=int)
    env_setting.add_argument('--total_height', help='Total block height generated before simulation stops.', type=int)
    env_setting.add_argument('--miner_num', help='The total miner number in the network.', type=int)
    env_setting.add_argument('--consensus_type',help='The consensus class imported during simulation',type=str)
    env_setting.add_argument('--network_type',help='The network class imported during simulation',type=str)
    env_setting.add_argument('--blocksize', help='The size of each block in MB. Only effective when dataitem_enable=False and network_type is TopologyNetwork or AdhocNetwork.',type=float)
    env_setting.add_argument('--show_fig', help='Show figures during simulation.',action='store_true')
    env_setting.add_argument('--no_compact_outputfile', action='store_true',
                             help='Simplify log and result outputs to reduce disk space consumption. Use no_compact_outputfile to disable this feature.')
    # ConsensusSettings
    consensus_setting = parser.add_argument_group('ConsensusSettings', 'Settings for Consensus Protocol')
    consensus_setting.add_argument('--q_ave', help='The average number of hash trials in a round.',type=float)
    consensus_setting.add_argument('--q_distr', help='distribution of hash rate across all miners.\
                        \'equal\': all miners have equal hash rate;\
                        \'rand\': q satisfies gaussion distribution.',type=str)
    consensus_setting.add_argument('-N', help='The number of block confirmations required for the transactoins in a block to be considered valid. Used to calculate attack success rate.', type=int)
    # Ensure only one of difficulty and average_block_time can be set
    group = consensus_setting.add_mutually_exclusive_group()
    group.add_argument('--difficulty', help='The number of zero prefix of valid block hash.\
                    A metric for Proof of Work difficulty.', type=int)
    group.add_argument('--average_block_time', help='The average time interval between two blocks.\
                    If average_block_time=0, then target is set as the difficulty.', type=float)
    # AttackModeSettings
    attack_setting = parser.add_argument_group('AttackModeSettings','Settings for Attack')
    attack_setting.add_argument('--adver_num',help='The total number of attackers. If adver_num is non-zero and adversary_ids not specified, then attackers are randomly selected.',type=int)
    attack_setting.add_argument('--adver_lists', help='Specify id of adversaries. If adversary_ids is set, `adver_num` will not take effect.', type=str)
    attack_setting.add_argument('--attack_type', help='The name of attack type defined in attack mode.',type=str)
    attack_setting.add_argument('-Ng', help='Parameter Ng for DoubleSpending', type=int)
    attack_setting.add_argument('--eclipse_target', help='The target miner id for eclipse attack.', type=str)
    premining_toggle = attack_setting.add_mutually_exclusive_group()
    premining_toggle.add_argument('--premining', dest='premining_enabled',
                                   action='store_true', default=None,
                                   help='Enable pre-mining before DoubleSpending.')
    premining_toggle.add_argument('--no-premining', dest='premining_enabled',
                                   action='store_false', default=None,
                                   help='Disable pre-mining before DoubleSpending.')
    attack_setting.add_argument('--premining-end-condition', dest='premining_end_condition',
                                choices=('height', 'round'),
                                help='End pre-mining by honest height or simulation round.')
    attack_setting.add_argument('--premining-target-height', dest='premining_target_height',
                                type=int, help='Honest block height targeted by height-mode pre-mining.')
    attack_setting.add_argument('--premining-target-round', dest='premining_target_round',
                                type=int, help='Round at which round-mode pre-mining ends.')
    attack_setting.add_argument('--premining-start-height', dest='premining_start_height',
                                type=int, help='Honest height at which private pre-mining starts.')
    # StochPropNetworkSettings
    stoch_setting = parser.add_argument_group('StochPropNetworkSettings','Settings for StochPropNetwork')
    stoch_setting.add_argument('--rcvprob_start', help='Initial receive probability when a block access network.',type=float)
    stoch_setting.add_argument('--rcvprob_inc',help='Increment of rreceive probability per round.', type=float)
    # CommonSettings for both TopologyNetwork and AdhocNetwork
    common_setting = parser.add_argument_group('CommonSettings', 'Common settings for both TopologyNetwork and AdhocNetwork')
    init_mode_help_text = ''' Options:coo/adj/rand.
    coo: load adjecent matrix in COOrdinate format.
    adj: load adjecent matrix.
    rand: randomly generate a network. AdhocNetwork only support this.'''
    common_setting.add_argument('--init_mode', help='Initialization mode for the network.' + init_mode_help_text, type=str)
    common_setting.add_argument('--topology_path', help='The relative path to the topology file in a csv format specified by init_mode.', type=str)
    common_setting.add_argument('--ave_degree', help='Set the average degree of the network.', type=float)
    common_setting.add_argument('--outage_prob', help='The outage probability of each link.', type=float)
    # TopologyNetworkSettings
    topology_setting = parser.add_argument_group('TopologyNetworkSettings', 'Settings for TopologyNetwork')
    topology_setting.add_argument('--show_label', help='Show edge labels on network and routing graph.', action='store_true')
    topology_setting.add_argument('--save_routing_graph', help='Generate routing graph at the end of simulation or not.', action='store_true')
    rand_mode_help_text = '''Options:homogeneous/binomial.
    homogeneous: try to keep the degree of each node the same.
    binomial: set up edges with probability ave_degree/(miner_num-1). '''
    topology_setting.add_argument('--rand_mode', help=rand_mode_help_text, type=str)
    topology_setting.add_argument('--bandwidth_honest', help='Set bandwidth between honest miners and between the honest and adversaries(MB/round)', type=float)
    topology_setting.add_argument('--bandwidth_adv', help='Set bandwidth between adversaries(MB/round)', type=float)
    topology_setting.add_argument('--dynamic', help='Whether the network topology can dynamically change.', action='store_true')
    topology_setting.add_argument('--avg_tp_change_interval', help='The average interval of topology changing.', type=float)
    topology_setting.add_argument('--edge_remove_prob', help='The probability of each links being removed in each round.', type=float)
    topology_setting.add_argument('--edge_add_prob', help='The probability of each links being added in each round.', type=float)
    topology_setting.add_argument('--max_allowed_partitions', help='The maximum number of network partitions being allowed.', type=int)
    # AdhocNetworkSettings
    adhoc_setting = parser.add_argument_group('AdhocNetworkSettings', 'Settings for AdhocNetwork')
    adhoc_setting.add_argument('--region_width', help='Width of the region for the network.', type=float)
    adhoc_setting.add_argument('--comm_range', help='Communication range.', type=float)
    adhoc_setting.add_argument('--move_variance', help='Variance of the movement when position updates in Gaussian random walk.', type=float)
    adhoc_setting.add_argument('--enable_large_scale_fading', help='If large-scale fading is enabled, the segment size will be adjusted automatically according to the fading model.', action='store_true')
    adhoc_setting.add_argument('--path_loss_level', help='Path loss level. low/medium/high', type=str)
    adhoc_setting.add_argument('--bandwidth_max', help='The max bandwidth is the bandwidth within the range of comm_range/100 in MB/round.', type=float)
    # DataItemSettings
    dataitem_setting = parser.add_argument_group('DataItemSettings', 'Settings for DataItem')
    dataitem_setting.add_argument('--dataitem_enable', help='Enable dataitem generation.', action='store_true')
    dataitem_setting.add_argument('--max_block_capacity', help='''The maximum number of dataitems that a block can contain. 
                                                                  max_block_capacity=0 will disable the dataitem mechanism.''', type=int)
    dataitem_setting.add_argument('--dataitem_size', help='The size of each dataitem in MB.', type=int)
    dataitem_setting.add_argument('--dataitem_input_interval', help='''The interval of dataitem input in rounds.
                                                                       dataitem_input_interval=0 will disable the dataitem queue of each miner.''', type=int)

    parser.add_argument('--result_path',help='The path to output results', type=str)
    parser.add_argument('--result-summary', dest='result_summary', type=str,
                        help='Write the attack outcome to a JSON file.')
    parser.add_argument('--no-save-results', dest='no_save_results', action='store_true',
                        help='Skip large chain and figure artifacts (useful for batch tests).')
    parser.add_argument('--seed', type=int,
                        help='Seed Python and NumPy random generators for a reproducible run.')
    parser.add_argument('--attack-case-json', type=str, help=argparse.SUPPRESS)
    parser.add_argument('--premining-test-config', type=str,
                        help='Run parallel pre-mining DoubleSpending cases from JSON.')
    parser.add_argument('--premining-test-workers', type=int,
                        help='Override max_workers in the pre-mining test JSON.')
    parser.add_argument('--disable_post_verification', action='store_true',
                        help='Disable post verification of the longest chain in the global chain right after the main loop in exec().')

    args = vars(parser.parse_args())

    if args.get('attack_case_json'):
        with Path(args['attack_case_json']).open('r', encoding='utf-8') as case_input:
            case_args = json.load(case_input)
        case_args['result_path'] = Path(case_args['result_path'])
        if case_args.get('seed') is not None:
            random.seed(case_args['seed'])
            np.random.seed(case_args['seed'])
        main(**case_args)
        raise SystemExit(0)

    direct_test = PREMINING_DOUBLE_SPENDING_TEST
    if direct_test.get('enabled', False):
        summaries = premining_double_spending_attack(
            direct_test.get('parameter_sets', []),
            max_workers=direct_test.get('max_workers', 1),
            output_dir=direct_test.get(
                'output_dir', 'Results/premining_double_spending'
            ),
            default_config=direct_test.get('config', 'system_config.ini'),
            defaults=direct_test.get('defaults', {}),
            keep_run_results=bool(
                direct_test.get('keep_run_results', False)
            ),
        )
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        raise SystemExit(0)

    if args.get('premining_test_config'):
        batch_path = Path(args['premining_test_config']).resolve()
        with batch_path.open('r', encoding='utf-8') as batch_input:
            batch_config = json.load(batch_input)
        if isinstance(batch_config, list):
            parameter_sets = batch_config
            batch_config = {}
        else:
            parameter_sets = batch_config.get('parameter_sets', [])
        max_workers = (args.get('premining_test_workers') or
                       batch_config.get('max_workers', 1))
        summaries = premining_double_spending_attack(
            parameter_sets,
            max_workers=max_workers,
            output_dir=batch_config.get(
                'output_dir', 'Results/premining_double_spending'
            ),
            default_config=batch_config.get('config', 'system_config.ini'),
            defaults=batch_config.get('defaults', {}),
            keep_run_results=bool(batch_config.get('keep_run_results', False)),
        )
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        raise SystemExit(0)

    args['result_path'] = args['result_path'] and Path(args['result_path'])
    if args.get('seed') is not None:
        random.seed(args['seed'])
        np.random.seed(args['seed'])
    if difficulty := args.get('difficulty'):
        target_bin = int('F'*64, 16) >> difficulty
        args['target'] = f"{target_bin:0>64X}"
    else:
        args['target'] = None

    if args.get('adver_lists') is not None:
        args['adver_lists'] = eval(args.get('adver_lists', 'None'))
    args['attack_arg'] = {}
    if args.get('Ng') is not None:
        args['attack_arg']['Ng'] = args.get('Ng')
    if args.get('eclipse_target') is not None:
        args['attack_arg']['eclipse_target'] = eval(args.get('eclipse_target'))
    if args.get('premining_enabled') is not None:
        args['attack_arg']['premining_enabled'] = args.get('premining_enabled')
    for key in ('premining_end_condition', 'premining_target_height',
                'premining_target_round', 'premining_start_height'):
        if args.get(key) is not None:
            args['attack_arg'][key] = args.get(key)

    main(**args)
    # experiment(trail_num=50, **args)
