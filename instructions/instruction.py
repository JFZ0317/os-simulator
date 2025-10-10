class Instruction:
    def __init__(self, mode, opcode, operands=None, addressing_modes=None, flags=None):
        self.mode = mode  # 特权级："user"/"kernel"
        self.opcode = opcode  # 操作码："MOV"/"ADD"/"SYSCALL"/"GET_PROCESS_COUNT"
        self.operands = operands or []  # 多操作数列表：如SYSCALL的["get_process_count", "R0"]
        self.addressing_modes = addressing_modes or []  # 寻址方式：["register", "immediate"]
        self.flags = flags or []  # 条件标志：["TRAP"（系统调用陷阱）, "CC"（更新条件码）]

    def __repr__(self):
        parts = [f"[{self.mode}] {self.opcode}"]
        if self.operands:
            parts.append(", ".join(map(str, self.operands)))
        if self.addressing_modes:
            parts.append(f"（寻址：{self.addressing_modes}）")
        if self.flags:
            parts.append(f"（标志：{self.flags}）")
        return " ".join(parts)