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
        # 1. 过滤无效进程（确保队列中都是存在于pcbs的进程）
        self.ready_queue = [pcb for pcb in self.ready_queue if pcb.process.pid in self.kernel.pcbs]
        
        # 2. 关键修复：当前进程（即使是running状态）若有效，强制放回就绪队列
        # （常驻进程运行中被调度时，需重新加入队列，避免丢失）
        if current_pcb:
            # 检查进程是否仍存在（未被回收）
            if current_pcb.process.pid in self.kernel.pcbs:
                # 标记为ready状态，放回队列
                current_pcb.state = "ready"
                # 避免重复加入（防止队列膨胀）
                if current_pcb not in self.ready_queue:
                    self.ready_queue.append(current_pcb)
                    print(f"[调度器] 将常驻进程 {current_pcb.process.pid} 重新加入就绪队列")
        
        # 3. 兜底：若就绪队列仍为空，主动加入常驻进程（pid=100）
        if not self.ready_queue:
            resident_pcb = self.kernel.pcbs.get(100)  # 常驻进程固定pid=100
            if resident_pcb and isinstance(resident_pcb.process, KernelProcess):
                resident_pcb.state = "ready"
                self.ready_queue.append(resident_pcb)
                print(f"[调度器] 就绪队列为空，主动加入常驻进程 {resident_pcb.process.pid}")
            else:
                print(f"[调度器] 无就绪进程，返回None")
                return None
        
        # 4. 选择队首进程，标记为running
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
        self.system_time = 0
        self.current_pcb = None
        self.scheduler = Scheduler(self)
        self.pcbs = {}

    def start(self):
        print("=== 系统启动（内核初始化） ===")
        self._create_initial_processes()
        self.clock.start()
        self._schedule_and_run()

    def _create_initial_processes(self):
        # 1. 常驻循环内核进程：系统日志（always_loop）
        log_process = KernelProcess(pid=100, kernel=self, loop_strategy="always_loop")
        log_process.register_task(
            task_id="sys_log",
            instructions=[
                Instruction("kernel", "LOG: 系统时间更新"),
                Instruction("kernel", "LOG: 内存使用率 25%"),
                Instruction("kernel", "LOG: 进程数 3")
            ]
        )
        log_pcb = PCB(log_process)
        log_pcb.priority = 3
        self.pcbs[log_process.pid] = log_pcb
        self.scheduler.add_ready_process(log_pcb)
        log_process.wake_up("sys_log")

        # 2. 一次性内核进程：系统初始化（once）
        init_process = KernelProcess(pid=102, kernel=self, loop_strategy="once")
        init_process.register_task(
            task_id="system_init",
            instructions=[
                Instruction("kernel", "INIT: 加载基础驱动"),
                Instruction("kernel", "INIT: 初始化内存管理"),
                Instruction("kernel", "INIT: 启动调度器")
            ]
        )
        init_pcb = PCB(init_process)
        init_pcb.priority = 5
        self.pcbs[init_process.pid] = init_pcb
        self.scheduler.add_ready_process(init_pcb)
        init_process.wake_up("system_init")

        # 3. 用户进程1
        user1 = UserProcess(pid=1, instructions=[
            Instruction("user", "MOV R0, 100"),
            Instruction("user", "ADD R1, R0"),
            Instruction("user", "PRINT R1 (用户1)")
        ])
        user1_pcb = PCB(user1)
        user1_pcb.priority = 1
        self.pcbs[user1.pid] = user1_pcb
        self.scheduler.add_ready_process(user1_pcb)

        # 4. 用户进程2
        user2 = UserProcess(pid=2, instructions=[
            Instruction("user", "MOV R2, 200"),
            Instruction("user", "SUB R3, R2"),
            Instruction("user", "PRINT R3 (用户2)")
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

        # 唤醒日志进程（确保进程100有任务可执行）
        if ticks % 5 == 0:
            log_process = self.pcbs.get(100).process
            log_process.wake_up("sys_log")

        # 保存当前进程上下文（仅当current_pcb有效时）
        if self.current_pcb:
            self.current_pcb.context = current_context
            self.current_pcb.time_slice += 1
            print(f"[内核] 保存进程 {self.current_pcb.process.pid} 上下文（时间片={self.current_pcb.time_slice}）")

        # 触发调度
        if ticks % 3 == 0:
            print(f"[内核] 时间片用完，触发调度")
            self.current_pcb = self.scheduler.select_next_process(self.current_pcb)
            
            # 关键判空：无进程可选时，不执行加载上下文
            if self.current_pcb is None:
                print(f"[内核] 无就绪进程，系统进入idle状态")
                return
            
            # 仅当current_pcb有效时，加载上下文
            self.cpu.load_context(self.current_pcb.context)
        else:
            # 不调度时，仅当current_pcb有效才加载上下文
            if self.current_pcb:
                self.cpu.load_context(current_context)

        # 恢复进程执行（仅当current_pcb有效时）
        if self.current_pcb:
            self._resume_current_process()

    def handle_exception(self, exception_type, data, current_context):
        if exception_type == "privilege_violation":
            print(f"[内核异常] 用户态执行特权指令：{data}，触发进程终止流程")  # 增强打印
            if self.current_pcb:
                self._terminate_process(self.current_pcb)
                self.current_pcb = None
            self.current_pcb = self.scheduler.select_next_process(None)
            if self.current_pcb:
                self.cpu.load_context(self.current_pcb.context)
                self._resume_current_process()

    def _terminate_process(self, pcb):
        """增强进程终止与回收的打印信息"""
        pid = pcb.process.pid
        process_type = "内核进程" if isinstance(pcb.process, KernelProcess) else "用户进程"
        
        # 1. 打印终止原因
        if isinstance(pcb.process, KernelProcess):
            if pcb.process.loop_strategy == "once":
                print(f"\n[进程终止] {process_type} {pid}（一次性任务）执行完毕，开始回收资源...")
            else:
                print(f"\n[进程终止] {process_type} {pid}（策略：{pcb.process.loop_strategy}）不满足终止条件，取消回收")
                pcb.state = "ready"
                return
        else:
            print(f"\n[进程终止] {process_type} {pid} 所有指令执行完毕，开始回收资源...")

        # 2. 回收PCB资源
        if pid in self.pcbs:
            del self.pcbs[pid]
            print(f"[资源回收] 已删除进程 {pid} 的PCB（进程控制块）")

        # 3. 从就绪队列移除
        original_queue_size = len(self.scheduler.ready_queue)
        self.scheduler.ready_queue = [q for q in self.scheduler.ready_queue if q.process.pid != pid]
        if len(self.scheduler.ready_queue) < original_queue_size:
            print(f"[资源回收] 已从就绪队列移除进程 {pid}")

        # 4. 模拟其他资源回收
        print(f"[资源回收] 已回收进程 {pid} 占用的内存、寄存器等资源")
        print(f"[资源回收] 进程 {pid} 回收完成，状态变更为：终止\n")

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
                    # 打印进程即将终止的提示
                    print(f"[进程状态] 进程 {process.pid} 已无指令可执行，触发终止流程")
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
