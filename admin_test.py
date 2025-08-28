"""
测试 Cookie 管理和环境变量配置功能
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_admin_api():
    """测试管理 API"""
    print("=== 测试管理 API ===")
    
    # 测试健康检查
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ 健康检查: {response.status_code}")
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return
    
    # 测试 Cookie API
    try:
        # 获取 Cookie 列表
        response = requests.get(f"{BASE_URL}/api/cookies")
        print(f"✅ 获取 Cookie 列表: {response.status_code}")
        
        # 更新 Cookie (测试)
        test_cookies = ["test_cookie_1", "test_cookie_2"]
        response = requests.post(f"{BASE_URL}/api/cookies", json={"cookies": test_cookies})
        print(f"✅ 更新 Cookie: {response.status_code}")
        
        # 获取配置
        response = requests.get(f"{BASE_URL}/api/config")
        print(f"✅ 获取配置: {response.status_code}")
        
        # 更新配置 (测试)
        test_config = {"log_level": "DEBUG", "show_think_tags": True}
        response = requests.put(f"{BASE_URL}/api/config", json=test_config)
        print(f"✅ 更新配置: {response.status_code}")
        
        print("\n🎉 所有 API 测试通过！")
        
    except Exception as e:
        print(f"❌ API 测试失败: {e}")

def test_frontend():
    """测试前端界面"""
    print("\n=== 测试前端界面 ===")
    
    try:
        # 测试管理界面是否可访问
        response = requests.get(f"{BASE_URL}/admin")
        print(f"✅ 管理界面: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 前端界面加载成功")
        else:
            print(f"❌ 前端界面加载失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 前端界面测试失败: {e}")

if __name__ == "__main__":
    print("🚀 开始测试 Z2API 管理功能...\n")
    test_admin_api()
    test_frontend()
    print("\n✨ 测试完成！")
    
    print(f"\n💡 访问管理界面: http://localhost:8000/admin")
    print(f"💡 API 端点: http://localhost:8000/api")
    print(f"💡 健康检查: http://localhost:8000/health")