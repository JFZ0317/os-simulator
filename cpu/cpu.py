class CPU:
    def __init__(self, kernel):
        # 保留原有PSW状态管理
        self.status = {0: "kernel", 1: "user"}
        self.psw = 0  # 初始内核态
        self.kernel = kernel  # 关联内核，用于中断时交互

    def change_to_user(self):
        self.psw = 1
        print(f"CPU切换到{self.status[self.psw]}态")

    def change_to_kernel(self):
        self.psw = 0
        print(f"CPU切换到{self.status[self.psw]}态")

    # 扩展：处理时钟中断（与时钟部件对接）
    def handle_interrupt(self, ticks):
        """CPU收到中断后的硬件级处理流程"""
        print(f"\n[CPU] 收到第{ticks}次时钟中断")
        
        # 1. 硬件自动切换到内核态（中断强制特权级提升）
        current_mode = self.status[self.psw]
        self.change_to_kernel()
        print(f"[CPU] 中断强制切换：{current_mode} → {self.status[self.psw]}")
        
        # 2. 保存当前运行状态（简化模拟：实际需保存寄存器、PC等）
        saved_state = {"psw": self.psw, "current_instruction": "正在执行的指令"}
        print(f"[CPU] 保存现场：{saved_state}")
        
        # 3. 通知内核处理中断（内核负责业务逻辑）
        self.kernel.handle_clock_interrupt(ticks)
        
        # 4. 恢复现场（简化模拟）
        print(f"[CPU] 恢复现场：{saved_state}")
        
        # 5. 切回中断前的状态（如果之前是用户态）
        if current_mode == "user":
            self.change_to_user()

    # 保留原有指令执行逻辑
    def run(self, instruction):
        if not self.check_instruction(instruction):
            # 非法指令：陷入内核
            print(f"[CPU] 检测到用户态执行特权指令《{instruction.name}》")
            self.change_to_kernel()
            # 通知内核处理异常（扩展：新增异常处理交互）
            self.kernel.handle_exception(instruction)
            return False
        else:
            # 正常执行指令
            instruction.run()
            return True

    # 保留原有指令检查逻辑
    def check_instruction(self, instruction):
        if instruction.get_type() == "privileged" and self.psw == 1:
            # 用户态执行特权指令：非法
            return False
        return True