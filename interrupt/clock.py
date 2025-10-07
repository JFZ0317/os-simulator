import threading
import time

class Kernel:
    def __init__(self):
        self.running = True
        self.current_process = None
        self.timer = None
        self.clock_interval = 2
        self.all_processes = []
        # 预创建两个进程（复用）
        self.process_a = None
        self.process_b = None

    def start(self):
        print("[内核] 启动，开始时钟管理...")
        self._start_timer()
        
        # 初始化并启动进程A和B
        self.process_a = Process("进程A")
        self.process_b = Process("进程B")
        self.all_processes = [self.process_a, self.process_b]
        self.process_a.start()  # 启动进程A（初始阻塞）
        self.process_b.start()  # 启动进程B（初始阻塞）
        
        # 首次调度进程A
        self.current_process = self.process_a
        self.current_process.resume()  # 解除阻塞，让进程A开始执行

        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

    def _start_timer(self):
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.timer = threading.Timer(self.clock_interval, self._clock_interrupt)
        self.timer.start()

    def _clock_interrupt(self):
        print(f"\n[内核-时钟中断] 时间片结束（{self.clock_interval}秒）")
        
        # 暂停当前进程
        if self.current_process and self.current_process.is_alive():
            print(f"[内核] 暂停{self.current_process.name}")
            self.current_process.pause()
        
        # 切换到另一个进程
        self.current_process = self.process_b if self.current_process == self.process_a else self.process_a
        print(f"[内核] 切换到{self.current_process.name}")
        self.current_process.resume()  # 恢复新进程
        
        self._start_timer()

    def stop(self):
        self.running = False
        if self.timer:
            self.timer.cancel()
        # 回收所有进程
        for process in self.all_processes:
            if process.is_alive():
                process.stop()
                process.join()
        print("\n[内核] 停止运行，所有进程已回收")


class Process(threading.Thread):
    def __init__(self, name):
        super().__init__(name=name)
        self.paused = True  # 初始暂停
        self._pause_event = threading.Event()
        self._pause_event.clear()  # 初始阻塞（等待resume）
        self._stop_flag = False
        self.step = 1

    def run(self):
        print(f"[{self.name}] 线程启动（等待调度）")  # 确认线程已启动
        while not self._stop_flag:
            self._pause_event.wait()  # 等待被resume()
            if self._stop_flag:
                break
            print(f"[{self.name}] 执行步骤 {self.step}")
            self.step += 1
            # 可中断的等待（避免sleep期间无法响应暂停）
            for _ in range(10):
                if self.paused or self._stop_flag:
                    break
                time.sleep(0.1)
        print(f"[{self.name}] 终止执行")

    def pause(self):
        self.paused = True
        self._pause_event.clear()

    def resume(self):
        self.paused = False
        self._pause_event.set()

    def stop(self):
        self._stop_flag = True
        self.resume()


if __name__ == "__main__":
    kernel = Kernel()
    kernel.start()