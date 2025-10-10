class Instruction:
    def __init__(self, mode, name):
        self.mode = mode  # "user"（非特权）或 "kernel"（特权）
        self.name = name

    def __repr__(self):
        return f"[{self.mode}] {self.name}"