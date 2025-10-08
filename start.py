# 运行示例
from kernel.kernel import Kernel


if __name__ == "__main__":
    kernel = Kernel()
    try:
        kernel.start()
    except KeyboardInterrupt:
        print("\n=== 系统关机 ===")