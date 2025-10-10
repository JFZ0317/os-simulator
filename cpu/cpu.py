class CPU:
    def __init__(self, kernel):
        self.kernel = kernel
        self.registers = {}  # 通用寄存器：{"R0": 100, "R1": 200}
        self.flags = {}  # 条件标志：{"ZF": 0, "CF": 0}（零标志、进位标志）
        self.pc = 0  # 程序计数器
        self.cpsr = "user"  # 状态寄存器（user/kernel）
        self.interrupt_enabled = True

    def set_mode(self, mode):
        if mode in ["user", "kernel"] and self.cpsr != mode:
            self.cpsr = mode
            print(f"[CPU硬件] 特权级切换：{mode}")

    def _resolve_operand(self, operand, addressing_mode):
        """解析操作数（根据寻址方式获取实际值）"""
        if addressing_mode == "register":
            return self.registers.get(operand, 0)
        elif addressing_mode == "immediate":
            return operand
        elif addressing_mode == "memory":
            # 简化内存寻址：内存地址对应内核memory字典
            mem_addr = self.registers.get(operand, 0)
            return self.kernel.memory.get(mem_addr, 0)
        else:
            raise ValueError(f"不支持的寻址方式：{addressing_mode}")

    def execute_instruction(self, instr):
        # ------------------------------
        # 1. 特权级前置检查（用户态禁止执行内核指令，SYSCALL除外）
        # ------------------------------
        if instr.opcode != "SYSCALL" and self.cpsr == "user" and instr.mode == "kernel":
            self.raise_exception("privilege_violation", instr)
            return

        try:
            # ------------------------------
            # 工具函数：减少重复代码
            # ------------------------------
            def check_operand_count(expected):
                """校验指令操作数数量，不符则抛异常"""
                if len(instr.operands) != expected:
                    raise ValueError(f"{instr.opcode}指令需{expected}个操作数")

            def replace_register_content(content):
                """替换字符串中的寄存器引用（如"R0"→实际值）"""
                for reg, val in self.registers.items():
                    content = content.replace(reg, str(val))
                return content

            # ------------------------------
            # 2. 指令执行逻辑（按功能分类，精简代码）
            # ------------------------------
            match instr.opcode:
                # ------------------------------
                # 数据传输指令：MOV
                # ------------------------------
                case "MOV":
                    check_operand_count(2)
                    dst, src = instr.operands
                    dst_mode, src_mode = instr.addressing_modes
                    src_val = self._resolve_operand(src, src_mode)
                    self.registers[dst] = src_val
                    print(f"[CPU硬件] 执行指令：{instr} → {dst}={src_val}（PC={self.pc}）")

                # ------------------------------
                # 算术运算指令：ADD / DIV
                # ------------------------------
                case "ADD":
                    check_operand_count(3)
                    dst, op1, op2 = instr.operands
                    op1_val = self._resolve_operand(op1, instr.addressing_modes[1])
                    op2_val = self._resolve_operand(op2, instr.addressing_modes[2])
                    self.registers[dst] = op1_val + op2_val
                    print(f"[CPU硬件] 执行指令：{instr} → {dst}={op1_val}+{op2_val}={self.registers[dst]}（PC={self.pc}）")
                    # 条件码更新（CC标志）
                    if "CC" in instr.flags:
                        self.flags["ZF"] = 1 if self.registers[dst] == 0 else 0
                        print(f"[CPU硬件] 更新条件码：ZF={self.flags['ZF']}")

                case "DIV":
                    check_operand_count(3)
                    dst, divd, divr = instr.operands
                    divd_val = self._resolve_operand(divd, instr.addressing_modes[1])
                    divr_val = self._resolve_operand(divr, instr.addressing_modes[2])
                    print(f"[CPU硬件] 执行指令：{instr} → {dst}={divd_val}/{divr_val}（PC={self.pc}）")
                    if divr_val == 0:
                        raise ZeroDivisionError("除数为0")
                    self.registers[dst] = divd_val // divr_val

                # ------------------------------
                # 系统调用指令：SYSCALL（核心逻辑保留）
                # ------------------------------
                case "SYSCALL":
                    check_operand_count(2)
                    syscall_name, result_reg = instr.operands
                    print(f"[CPU硬件] 用户态发起系统调用：{syscall_name}（结果存{result_reg}，PC={self.pc}）")

                    # 1. 保存用户态上下文
                    user_context = {
                        "registers": self.registers.copy(),
                        "flags": self.flags.copy(),
                        "pc": self.pc,
                        "cpsr": self.cpsr
                    }
                    # 2. 切内核态→调用内核处理→写结果→切回用户态
                    self.set_mode("kernel")
                    sys_result = self.kernel.handle_syscall(syscall_name, user_context)
                    self.registers[result_reg] = sys_result
                    print(f"[CPU硬件] 系统调用返回结果：{result_reg}={sys_result}")
                    self.set_mode("user")

                # ------------------------------
                # 内核专用指令：GET_PROCESS_COUNT
                # ------------------------------
                case "GET_PROCESS_COUNT":
                    check_operand_count(1)
                    result_reg = instr.operands[0]
                    count = len(self.kernel.pcbs)
                    self.registers[result_reg] = count
                    print(f"[CPU硬件] 执行内核指令：{instr} → {result_reg}={count}（PC={self.pc}）")

                # ------------------------------
                # 输出指令：PRINT（用户态） / LOG（内核态）
                # ------------------------------
                case "PRINT":
                    check_operand_count(1)
                    content = replace_register_content(instr.operands[0])
                    print(f"[用户进程输出] {content}（PC={self.pc}）")

                case "LOG":
                    check_operand_count(1)
                    content = replace_register_content(instr.operands[0])
                    print(f"[内核日志] {content}（PC={self.pc}）")

                # ------------------------------
                # 空指令：NOP
                # ------------------------------
                case "NOP":
                    print(f"[CPU硬件] 执行指令：{instr}（PC={self.pc}）")

                # ------------------------------
                # 未知指令
                # ------------------------------
                case _:
                    raise ValueError(f"未知指令：{instr.opcode}")

        # ------------------------------
        # 3. 异常处理（精简捕获逻辑）
        # ------------------------------
        except ZeroDivisionError:
            self.raise_exception("divide_by_zero", instr)
            return
        except Exception as e:
            err_msg = f"{instr}（错误：{str(e)}）"
            self.raise_exception("invalid_instruction", err_msg)
            return

        # ------------------------------
        # 4. 程序计数器自增（统一处理）
        # ------------------------------
        self.pc += 1

    def receive_hardware_interrupt(self, interrupt_type, data):
        """处理硬件中断（如时钟中断）"""
        if not self.interrupt_enabled:
            return
        current_context = {
            "registers": self.registers.copy(),
            "flags": self.flags.copy(),
            "pc": self.pc,
            "cpsr": self.cpsr
        }
        self.set_mode("kernel")
        self.kernel.handle_interrupt(interrupt_type, data, current_context)

    def raise_exception(self, exception_type, data):
        """处理内中断（异常：特权违规、除零、无效指令）"""
        current_context = {
            "registers": self.registers.copy(),
            "flags": self.flags.copy(),
            "pc": self.pc,
            "cpsr": self.cpsr
        }
        self.set_mode("kernel")
        print(f"[CPU硬件] 触发内中断：{exception_type}（原因：{data}）")
        self.kernel.handle_exception(exception_type, data, current_context)

    def load_context(self, context):
        """加载进程上下文（进程切换时使用）"""
        self.registers = context["registers"].copy()
        self.flags = context.get("flags", {}).copy()
        self.pc = context["pc"]
        self.set_mode(context["cpsr"])
        print(f"[CPU硬件] 加载上下文：PC={self.pc}，标志={self.flags}")
