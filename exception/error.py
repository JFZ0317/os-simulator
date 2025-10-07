import threading
import time
import random

# ------------------------------
# 1. 自定义异常类
# ------------------------------
class DivideByZeroError(Exception):
    """模拟除零异常"""
    pass

class MemoryAccessError(Exception):
    """模拟内存访问越界异常"""
    pass

class InvalidInstructionError(Exception):
    """模拟非法指令异常"""
    pass


# ------------------------------
# 2. 进程类（支持抛出异常）
# ------------------------------
class Process(threading.Thread):
    def __init__(self, name):
        super().__init__(name=name)
        self.paused = True  # 初始暂停（等待调度）
        self._pause_event = threading.Event()
        self._pause_event.clear()  # 初始阻塞
        self._stop_flag = False
        self.step = 1
        self.exception_occurred = None  # 异常标记

    def run(self):
        print(f"[{self.name}] 启动（等待调度）")
        while not self._stop_flag:
            self._pause_event.wait()  # 等待内核调度
            if self._stop_flag:
                break

            try:
                # 模拟进程执行（20%概率触发异常）
                self._execute_step()
                print(f"[{self.name}] 执行步骤 {self.step}（正常）")
                self.step += 1

                # 可中断的等待（1秒）
                for _ in range(10):
                    if self.paused or self._stop_flag:
                        break
                    time.sleep(0.1)

            except (DivideByZeroError, MemoryAccessError, InvalidInstructionError) as e:
                self.exception_occurred = e
                self.paused = True
                self._pause_event.clear()
                print(f"[{self.name}] 执行步骤 {self.step} 时发生异常：{type(e).__name__}")
                break  # 异常后终止执行

        print(f"[{self.name}] 已终止")

    def _execute_step(self):
        """随机触发异常"""
        if random.random() < 0.2:
            raise random.choice([
                DivideByZeroError("除以零错误"),
                MemoryAccessError("访问非法内存0xFFFF"),
                InvalidInstructionError("非法指令0x0001")
            ])

    def pause(self):
        self.paused = True
        self._pause_event.clear()

    def resume(self):
        self.paused = False
        self._pause_event.set()

    def stop(self):
        self._stop_flag = True
        self.resume()  # 唤醒阻塞


# ------------------------------
# 3. 内核类（异常处理：终止进程，最终运行空进程）
# ------------------------------
class Kernel:
    def __init__(self):
        self.running = True
        self.current_process = None  # 当前运行的进程
        self.timer = None
        self.clock_interval = 2  # 时钟间隔
        self.all_processes = []  # 所有进程列表
        self.empty_process_counter = 0  # 空进程计数

    def start(self):
        print("[内核] 启动，开始进程调度与异常监控...")
        # 初始化并启动两个进程
        self.process_a = Process("进程A")
        self.process_b = Process("进程B")
        self.all_processes = [self.process_a, self.process_b]
        self.process_a.start()
        self.process_b.start()

        # 首次调度进程A
        self.current_process = self.process_a
        self.current_process.resume()

        # 启动时钟
        self._start_timer()

        try:
            while self.running:
                # 检查是否所有进程都已终止
                if all(not p.is_alive() for p in self.all_processes):
                    self._run_empty_process()  # 运行空进程
                # 检查当前进程是否异常
                elif self.current_process and self.current_process.exception_occurred:
                    self._handle_exception()  # 处理异常
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

    def _start_timer(self):
        """启动时钟定时器"""
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.timer = threading.Timer(self.clock_interval, self._clock_interrupt)
        self.timer.start()

    def _clock_interrupt(self):
        """时钟中断：切换进程（仅当有存活进程时）"""
        if not self.running:
            return

        # 若所有进程已终止，直接重启时钟（空进程模式）
        if all(not p.is_alive() for p in self.all_processes):
            self._start_timer()
            return

        print(f"\n[内核-时钟中断] 时间片结束（{self.clock_interval}秒）")
        
        # 暂停当前存活且无异常的进程
        if self.current_process and self.current_process.is_alive() and not self.current_process.exception_occurred:
            print(f"[内核] 暂停{self.current_process.name}")
            self.current_process.pause()
        
        # 切换到下一个存活的进程
        self.current_process = self._get_next_alive_process()
        if self.current_process:
            print(f"[内核] 切换到{self.current_process.name}")
            self.current_process.resume()
        else:
            print("[内核] 无存活进程可切换")
        
        self._start_timer()

    def _get_next_alive_process(self):
        """获取下一个存活的进程（简单轮询）"""
        if not self.all_processes:
            return None
        # 找到当前进程的索引
        current_idx = self.all_processes.index(self.current_process) if self.current_process in self.all_processes else -1
        # 从下一个索引开始查找存活进程
        for i in range(1, len(self.all_processes) + 1):
            idx = (current_idx + i) % len(self.all_processes)
            candidate = self.all_processes[idx]
            if candidate.is_alive() and not candidate.exception_occurred:
                return candidate
        return None  # 无存活进程

    def _handle_exception(self):
        """异常处理：直接终止异常进程，不重建"""
        error_process = self.current_process
        print(f"\n[内核-异常处理] 捕获{error_process.name}的异常：{error_process.exception_occurred}")
        print(f"[内核] 终止异常进程{error_process.name}")
        
        # 终止进程并从列表中移除
        error_process.stop()
        error_process.join()
        if error_process in self.all_processes:
            self.all_processes.remove(error_process)
        
        # 切换到下一个存活进程
        self.current_process = self._get_next_alive_process()
        if self.current_process:
            print(f"[内核] 切换到{self.current_process.name}继续执行")
            self.current_process.resume()
        else:
            print("[内核] 无存活进程，准备进入空进程模式")

    def _run_empty_process(self):
        """所有进程终止后，持续运行空进程"""
        self.empty_process_counter += 1
        print(f"\n[内核-空进程] 系统无活跃进程，空进程运行中（计数：{self.empty_process_counter}）")
        time.sleep(self.clock_interval)  # 保持与时钟间隔一致的节奏

    def stop(self):
        """停止内核"""
        self.running = False
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        # 终止所有剩余进程
        for p in self.all_processes:
            if p.is_alive():
                p.stop()
                p.join()
        print("\n[内核] 系统停止运行")


if __name__ == "__main__":
    kernel = Kernel()
    kernel.start()