from instructions.instruction import Instruction


class PCB:
    """进程控制块：内核用于管理进程的元数据（软件结构）"""
    def __init__(self, process):
        self.process = process  # 关联的进程对象
        self.context = {  # 进程上下文（由内核保存，CPU加载）
            "registers": {},
            "pc": 0,
            "cpsr": "user" if isinstance(process, UserProcess) else "kernel"
        }
        self.state = "ready"  # 进程状态：ready/running/blocked
        self.priority = 1  # 优先级（调度用）
        self.time_slice = 0  # 已使用的时间片

class UserProcess:
    """用户进程：运行在用户态的程序（仅含非特权指令）"""
    def __init__(self, pid, instructions):
        self.pid = pid
        self.instructions = instructions  # 指令列表（存在内存中）

    def get_next_instruction(self, pc):
        """从内存中获取下一条指令（模拟内存读取）"""
        if pc < len(self.instructions):
            return self.instructions[pc]
        return None  # 指令执行完毕

class KernelProcess:
    """
    可扩展的内核进程类：支持任务模板注入和循环策略配置
    loop_strategy: 循环策略
        - "always_loop": 永久循环，任务完成后等待新事件（如日志监控）
        - "once": 一次性执行，任务完成后终止（如系统初始化）
        - "on_demand": 按需循环，无任务时休眠，有任务时唤醒（如I/O处理）
    """
    def __init__(self, pid, kernel, loop_strategy="on_demand"):
        self.pid = pid
        self.kernel = kernel
        self.loop_strategy = loop_strategy  # 循环策略（可配置）
        self.task_templates = {}  # 任务模板库：{task_id: 指令列表}
        self.current_task = None  # 当前执行的任务ID
        self.current_pc = 0  # 当前任务的指令指针

    def register_task(self, task_id, instructions):
        """
        注册任务模板（可扩展接口）
        :param task_id: 任务唯一标识（如"sys_log"、"io_handle"）
        :param instructions: 该任务的指令列表
        """
        if task_id not in self.task_templates:
            self.task_templates[task_id] = instructions
            print(f"[内核进程{self.pid}] 注册任务：{task_id}（指令数：{len(instructions)}）")
        else:
            print(f"[内核进程{self.pid}] 任务 {task_id} 已存在，跳过注册")

    def wake_up(self, task_id):
        """唤醒内核进程，指定要执行的任务（支持动态任务）"""
        if task_id not in self.task_templates:
            print(f"[内核进程{self.pid}] 未知任务 {task_id}，唤醒失败")
            return
        # 重置任务状态，准备执行
        self.current_task = task_id
        self.current_pc = 0
        print(f"[内核进程{self.pid}] 被唤醒，执行任务：{task_id}")

    def get_next_instruction(self):
        # 新增：动态获取当前系统进程数（统计pcbs字典的长度）
        current_process_count = len(self.kernel.pcbs)
        
        # 无任务时的行为
        if self.current_task is None:
            if self.loop_strategy == "always_loop":
                # 实时替换进程数，不再用固定文本
                return Instruction("kernel", f"[进程{self.pid}] 永久等待新任务...（当前进程数：{current_process_count}）")
            elif self.loop_strategy == "on_demand":
                return Instruction("kernel", f"[进程{self.pid}] 休眠等待唤醒...（当前进程数：{current_process_count}）")
            elif self.loop_strategy == "once":
                return None

        # 执行当前任务时，也替换日志中的进程数
        task_instrs = self.task_templates[self.current_task]
        if self.current_pc >= len(task_instrs):
            print(f"[内核进程{self.pid}] 任务 {self.current_task} 执行完毕")
            if self.loop_strategy == "always_loop":
                self.current_pc = 0
            else:
                self.current_task = None
            return self.get_next_instruction()

        # 动态替换指令中的进程数（如果指令包含“进程数”关键词）
        instr = task_instrs[self.current_pc]
        if "进程数" in instr.name:
            # 用实际进程数替换固定文本
            updated_name = instr.name.replace("进程数 3", f"进程数 {current_process_count}")
            instr = Instruction(instr.mode, updated_name)
        self.current_pc += 1
        return instr