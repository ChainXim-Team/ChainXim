import hashlib
import importlib
from typing import Union
from scipy.special import factorial
import numpy as np


BYTE_ORDER = 'little'
HASH_LEN = 32
INT_LEN = 4

def calculate_h_t(lambda_, beta, t, max_terms=100):
    """
    计算 h(t) 的值。

    :param lambda_: lambda 参数
    :param beta: beta 参数
    :param t: 时间值
    :param max_terms: 级数计算的最大项数
    :return: h(t) 的计算结果
    """
    h_t = 0.0
    for k in range(max_terms + 1):
        term1 = np.exp(-1 * (1 - beta) * lambda_ * t) * ((1 - beta) * lambda_ * t) ** k / factorial(k)
        inner_sum = 0.0
        for n in range(k + 1):
            term2 = np.exp(-1 * beta * lambda_ * t) * (beta * lambda_ * t) ** n / factorial(n)
            term3 = (1 - (beta / (1 - beta)) ** (k - n))
            inner_sum += term2 * term3
        h_t += term1 * inner_sum

    return h_t

def hash_bytes(s: Union[bytes, bytearray]) -> hashlib._hashlib.HASH:
    hasher = hashlib.sha256()
    hasher.update(s)
    return hasher

def hashsha256(contentlist:list)->str:
    '''
    计算哈希值 (Deprecated)
    输入:需要转化为hash的内容           type:list
    输出:该list中所有内容的十六进制hash  type:str
    '''
    s = hashlib.sha256()
    data = ''.join([str(x) for x in contentlist])
    s.update(data.encode("utf-8")) 
    b = s.hexdigest()
    return b

def hashH(contentlist:list)->str:
    '''Deprecated'''
    return hashsha256(contentlist)

def hashG(contentlist:list)->str:
    '''Deprecated'''
    return hashsha256(contentlist)

def merkle_root(inputs):
    """计算默克尔树根的哈希值"""
    # 对每个输入进行哈希处理
    level = [hashsha256(input) for input in inputs]

    # 当层级中只剩下一个元素时，这个元素就是根哈希
    while len(level) > 1:
        # 准备下一层
        next_level = []

        # 两两配对处理
        for i in range(0, len(level), 2):
            # 如果是奇数个元素，复制最后一个元素
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            # 对两个哈希值进行哈希
            next_level.append(hashsha256(left + right))

        level = next_level

    return level[0]

def for_name(name):
    """
    返回并加载指定的类
    输入:name为指定类的路径 如Consensus.POW    type: str
    """
    # class_name = Test
    class_name = name.split('.')[-1]
    # import_module("lib.utils.test")
    file = importlib.import_module(name[:name.index("." + class_name)])
    clazz = getattr(file, class_name)
 
    return clazz

def targetG(p_per_round,miner_num,group,q):
    '''
    p = target/group
    (1-p)^(miner_num*q)=1 - p_per_round
    1-p=(1-p_per_round)**(1/(miner_num*q))
    p=1-(1-p_per_round)**(1/(miner_num*q))
    target = round(group*p)
    '''
    p=1-(1-p_per_round)**(1/(miner_num*q))
    target = round(group*p)
    return hex(target)[2:]


def target_adjust(difficulty):
    '''
    根据难度调整target前导零的数量,难度越大前导零越少
    param:difficulty(float):0~1
    return:target(str):256位的16进制数
    '''
    difficulty = difficulty
    leading_zeros_num = int(difficulty * (64 - 1))  # 前导零数量
    target = '0' * leading_zeros_num + 'F' * (64 - leading_zeros_num)  # 在前导零之前插入0字符
    return target

