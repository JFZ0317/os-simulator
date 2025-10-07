import threading
import time

# 定义全局 Timer 对象，用于后续取消定时器
global_timer = None

# 模拟“时钟中断处理程序”
def clock_interrupt_handler():
    global global_timer  # 声明使用全局变量
    print("\n[时钟中断] 时间片用完！切换到下一个进程（模拟）")
    
    # 重新创建下一个定时器，并赋值给全局变量（覆盖旧的已执行完毕的 Timer）
    global_timer = threading.Timer(2, clock_interrupt_handler)
    global_timer.start()

# 启动首次时钟中断（创建第一个定时器线程）
global_timer = threading.Timer(2, clock_interrupt_handler)
global_timer.start()

# 模拟进程执行（被时钟中断打断）
try:
    print("进程开始执行...")
    while True:
        time.sleep(1)
        print("进程正在运行...")
except KeyboardInterrupt:
    # 程序退出时，主动取消当前等待中的定时器线程
    if global_timer is not None and global_timer.is_alive():
        global_timer.cancel()
        print("\n[线程回收] 已取消等待中的时钟中断定时器")
    
    print("用户中断（Ctrl+C），程序正常退出")