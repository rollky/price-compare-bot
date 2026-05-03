from platforms.pdd import PDDAdapter
from config import PLATFORM_CONFIGS
import asyncio

async def main():
    config = PLATFORM_CONFIGS.get("pdd")
    adapter = PDDAdapter(config)
    # # 检查备案状态
    # result = await adapter.check_authority()
    # print(f"备案状态: {result}")
    # # 生成备案链接
    rp_url = await adapter.generate_rp_url()
    print(f"备案链接: {rp_url}")
    #
    # pid_list = await adapter.generate_pid()
    # print(f"推广位: {pid_list}")




if __name__ == "__main__":
    asyncio.run(main())