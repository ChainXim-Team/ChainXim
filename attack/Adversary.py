from attack.Adversary_abc import Adversary


class Adversary(Adversary): 
    def __init__(self, **args) -> None:
        super().__init__(**args)
