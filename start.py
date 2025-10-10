# 运行示例
import time
from kernel.kernel import Kernel

if __name__ == "__main__":
    kernel = Kernel()
    try:
        kernel.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n=== 系统关闭 ===")
        kernel.clock.stop()