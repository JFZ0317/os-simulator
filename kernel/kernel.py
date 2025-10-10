from threading import Event
import time

from clock.clock import ClockDevice
from cpu.cpu import CPU
from instructions.instruction import Instruction
from process.process import PCB, KernelProcess, UserProcess

# ------------------------------
# 调度器（Scheduler）
# ------------------------------
class Scheduler:
    def __init__(self, kernel):
        self.kernel = kernel
        self.ready_queue = []

    def add_ready_process(self, pcb):
        pcb.state = "ready"
        self.ready_queue.append(pcb)
        print(f"[调度器] 进程 {pcb.process.pid} 进入就绪队列")

    def select_next_process(self, current_pcb):
        self.ready_queue = [pcb for pcb in self.ready_queue if pcb.process.pid in self.kernel.pcbs]

        if not self.ready_queue:
            resident_pcb = self.kernel.pcbs.get(100)
            if resident_pcb:
                self.add_ready_process(resident_pcb)
            else:
                return None

        if current_pcb and current_pcb.process.pid in self.kernel.pcbs:
            current_pcb.state = "ready"
            self.ready_queue.append(current_pcb)

        next_pcb = self.ready_queue.pop(0)
        next_pcb.state = "running"
        print(f"[调度器] 选中进程 {next_pcb.process.pid}（状态：running）")
        return next_pcb

# ------------------------------
# 内核（Kernel）
# ------------------------------
class Kernel:
    def __init__(self):
        self.cpu = CPU(self)
        self.clock = ClockDevice(interval=1)
        self.clock.set_cpu(self.cpu)
        self.system_time = 0  # 系统时间（时钟滴答数）
        self.current_pcb = None  # 当前运行的进程PCB
        self.scheduler = Scheduler(self)
        self.pcbs = {}  # 所有进程的PCB：{pid: PCB}
        self.memory = {}  # 模拟内存：{地址: 值}
        # 系统调用表：{调用名称: 处理函数}（核心新增）
        self.syscall_table = {
            "get_process_count": self._sys_get_process_count,
            "print_message": self._sys_print_message
        }
        # 用户权限表：{pid: 权限等级}（0=普通用户，1=管理员）
        self.user_privileges = {
            1: 0,   # 用户进程1：普通用户
            2: 1,   # 用户进程2：管理员
            3: 0    # 用户进程3：普通用户（除零测试）
        }

    def start(self):
        """启动系统：初始化进程+启动时钟+开始调度"""
        print("=== 系统启动（内核初始化） ===")
        self._create_initial_processes()
        self.clock.start()
        self._schedule_and_run()

    def _create_initial_processes(self):
        """创建初始进程（内核进程+用户进程）"""
        # 1. 内核进程1：系统日志（常驻循环，pid=100）
        log_process = KernelProcess(pid=100, kernel=self, loop_strategy="always_loop")
        log_process.register_task(
            task_id="sys_log",
            instructions=[
                Instruction("kernel", "MOV", ["R5", 0], ["register", "immediate"]),
                Instruction("kernel", "PRINT", ["系统日志：时间=R5"], ["memory"])
            ]
        )
        log_pcb = PCB(log_process)
        log_pcb.priority = 3
        self.pcbs[100] = log_pcb
        self.scheduler.add_ready_process(log_pcb)
        log_process.wake_up("sys_log")

        # 2. 内核进程2：进程监控（常驻循环，pid=101）
        monitor_process = KernelProcess(pid=101, kernel=self, loop_strategy="always_loop")
        monitor_process.register_task(
            task_id="process_monitor",
            instructions=[
                Instruction("kernel", "GET_PROCESS_COUNT", ["R10"], ["register"]),
                Instruction("kernel", "PRINT", ["内核监控：总进程数=R10"], ["memory"])
            ]
        )
        monitor_pcb = PCB(monitor_process)
        monitor_pcb.priority = 3
        self.pcbs[101] = monitor_pcb
        self.scheduler.add_ready_process(monitor_pcb)
        monitor_process.wake_up("process_monitor")

        # 3. 用户进程1：普通用户，获取用户态进程数（pid=1）
        user1 = UserProcess(pid=1, instructions=[
            Instruction("user", "SYSCALL", ["get_process_count", "R0"], flags=["TRAP"]),
            Instruction("user", "PRINT", ["普通用户：当前用户态进程数=R0"], ["memory"])
        ])
        user1_pcb = PCB(user1)
        user1_pcb.priority = 1
        self.pcbs[1] = user1_pcb
        self.scheduler.add_ready_process(user1_pcb)

        # 4. 用户进程2：管理员，获取全系统进程数（pid=2）
        user2 = UserProcess(pid=2, instructions=[
            Instruction("user", "SYSCALL", ["get_process_count", "R0"], flags=["TRAP"]),
            Instruction("user", "PRINT", ["管理员：当前全系统进程数=R0"], ["memory"])
        ])
        user2_pcb = PCB(user2)
        user2_pcb.priority = 1
        self.pcbs[2] = user2_pcb
        self.scheduler.add_ready_process(user2_pcb)

        # 5. 用户进程3：除零测试（pid=3）
        user3 = UserProcess(pid=3, instructions=[
            Instruction("user", "MOV", ["R0", 10], ["register", "immediate"]),
            Instruction("user", "DIV", ["R1", "R0", 0], ["register", "register", "immediate"])
        ])
        user3_pcb = PCB(user3)
        user3_pcb.priority = 1
        self.pcbs[3] = user3_pcb
        self.scheduler.add_ready_process(user3_pcb)
        print(f"\n初始化后就绪队列进程ID：{[pcb.process.pid for pcb in self.scheduler.ready_queue]}")
        print(f"初始化后PCB表进程ID：{list(self.pcbs.keys())}")

    def handle_interrupt(self, interrupt_type, data, current_context):
        """处理硬件中断（如时钟中断）"""
        if interrupt_type == "clock":
            self._handle_clock_interrupt(data, current_context)

    def _handle_clock_interrupt(self, ticks, current_context):
        """时钟中断处理：更新时间+触发调度"""
        self.system_time = ticks
        print(f"\n[内核ISR] 处理时钟中断，系统时间={self.system_time}")

        # 每5个滴答唤醒系统日志进程
        if ticks % 5 == 0:
            log_process = self.pcbs.get(100).process
            log_process.wake_up("sys_log")

        # 每10个滴答唤醒进程监控进程
        if ticks % 10 == 0:
            monitor_process = self.pcbs.get(101).process
            monitor_process.wake_up("process_monitor")

        # 保存当前进程上下文
        if self.current_pcb:
            self.current_pcb.context = current_context
            self.current_pcb.time_slice += 1
            print(f"[内核] 保存进程{self.current_pcb.process.pid}上下文（时间片={self.current_pcb.time_slice}）")

        # 每3个滴答触发调度（时间片轮转）
        if ticks % 3 == 0:
            print(f"[内核] 时间片用完，触发调度")
            self.current_pcb = self.scheduler.select_next_process(self.current_pcb)
            if self.current_pcb:
                self.cpu.load_context(self.current_pcb.context)
            else:
                return
        else:
            if self.current_pcb:
                self.cpu.load_context(current_context)

        if self.current_pcb:
            self._resume_current_process()

    def handle_exception(self, exception_type, data, current_context):
        """处理内中断（异常）"""
        if exception_type == "divide_by_zero":
            self._handle_divide_by_zero(data, current_context)
        elif exception_type == "privilege_violation":
            self._handle_privilege_violation(data, current_context)
        elif exception_type == "invalid_instruction":
            self._handle_invalid_instruction(data, current_context)

    def _handle_divide_by_zero(self, instr, current_context):
        print(f"[内核异常] 除零错误：指令{instr}触发，终止进程")
        if self.current_pcb:
            self.current_pcb.context = current_context
            self._terminate_process(self.current_pcb)
            self.current_pcb = None
        self.current_pcb = self.scheduler.select_next_process(None)
        if self.current_pcb:
            self.cpu.load_context(self.current_pcb.context)
            self._resume_current_process()

    def _handle_privilege_violation(self, instr, current_context):
        print(f"[内核异常] 特权违规：用户态执行{instr}，终止进程")
        if self.current_pcb:
            self.current_pcb.context = current_context
            self._terminate_process(self.current_pcb)
            self.current_pcb = None
        self.current_pcb = self.scheduler.select_next_process(None)
        if self.current_pcb:
            self.cpu.load_context(self.current_pcb.context)
            self._resume_current_process()

    def _handle_invalid_instruction(self, instr, current_context):
        print(f"[内核异常] 无效指令：{instr}，终止进程")
        if self.current_pcb:
            self.current_pcb.context = current_context
            self._terminate_process(self.current_pcb)
            self.current_pcb = None
        self.current_pcb = self.scheduler.select_next_process(None)
        if self.current_pcb:
            self.cpu.load_context(self.current_pcb.context)
            self._resume_current_process()

    # ------------------------------
    # 系统调用核心处理逻辑（新增）
    # ------------------------------
    def handle_syscall(self, syscall_name, user_context):
        """系统调用统一入口：分发到对应处理函数"""
        if syscall_name not in self.syscall_table:
            print(f"[内核] 未知系统调用：{syscall_name}")
            return -1  # 错误码
        # 调用对应处理函数
        return self.syscall_table[syscall_name](user_context)

    def _sys_get_process_count(self, user_context):
        """系统调用：获取进程数（根据用户权限返回不同结果）"""
        # 1. 查找发起系统调用的用户进程PID
        current_pid = None
        for pid, pcb in self.pcbs.items():
            if isinstance(pcb.process, UserProcess) and pcb.context["pc"] == user_context["pc"]:
                current_pid = pid
                break
        if not current_pid:
            return -1  # 无法识别进程

        # 2. 根据权限返回结果
        privilege = self.user_privileges.get(current_pid, 0)
        if privilege == 0:
            # 普通用户：仅统计用户态进程
            user_count = len([
                pcb for pcb in self.pcbs.values()
                if isinstance(pcb.process, UserProcess)
            ])
            print(f"[内核] 处理系统调用：{current_pid}（普通用户）→ 用户态进程数={user_count}")
            return user_count
        else:
            # 管理员：统计全系统进程（用户+内核）
            total_count = len(self.pcbs)
            print(f"[内核] 处理系统调用：{current_pid}（管理员）→ 全系统进程数={total_count}")
            return total_count

    def _sys_print_message(self, user_context):
        """系统调用：打印消息（示例）"""
        msg = user_context["registers"].get("R1", "空消息")
        print(f"[内核] 处理系统调用print_message → {msg}")
        return 0  # 成功码

    # ------------------------------
    # 进程终止与回收
    # ------------------------------
    def _terminate_process(self, pcb):
        pid = pcb.process.pid
        process_type = "内核进程" if isinstance(pcb.process, KernelProcess) else "用户进程"
        print(f"\n[进程终止] {process_type}{pid} 开始回收资源...")

        # 1. 从PCB表删除
        if pid in self.pcbs:
            del self.pcbs[pid]
            print(f"[资源回收] 已删除进程{pid}的PCB")

        # 2. 从就绪队列移除
        self.scheduler.ready_queue = [q for q in self.scheduler.ready_queue if q.process.pid != pid]
        print(f"[资源回收] 已从就绪队列移除进程{pid}")

        # 3. 模拟内存回收
        print(f"[资源回收] 进程{pid}回收完成\n")

    # ------------------------------
    # 调度与执行主循环
    # ------------------------------
    def _schedule_and_run(self):
        """调度进程并执行指令"""
        while True:
            if not self.clock.running:
                break
            if self.current_pcb:
                # 获取当前进程的下一条指令
                process = self.current_pcb.process
                if isinstance(process, KernelProcess):
                    instr = process.get_next_instruction()
                else:
                    instr = process.get_next_instruction(self.cpu.pc)

                if instr:
                    # 执行指令
                    self.cpu.execute_instruction(instr)
                else:
                    # 指令执行完毕，终止进程
                    print(f"[进程状态] 进程{process.pid}指令执行完毕")
                    self._terminate_process(self.current_pcb)
                    self.current_pcb = self.scheduler.select_next_process(None)
                    if self.current_pcb:
                        self.cpu.load_context(self.current_pcb.context)
            else:
                # 无当前进程，调度新进程
                self.current_pcb = self.scheduler.select_next_process(None)
                if self.current_pcb:
                    self.cpu.load_context(self.current_pcb.context)
            # 模拟指令执行耗时
            Event().wait(0.5)

    def _resume_current_process(self):
        """恢复进程执行"""
        print(f"[内核] 恢复进程{self.current_pcb.process.pid}执行")
    def __init__(self):
        self.cpu = CPU(self)
        self.clock = ClockDevice(interval=1)
        self.clock.set_cpu(self.cpu)
        self.system_time = 0
        self.current_pcb = None
        self.scheduler = Scheduler(self)
        self.pcbs = {}
        self.memory = {}  # 模拟内存（地址→值），用于内存寻址

    def start(self):
        print("=== 系统启动（内核初始化） ===")
        self._create_initial_processes()
        self.clock.start()
        self._schedule_and_run()

    def _create_initial_processes(self):
        # 1. 常驻内核进程：系统日志（pid=100）
        log_process = KernelProcess(pid=100, kernel=self, loop_strategy="always_loop")
        log_process.register_task(
            task_id="sys_log",
            instructions=[
                Instruction("kernel", "MOV", ["R5", self.system_time], ["register", "immediate"]),
                Instruction("kernel", "LOG", ["系统时间：R5"], flags=["INFO"])
            ]
        )
        log_pcb = PCB(log_process)
        log_pcb.priority = 3
        self.pcbs[log_process.pid] = log_pcb
        self.scheduler.add_ready_process(log_pcb)
        log_process.wake_up("sys_log")

        # 新增：进程数量报告内核进程（pid=101，常驻循环）
        process_monitor = KernelProcess(
            pid=101,
            kernel=self,
            loop_strategy="always_loop"  # 永久循环，定期报告
        )
        # 注册“进程数量报告”任务（指令会动态获取进程数）
        process_monitor.register_task(
            task_id="process_count_report",
            instructions=[
                # 指令1：获取当前进程数（通过内核接口）
                Instruction("kernel", "GET_PROCESS_COUNT", ["R10"], ["register"], ["SYSCALL"]),
                # 指令2：打印进程数
                Instruction("kernel", "PRINT", ["当前进程总数：R10"], ["memory"], ["INFO"])
            ]
        )
        # 创建PCB并设置高优先级
        monitor_pcb = PCB(process_monitor)
        monitor_pcb.priority = 3  # 与日志进程同级
        self.pcbs[process_monitor.pid] = monitor_pcb
        self.scheduler.add_ready_process(monitor_pcb)
        # 初始唤醒，开始报告
        process_monitor.wake_up("process_count_report")

        # 2. 用户进程1：测试多操作数和条件跳转（pid=1）
        user1 = UserProcess(pid=1, instructions=[
            # 指令1：MOV R0, 100（寄存器←立即数）
            Instruction("user", "MOV", ["R0", 100], ["register", "immediate"]),
            # 指令2：MOV R1, 200（寄存器←立即数）
            Instruction("user", "MOV", ["R1", 200], ["register", "immediate"]),
            # 指令3：ADD R2, R0, R1（R2 = R0 + R1，更新条件码）
            Instruction("user", "ADD", ["R2", "R0", "R1"], ["register", "register", "register"], ["CC"]),
            # 指令4：JMP 6（NZ）→ 若R2≠0则跳转到PC=6（跳过指令5）
            Instruction("user", "JMP", [6], ["immediate"], ["NZ"]),
            # 指令5：MOV R3, 0（若跳转则不执行）
            Instruction("user", "MOV", ["R3", 0], ["register", "immediate"]),
            # 指令6：MOV R3, 1（跳转目标）
            Instruction("user", "MOV", ["R3", 1], ["register", "immediate"])
        ])
        user1_pcb = PCB(user1)
        user1_pcb.priority = 1
        self.pcbs[user1.pid] = user1_pcb
        self.scheduler.add_ready_process(user1_pcb)

        # 3. 用户进程2：测试除零异常（pid=2）
        user2 = UserProcess(pid=2, instructions=[
            # 指令1：MOV R0, 50（被除数）
            Instruction("user", "MOV", ["R0", 50], ["register", "immediate"]),
            # 指令2：DIV R1, R0, 0（除零！R1 = R0 / 0）
            Instruction("user", "DIV", ["R1", "R0", 0], ["register", "register", "immediate"])
        ])
        user2_pcb = PCB(user2)
        user2_pcb.priority = 1
        self.pcbs[user2.pid] = user2_pcb
        self.scheduler.add_ready_process(user2_pcb)

    def handle_interrupt(self, interrupt_type, data, current_context):
        if interrupt_type == "clock":
            self._handle_clock_interrupt(data, current_context)

    def _handle_clock_interrupt(self, ticks, current_context):
        self.system_time = ticks
        print(f"\n[内核ISR] 处理时钟中断，系统时间={self.system_time}")

        # 每5个滴答唤醒日志进程（原有逻辑）
        if ticks % 5 == 0:
            log_process = self.pcbs.get(100).process
            log_process.wake_up("sys_log")

        # 新增：每10个滴答唤醒进程数量报告进程
        if ticks % 10 == 0:
            monitor_process = self.pcbs.get(101).process
            if monitor_process:
                monitor_process.wake_up("process_count_report")
                # 确保进程在就绪队列中
                monitor_pcb = self.pcbs[101]
                if monitor_pcb not in self.scheduler.ready_queue and monitor_pcb.state != "running":
                    self.scheduler.add_ready_process(monitor_pcb)
            print(f"[内核] 触发进程数量统计（系统时间={ticks}）")

        if self.current_pcb:
            self.current_pcb.context = current_context
            self.current_pcb.time_slice += 1
            print(f"[内核] 保存进程 {self.current_pcb.process.pid} 上下文（时间片={self.current_pcb.time_slice}）")

        if ticks % 3 == 0:
            print(f"[内核] 时间片用完，触发调度")
            self.current_pcb = self.scheduler.select_next_process(self.current_pcb)
            if self.current_pcb:
                self.cpu.load_context(self.current_pcb.context)
            else:
                return
        else:
            if self.current_pcb:
                self.cpu.load_context(current_context)

        if self.current_pcb:
            self._resume_current_process()

    def handle_exception(self, exception_type, data, current_context):
        if exception_type == "divide_by_zero":
            self._handle_divide_by_zero(data, current_context)
        elif exception_type == "privilege_violation":
            self._handle_privilege_violation(data, current_context)
        elif exception_type == "invalid_instruction":
            self._handle_invalid_instruction(data, current_context)

    def _handle_divide_by_zero(self, instr, current_context):
        print(f"[内核异常] 除零错误！指令 {instr} 触发内中断，进程将被终止")
        if self.current_pcb:
            self.current_pcb.context = current_context
            self._terminate_process(self.current_pcb)
            self.current_pcb = None
        self.current_pcb = self.scheduler.select_next_process(None)
        if self.current_pcb:
            self.cpu.load_context(self.current_pcb.context)
            self._resume_current_process()

    def _handle_privilege_violation(self, instr, current_context):
        print(f"[内核异常] 特权违规！用户态执行指令 {instr}，进程将被终止")
        if self.current_pcb:
            self.current_pcb.context = current_context
            self._terminate_process(self.current_pcb)
            self.current_pcb = None
        self.current_pcb = self.scheduler.select_next_process(None)
        if self.current_pcb:
            self.cpu.load_context(self.current_pcb.context)
            self._resume_current_process()

    def _handle_invalid_instruction(self, instr, current_context):
        print(f"[内核异常] 无效指令！{instr}，进程将被终止")
        if self.current_pcb:
            self.current_pcb.context = current_context
            self._terminate_process(self.current_pcb)
            self.current_pcb = None
        self.current_pcb = self.scheduler.select_next_process(None)
        if self.current_pcb:
            self.cpu.load_context(self.current_pcb.context)
            self._resume_current_process()

    def _terminate_process(self, pcb):
        pid = pcb.process.pid
        process_type = "内核进程" if isinstance(pcb.process, KernelProcess) else "用户进程"
        print(f"\n[进程终止] {process_type} {pid} 开始回收资源...")

        if pid in self.pcbs:
            del self.pcbs[pid]
            print(f"[资源回收] 已删除进程 {pid} 的PCB")

        self.scheduler.ready_queue = [q for q in self.scheduler.ready_queue if q.process.pid != pid]
        print(f"[资源回收] 已从就绪队列移除进程 {pid}")
        print(f"[资源回收] 进程 {pid} 回收完成\n")

    def _schedule_and_run(self):
        while True:
            if not self.clock.running:
                break
            if self.current_pcb:
                process = self.current_pcb.process
                if isinstance(process, KernelProcess):
                    instr = process.get_next_instruction()
                else:
                    instr = process.get_next_instruction(self.cpu.pc)

                if instr:
                    self.cpu.execute_instruction(instr)
                else:
                    print(f"[进程状态] 进程 {process.pid} 指令执行完毕")
                    self._terminate_process(self.current_pcb)
                    self.current_pcb = self.scheduler.select_next_process(None)
                    if self.current_pcb:
                        self.cpu.load_context(self.current_pcb.context)
            else:
                self.current_pcb = self.scheduler.select_next_process(None)
                if self.current_pcb:
                    self.cpu.load_context(self.current_pcb.context)
            Event().wait(0.5)

    def _resume_current_process(self):
        print(f"[内核] 恢复进程 {self.current_pcb.process.pid} 执行")
