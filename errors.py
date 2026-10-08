class NetMinerNumError(Exception):
    """网络矿工总数定义错误"""
    def __init__(self,ErrorInfo):
        super().__init__(self)  # 初始化父类
        self.errorinfo=ErrorInfo
    def __str__(self):
        return self.errorinfo
    
class NetAdjError(Exception):
    """邻接矩阵定义错误"""
    def __init__(self,ErrorInfo):
        super().__init__(self)  # 初始化父类
        self.errorinfo=ErrorInfo
    def __str__(self):
        return self.errorinfo
    
class NetIsoError(Exception):
    """网络存在孤立节点"""
    def __init__(self,ErrorInfo):
        super().__init__(self)  # 初始化父类
        self.errorinfo=ErrorInfo
    def __str__(self):
        return self.errorinfo
    
class NetUnconnetedError(Exception):
    """网络存在不连通部分"""
    def __init__(self,ErrorInfo):
        super().__init__(self)  # 初始化父类
        self.errorinfo=ErrorInfo
    def __str__(self):
        return self.errorinfo
    
class NetGenError(Exception):
    """网络生成方式错误"""
    def __init__(self,ErrorInfo):
        super().__init__(self)  # 初始化父类
        self.errorinfo=ErrorInfo
    def __str__(self):
        return self.errorinfo