from threading import Thread, Timer, Event
import time

class ClockDevice:
    """硬件时钟：定期向CPU发送中断信号（纯硬件行为）"""
    def __init__(self, interval=1):
        self.cpu = None
        self.interval = interval  # 中断间隔（秒）
        self.running = False
        self.ticks = 0

    def set_cpu(self, cpu):
        self.cpu = cpu

    def start(self):
        self.running = True
        Thread(target=self._tick, daemon=True).start()
        print(f"[时钟硬件] 启动，间隔 {self.interval} 秒")

    def stop(self):
        self.running = False

    def _tick(self):
        while self.running:
            time.sleep(self.interval)
            self.ticks += 1
            if self.cpu:
                # 硬件级：直接触发CPU的中断引脚（模拟硬件信号）
                self.cpu.receive_hardware_interrupt("clock", self.ticks)