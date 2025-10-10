from instructions.instruction import Instruction

class PCB:
    def __init__(self, process):
        self.process = process  # 关联的进程对象（UserProcess/KernelProcess）
        self.context = {
            "registers": {},
            "flags": {},
            "pc": 0,
            "cpsr": "user" if isinstance(process, UserProcess) else "kernel"
        }
        self.state = "ready"  # 进程状态：ready/running/blocked
        self.priority = 1     # 优先级（数字越小优先级越高）
        self.time_slice = 0   # 已使用时间片
        

class UserProcess:
    def __init__(self, pid, instructions):
        self.pid = pid  # 进程ID
        self.instructions = instructions  # 指令列表（扩展Instruction对象）

    def get_next_instruction(self, pc):
        """根据PC获取下一条指令（PC越界则返回None，标识进程结束）"""
        if 0 <= pc < len(self.instructions):
            return self.instructions[pc]
        return None


class KernelProcess:
    def __init__(self, pid, kernel, loop_strategy="on_demand"):
        self.pid = pid
        self.kernel = kernel
        self.loop_strategy = loop_strategy  # 循环策略：always_loop/on_demand/once
        self.task_templates = {}  # 任务模板：{task_id: 指令列表}
        self.current_task = None  # 当前执行的任务ID
        self.current_pc = 0       # 任务内部的PC

    def register_task(self, task_id, instructions):
        """注册任务（内核进程的指令集合）"""
        if task_id not in self.task_templates:
            self.task_templates[task_id] = instructions
            print(f"[内核进程{self.pid}] 注册任务：{task_id}（指令数：{len(instructions)}）")

    def wake_up(self, task_id):
        """唤醒进程，指定执行的任务"""
        if task_id in self.task_templates:
            self.current_task = task_id
            self.current_pc = 0
            print(f"[内核进程{self.pid}] 被唤醒，执行任务：{task_id}")

    def get_next_instruction(self):
        """获取下一条指令（根据循环策略处理任务执行逻辑）"""
        if self.current_task is None:
            # 无任务时：根据策略返回空指令或None
            if self.loop_strategy == "always_loop":
                return Instruction("kernel", "NOP", flags=["IDLE"])
            elif self.loop_strategy == "on_demand":
                return Instruction("kernel", "NOP", flags=["SLEEP"])
            else:
                return None

        # 有任务时：获取当前任务的下一条指令
        task_instrs = self.task_templates[self.current_task]
        if self.current_pc >= len(task_instrs):
            print(f"[内核进程{self.pid}] 任务 {self.current_task} 执行完毕")
            # 任务结束后：根据循环策略决定是否重启
            if self.loop_strategy == "always_loop":
                self.current_pc = 0
            else:
                self.current_task = None
            return self.get_next_instruction()

        # 返回当前指令并更新任务PC
        instr = task_instrs[self.current_pc]
        self.current_pc += 1
        return instr