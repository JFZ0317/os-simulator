from threading import Event

from clock.clock import ClockDevice
from cpu.cpu import CPU
from instructions.instruction import Instruction

class Kernel:
    def __init__(self):
        # 1. 创建CPU并关联内核
        self.cpu = CPU(self)
        # 2. 创建时钟部件并绑定CPU
        self.clock = ClockDevice()
        self.clock.set_cpu(self.cpu)
        # 内核维护的系统状态
        self.system_time = 0
        self.processes = ["user_app_1", "user_app_2"]  # 模拟进程列表

    def start(self):
        """启动系统：初始化硬件+运行用户进程"""
        print("=== 系统启动 ===")
        self.clock.start()  # 启动时钟
        self.cpu.change_to_user()  # 切换到用户态运行应用
        self.run_user_process()  # 开始执行用户进程

    def handle_clock_interrupt(self, ticks):
        """内核处理时钟中断（业务逻辑）"""
        self.system_time = ticks
        print(f"[内核] 处理时钟中断，系统时间更新为 {self.system_time}")
        
        # 每3次中断触发一次进程调度（模拟时间片轮转）
        if ticks % 3 == 0:
            print(f"[内核] 触发进程调度，切换到下一个进程")

    def handle_exception(self, instruction):
        """内核处理CPU异常（如用户态执行特权指令）"""
        print(f"[内核] 处理异常：禁止用户态执行特权指令《{instruction.name}》")
        # 可扩展：终止进程、返回错误码等

    def run_user_process(self):
        """模拟用户进程执行（会被时钟中断打断）"""
        print("\n[用户态] 开始执行用户进程")
        # 模拟用户进程执行一系列指令
        try:
            while True:
                # 普通指令（用户态可执行）
                user_instr = Instruction("user", "MOV R0, 100")
                self.cpu.run(user_instr)
                
                # 模拟指令执行间隔（会被时钟中断打断）
                Event().wait(1)
        except KeyboardInterrupt:
            print("\n[用户态] 进程执行终止")
            self.clock.stop()
