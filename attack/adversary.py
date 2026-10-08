import attack._adversary as A


class Adversary(A.Adversary): 
    def __init__(self, **args) -> None:
        super().__init__(**args)
