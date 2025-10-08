class Instruction:
    def __init__(self, type_, name, func=None):
        self.name = name
        self.type = type_  # "privileged" 或 "user"
        self.func = func   # 指令执行的具体逻辑（可选）

    def get_type(self):
        return self.type

    def run(self, *args, **kwargs):
        print(f"执行指令: {self.name}")
        if self.func:
            self.func(*args, **kwargs)  # 执行指令绑定的逻辑