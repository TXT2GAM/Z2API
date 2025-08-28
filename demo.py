"""
Z2API 管理功能演示脚本

这个脚本展示了如何使用新添加的 Cookie 管理和环境变量配置功能。
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any

class Z2APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_cookies(self) -> Dict[str, Any]:
        """获取当前 Cookie 列表"""
        async with self.session.get(f"{self.base_url}/api/cookies") as response:
            return await response.json()
    
    async def update_cookies(self, cookies: list) -> Dict[str, Any]:
        """批量更新 Cookie"""
        data = {"cookies": cookies}
        async with self.session.post(
            f"{self.base_url}/api/cookies",
            json=data
        ) as response:
            return await response.json()
    
    async def clear_cookies(self) -> Dict[str, Any]:
        """清空所有 Cookie"""
        async with self.session.delete(f"{self.base_url}/api/cookies") as response:
            return await response.json()
    
    async def test_cookie(self, cookie: str) -> Dict[str, Any]:
        """测试单个 Cookie 有效性"""
        data = {"cookie": cookie}
        async with self.session.post(
            f"{self.base_url}/api/cookies/test",
            json=data
        ) as response:
            return await response.json()
    
    async def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        async with self.session.get(f"{self.base_url}/api/config") as response:
            return await response.json()
    
    async def update_config(self, **kwargs) -> Dict[str, Any]:
        """更新配置"""
        async with self.session.put(
            f"{self.base_url}/api/config",
            json=kwargs
        ) as response:
            return await response.json()
    
    async def reload_config(self) -> Dict[str, Any]:
        """重新加载配置"""
        async with self.session.post(f"{self.base_url}/api/config/reload") as response:
            return await response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        async with self.session.get(f"{self.base_url}/health") as response:
            return await response.json()

async def demo_cookie_management():
    """演示 Cookie 管理功能"""
    print("=== Cookie 管理演示 ===")
    
    async with Z2APIClient() as client:
        # 获取当前 Cookie 状态
        print("\n1. 获取当前 Cookie 状态:")
        try:
            cookies_info = await client.get_cookies()
            print(f"   总 Cookie 数: {cookies_info.get('count', 0)}")
            print(f"   失败 Cookie 数: {cookies_info.get('failed_count', 0)}")
        except Exception as e:
            print(f"   错误: {e}")
        
        # 添加测试 Cookie
        print("\n2. 添加测试 Cookie:")
        test_cookies = [
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_cookie_1",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_cookie_2",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_cookie_3"
        ]
        
        try:
            result = await client.update_cookies(test_cookies)
            print(f"   结果: {result.get('message', 'Success')}")
            
            # 获取更新后的状态
            cookies_info = await client.get_cookies()
            print(f"   更新后总 Cookie 数: {cookies_info.get('count', 0)}")
        except Exception as e:
            print(f"   错误: {e}")
        
        # 测试单个 Cookie
        print("\n3. 测试单个 Cookie:")
        try:
            test_result = await client.test_cookie("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_cookie_1")
            print(f"   Cookie 状态: {'有效' if test_result.get('is_valid') else '无效'}")
            print(f"   消息: {test_result.get('message', 'No message')}")
        except Exception as e:
            print(f"   错误: {e}")
        
        # 清空 Cookie
        print("\n4. 清空 Cookie:")
        try:
            result = await client.clear_cookies()
            print(f"   结果: {result.get('message', 'Success')}")
            
            # 验证清空
            cookies_info = await client.get_cookies()
            print(f"   清空后总 Cookie 数: {cookies_info.get('count', 0)}")
        except Exception as e:
            print(f"   错误: {e}")

async def demo_config_management():
    """演示配置管理功能"""
    print("\n=== 配置管理演示 ===")
    
    async with Z2APIClient() as client:
        # 获取当前配置
        print("\n1. 获取当前配置:")
        try:
            config = await client.get_config()
            print(f"   API Key: {config.get('api_key', 'Not set')}")
            print(f"   日志级别: {config.get('log_level', 'Not set')}")
            print(f"   端口: {config.get('port', 'Not set')}")
            print(f"   显示思考标签: {config.get('show_think_tags', 'Not set')}")
            print(f"   默认流式模式: {config.get('default_stream', 'Not set')}")
        except Exception as e:
            print(f"   错误: {e}")
        
        # 更新配置
        print("\n2. 更新配置:")
        try:
            result = await client.update_config(
                log_level="DEBUG",
                show_think_tags=True,
                default_stream=False,
                max_requests_per_minute=100
            )
            print(f"   更新结果: {result.get('message', 'Success')}")
            print(f"   更新字段: {', '.join(result.get('updated_fields', []))}")
        except Exception as e:
            print(f"   错误: {e}")
        
        # 验证更新
        print("\n3. 验证配置更新:")
        try:
            config = await client.get_config()
            print(f"   新的日志级别: {config.get('log_level', 'Not set')}")
            print(f"   新的显示思考标签: {config.get('show_think_tags', 'Not set')}")
            print(f"   新的流式模式: {config.get('default_stream', 'Not set')}")
            print(f"   新的最大请求数: {config.get('max_requests_per_minute', 'Not set')}")
        except Exception as e:
            print(f"   错误: {e}")
        
        # 重新加载配置
        print("\n4. 重新加载配置:")
        try:
            result = await client.reload_config()
            print(f"   结果: {result.get('message', 'Success')}")
        except Exception as e:
            print(f"   错误: {e}")

async def main():
    """主演示函数"""
    print("🚀 Z2API 管理功能演示")
    print("=" * 50)
    
    # 检查服务状态
    async with Z2APIClient() as client:
        try:
            health = await client.health_check()
            print(f"✅ 服务状态: {health.get('status', 'Unknown')}")
            print(f"🤖 模型: {health.get('model', 'Unknown')}")
            print(f"🌐 访问地址: http://localhost:8000/admin")
        except Exception as e:
            print(f"❌ 服务连接失败: {e}")
            print("💡 请确保服务器正在运行: python main.py")
            return
    
    # 运行演示
    await demo_cookie_management()
    await demo_config_management()
    
    print("\n" + "=" * 50)
    print("✨ 演示完成!")
    print("\n📖 使用说明:")
    print("   1. 启动服务: python main.py")
    print("   2. 访问管理界面: http://localhost:8000/admin")
    print("   3. 通过界面进行 Cookie 和配置管理")
    print("   4. 也可以使用 API 直接管理（如演示脚本所示)")

if __name__ == "__main__":
    asyncio.run(main())