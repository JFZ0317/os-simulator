class Memory:
    def __init__(self, total_physical_pages=64, page_size=4096):
        """
        初始化内存模块（贴合现代 OS 内存模型）
        :param total_physical_pages: 物理页框总数（模拟物理内存大小：64页 × 4KB = 256KB）
        :param page_size: 页大小（现代 OS 常见值：4096字节=4KB）
        """
        self.page_size = page_size  # 页大小（虚拟/物理页统一大小）
        self.total_physical_pages = total_physical_pages  # 物理页框总数

        # 1. 物理内存管理：模拟物理页框（页框号→页数据）+ 空闲页框链表
        self.physical_pages = {}  # 物理页框：{page_frame_num: 页数据（bytes）}
        self.free_page_frames = list(range(total_physical_pages))  # 空闲页框链表（初始所有页空闲）

        # 2. 进程虚拟地址空间管理：为每个进程维护“虚拟页→物理页”映射表+权限
        # 结构：{pid: {"page_table": {vpn: pfn}, "permissions": {vpn: "r"/"rw"/"rx"}}}
        self.process_vm = {}

        # 3. 内核专用内存：模拟内核固定地址空间（如内核代码段、PCB 存储区）
        self.kernel_reserved_pages = self._reserve_kernel_memory()

    def _reserve_kernel_memory(self):
        """预留内核专用物理页框（现代 OS 中内核内存与用户内存分离）"""
        kernel_pages = []
        # 预留前 4 个页框给内核（模拟内核代码、全局变量、中断向量表）
        for i in range(4):
            if self.free_page_frames:
                pfn = self.free_page_frames.pop(0)
                kernel_pages.append(pfn)
                # 初始化内核页数据（标记为内核专用）
                self.physical_pages[pfn] = b"KERNEL_RESERVED" + b"\x00" * (self.page_size - 16)
        print(f"[内存模块] 预留内核专用页框：{kernel_pages}（共{len(kernel_pages)}页）")
        return kernel_pages

    def create_process_vm(self, pid):
        """为新进程创建独立虚拟地址空间（现代 OS 进程地址空间隔离的核心）"""
        if pid not in self.process_vm:
            self.process_vm[pid] = {
                "page_table": {},  # 虚拟页号（vpn）→ 物理页号（pfn）映射
                "permissions": {}  # 虚拟页权限：r（只读）、rw（读写）、rx（读执行）
            }
        print(f"[内存模块] 为进程{pid}创建虚拟地址空间（初始空页表）")

    def allocate_physical_page(self, pid, vpn, permission="rw"):
        """
        为进程分配物理页框并建立虚拟地址映射（模拟现代 OS 的页分配+页表更新）
        :param pid: 进程ID
        :param vpn: 需映射的虚拟页号
        :param permission: 虚拟页权限
        :return: 分配的物理页号（pfn），失败返回 None
        """
        # 1. 检查进程虚拟地址空间是否存在
        if pid not in self.process_vm:
            print(f"[内存模块] 进程{pid}未创建虚拟地址空间，分配失败")
            return None

        # 2. 检查空闲页框
        if not self.free_page_frames:
            print(f"[内存模块] 物理内存耗尽，进程{pid}页分配失败")
            return None

        # 3. 分配物理页框
        pfn = self.free_page_frames.pop(0)
        # 初始化页数据（空数据）
        self.physical_pages[pfn] = b"\x00" * self.page_size

        # 4. 建立虚拟页→物理页映射 + 设置权限
        self.process_vm[pid]["page_table"][vpn] = pfn
        self.process_vm[pid]["permissions"][vpn] = permission

        print(f"[内存模块] 进程{pid}：虚拟页{vpn} → 物理页{pfn}（权限：{permission}），剩余空闲页{len(self.free_page_frames)}")
        return pfn

    def free_physical_page(self, pid, vpn):
        """释放进程的物理页框并删除虚拟地址映射（模拟进程退出时的内存回收）"""
        if pid not in self.process_vm:
            return
        page_table = self.process_vm[pid]["page_table"]
        if vpn not in page_table:
            return

        # 1. 回收物理页框到空闲链表
        pfn = page_table.pop(vpn)
        if pfn not in self.kernel_reserved_pages:  # 不允许释放内核页
            self.free_page_frames.append(pfn)
            # 清空页数据（模拟内存擦除）
            del self.physical_pages[pfn]
            print(f"[内存模块] 进程{pid}：释放虚拟页{vpn}→物理页{pfn}，剩余空闲页{len(self.free_page_frames)}")

        # 2. 删除权限记录
        if vpn in self.process_vm[pid]["permissions"]:
            del self.process_vm[pid]["permissions"][vpn]

    def translate_virtual_address(self, pid, virtual_addr):
        """
        虚拟地址→物理地址转换（模拟现代 OS 的 MMU 地址转换功能）
        :param pid: 进程ID（确定使用哪个进程的页表）
        :param virtual_addr: 虚拟地址（整数）
        :return: (物理地址, 权限)，转换失败返回 (None, None)
        """
        # 1. 检查进程虚拟地址空间
        if pid not in self.process_vm:
            print(f"[内存模块] 进程{pid}无虚拟地址空间，地址转换失败")
            return None, None

        # 2. 拆分虚拟地址为“虚拟页号（vpn）”和“页内偏移（offset）”
        vpn = virtual_addr // self.page_size  # 虚拟页号 = 虚拟地址 // 页大小
        offset = virtual_addr % self.page_size  # 页内偏移 = 虚拟地址 % 页大小

        # 3. 查页表获取物理页号（pfn）
        page_table = self.process_vm[pid]["page_table"]
        if vpn not in page_table:
            print(f"[内存模块] 进程{pid}虚拟页{vpn}未映射物理页（缺页异常）")
            return None, None

        # 4. 计算物理地址
        pfn = page_table[vpn]
        physical_addr = pfn * self.page_size + offset

        # 5. 获取该虚拟页的权限
        permission = self.process_vm[pid]["permissions"].get(vpn, "r")

        return physical_addr, permission

    def read_memory(self, pid, virtual_addr, length=4):
        """
        读取内存数据（模拟 CPU 通过 MMU 读内存，需地址转换+权限检查）
        :param pid: 进程ID（当前运行进程）
        :param virtual_addr: 虚拟地址
        :param length: 读取字节数（默认4字节，模拟32位系统）
        :return: 读取的数据（整数），失败返回 0
        """
        # 1. 地址转换
        physical_addr, permission = self.translate_virtual_address(pid, virtual_addr)
        if not physical_addr:
            return 0

        # 2. 权限检查（读操作需“r”或“rw”或“rx”权限）
        if permission not in ["r", "rw", "rx"]:
            print(f"[内存模块] 进程{pid}读虚拟地址{virtual_addr}：权限不足（当前权限{permission}）")
            return 0

        # 3. 检查物理页是否存在
        pfn = physical_addr // self.page_size
        if pfn not in self.physical_pages:
            print(f"[内存模块] 物理页{pfn}不存在，读操作失败")
            return 0

        # 4. 读取页内数据（从物理页数据中截取偏移+长度的字节）
        page_data = self.physical_pages[pfn]
        offset = physical_addr % self.page_size
        # 确保读取长度不超出页边界
        if offset + length > self.page_size:
            length = self.page_size - offset
        read_data = page_data[offset:offset+length]

        # 5. 转换为整数（小端序，模拟x86架构）
        return int.from_bytes(read_data, byteorder="little", signed=False)

    def write_memory(self, pid, virtual_addr, data, length=4):
        """
        写入内存数据（模拟 CPU 通过 MMU 写内存，需地址转换+权限检查）
        :param pid: 进程ID（当前运行进程）
        :param virtual_addr: 虚拟地址
        :param data: 要写入的数据（整数）
        :param length: 写入字节数（默认4字节）
        :return: 成功返回 True，失败返回 False
        """
        # 1. 地址转换
        physical_addr, permission = self.translate_virtual_address(pid, virtual_addr)
        if not physical_addr:
            return False

        # 2. 权限检查（写操作需“rw”权限）
        if permission != "rw":
            print(f"[内存模块] 进程{pid}写虚拟地址{virtual_addr}：权限不足（当前权限{permission}）")
            return False

        # 3. 检查物理页是否存在
        pfn = physical_addr // self.page_size
        if pfn not in self.physical_pages:
            print(f"[内存模块] 物理页{pfn}不存在，写操作失败")
            return False

        # 4. 准备写入数据（转换为字节流，小端序）
        page_data = bytearray(self.physical_pages[pfn])  # 转为可修改的字节数组
        offset = physical_addr % self.page_size
        # 确保写入长度不超出页边界
        if offset + length > self.page_size:
            length = self.page_size - offset
        # 转换数据为字节流（不足补0）
        data_bytes = data.to_bytes(length, byteorder="little", signed=False)

        # 5. 写入物理页
        page_data[offset:offset+length] = data_bytes
        self.physical_pages[pfn] = page_data  # 写回物理页
        print(f"[内存模块] 进程{pid}：虚拟地址{virtual_addr}写入数据{data}（物理地址{physical_addr}）")
        return True

    def get_free_memory_size(self):
        """获取空闲物理内存大小（模拟现代 OS 的 free 命令）"""
        return len(self.free_page_frames) * self.page_size