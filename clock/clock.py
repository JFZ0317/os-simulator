from threading import Timer, Event

class ClockDevice:
    def __init__(self):
        self.period = 2  # 固定2秒中断一次
        self.ticks = 0
        self.is_running = False
        self.cpu = None  # 关联CPU
        self._timer = None
        self._stop_event = Event()

    def set_cpu(self, cpu):
        """绑定CPU，用于发送中断"""
        self.cpu = cpu

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        print(f"时钟启动，每{self.period}秒发送一次中断")
        self._send_interrupt()

    def stop(self):
        self.is_running = False
        self._stop_event.set()
        if self._timer:
            self._timer.cancel()
        print(f"时钟停止，共发送{self.ticks}次中断")

    def _send_interrupt(self):
        if not self.is_running or self._stop_event.is_set() or not self.cpu:
            return
        self.ticks += 1
        # 向CPU发送中断（调用CPU的中断处理方法）
        self.cpu.handle_interrupt(self.ticks)
        # 预约下一次中断
        self._timer = Timer(self.period, self._send_interrupt)
        self._timer.daemon = True
        self._timer.start()