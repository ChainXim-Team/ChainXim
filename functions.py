import sys
import hashlib
import importlib
from typing import Union

BYTE_ORDER = sys.byteorder
HASH_LEN = 32
INT_LEN = 4

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

