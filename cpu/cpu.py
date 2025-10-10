
class CPU:
    def __init__(self, kernel):
        self.kernel = kernel  # 仅用于中断时跳转内核处理（硬件到软件的入口）
        # 硬件寄存器（模拟CPU状态）
        self.registers = {}  # 通用寄存器（如R0-R7）
        self.pc = 0  # 程序计数器（当前执行指令的地址）
        self.cpsr = "user"  # 当前状态寄存器（"user"或"kernel"）
        self.interrupt_enabled = True  # 是否允许中断（硬件开关）

    def set_mode(self, mode):
        """硬件级：切换用户态/内核态（仅内核可调用，通过特权指令）"""
        if mode not in ["user", "kernel"]:
            raise ValueError("无效的CPU模式")
        self.cpsr = mode
        print(f"[CPU硬件] 模式切换为：{mode}")

    def execute_instruction(self, instr):
        """硬件级：执行一条指令（含特权检查）"""
        # 1. 特权检查（硬件强制）：用户态不能执行内核指令
        if self.cpsr == "user" and instr.mode == "kernel":
            # 触发硬件异常（如x86的#GP通用保护错误）
            self.raise_exception("privilege_violation", instr)
            return

        # 2. 执行指令（模拟硬件逻辑，实际是二进制运算，此处简化）
        print(f"[CPU硬件] 执行指令：{instr}（PC={self.pc}）")
        self.pc += 1  # 指令指针自增（模拟下一条指令地址）

    def receive_hardware_interrupt(self, interrupt_type, data):
        """硬件级：接收外部中断（如时钟），触发中断处理流程"""
        if not self.interrupt_enabled:
            return  # 中断被屏蔽（硬件级关闭）

        # 1. 硬件自动保存当前上下文（关键！CPU的核心职责）
        current_context = {
            "registers": self.registers.copy(),
            "pc": self.pc,
            "cpsr": self.cpsr
        }

        # 2. 硬件强制切换到内核态（中断处理必须在内核态）
        self.set_mode("kernel")

        # 3. 跳转到内核的中断服务例程（ISR），传递中断类型和保存的上下文
        self.kernel.handle_interrupt(interrupt_type, data, current_context)

    def raise_exception(self, exception_type, data):
        """硬件级：触发异常（如特权违规），流程类似中断"""
        # 保存上下文并切换到内核态
        current_context = {
            "registers": self.registers.copy(),
            "pc": self.pc,
            "cpsr": self.cpsr
        }
        self.set_mode("kernel")
        # 跳转到内核异常处理例程
        self.kernel.handle_exception(exception_type, data, current_context)

    def load_context(self, context):
        """硬件级：加载进程上下文（由内核调用，用于切换进程）"""
        self.registers = context["registers"].copy()
        self.pc = context["pc"]
        self.set_mode(context["cpsr"])  # 恢复到进程原来的模式（用户/内核）
        print(f"[CPU硬件] 加载上下文（PC={self.pc}，模式={self.cpsr}）")
