"""
创建拼多多多多进宝推广位
生成三段式PID用于转链
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from platforms.pdd import PDDAdapter
from config import PLATFORM_CONFIGS


async def main():
    """创建推广位"""
    config = PLATFORM_CONFIGS.get("pdd")
    if not config:
        print("错误: 拼多多配置未找到")
        return

    adapter = PDDAdapter(config)

    print("正在创建多多进宝推广位...")
    print(f"当前PID: {adapter.pid}")
    print()

    # 创建推广位
    pid_list = await adapter.generate_pid(number=1, pid_name="公众号推广位")

    if pid_list:
        print(f"✅ 成功创建推广位!")
        print(f"新的PID: {pid_list[0]}")
        print()
        print("请将此PID更新到环境变量 PDD_PID 中，然后重启服务")
        print("export PDD_PID='{}'".format(pid_list[0]))
    else:
        print("❌ 创建推广位失败")
        print("请检查: 1) 拼多多API配置是否正确 2) 是否有创建推广位的权限")


if __name__ == "__main__":
    asyncio.run(main())
