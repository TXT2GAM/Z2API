#!/usr/bin/env python3
"""
测试Cookie刷新功能
"""
import asyncio
import json
import requests
import time

# API配置
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"
HEADERS = {"Content-Type": "application/json"}

def print_separator(title):
    """打印分隔线"""
    print("=" * 60)
    print(f" {title}")
    print("=" * 60)

def print_table_header():
    """打印表格头部"""
    print(f"{'序号':<6} {'账号':<20} {'密码':<15} {'Cookie':<40} {'状态':<10}")
    print("-" * 100)

def print_cookie_info(cookies, failed_cookies):
    """打印Cookie信息"""
    print_table_header()
    
    for i, cookie in enumerate(cookies, 1):
        is_failed = cookie in failed_cookies
        status = "无效" if is_failed else "可用"
        
        # 解析cookie格式
        email = ""
        password = ""
        cookie_display = cookie
        
        if '----' in cookie:
            parts = cookie.split('----')
            if len(parts) >= 3:
                email = parts[0]
                password = parts[1]
                cookie_display = parts[2]
            elif len(parts) == 2:
                email = parts[0]
                password = parts[1]
                cookie_display = "(需要获取Token)"
        
        # 截断显示
        if len(cookie_display) > 38:
            cookie_display = cookie_display[:18] + "..." + cookie_display[-18:]
        
        print(f"{i:<6} {email:<20} {password:<15} {cookie_display:<40} {status:<10}")

def get_cookies():
    """获取当前Cookie列表"""
    try:
        response = requests.get(f"{API_BASE}/cookies")
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"获取Cookie失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"获取Cookie异常: {e}")
        return None

def refresh_cookies():
    """刷新Cookie令牌"""
    try:
        print("正在刷新Cookie令牌...")
        response = requests.post(f"{API_BASE}/cookies/refresh")
        if response.status_code == 200:
            result = response.json()
            print(f"刷新成功!")
            print(f"消息: {result.get('message', 'N/A')}")
            print(f"刷新成功数: {result.get('refreshed_count', 0)}")
            print(f"刷新失败数: {result.get('failed_count', 0)}")
            print(f"总数: {result.get('total_count', 0)}")
            return result
        else:
            error_data = response.json()
            print(f"刷新失败: {response.status_code}")
            print(f"错误信息: {error_data.get('detail', 'N/A')}")
            return None
    except Exception as e:
        print(f"刷新异常: {e}")
        return None

def main():
    """主函数"""
    print_separator("Cookie刷新功能测试")
    
    # 获取当前Cookie状态
    print("\n1. 获取当前Cookie状态:")
    data = get_cookies()
    if not data:
        print("无法获取Cookie信息，请确保服务正在运行")
        return
    
    cookies = data.get('cookies', [])
    failed_cookies = data.get('failed_cookies', [])
    
    print(f"\n总Cookie数: {data.get('count', 0)}")
    print(f"失败Cookie数: {data.get('failed_count', 0)}")
    print(f"可用Cookie数: {data.get('count', 0) - data.get('failed_count', 0)}\n")
    
    if cookies:
        print("\n当前Cookie列表:")
        print_cookie_info(cookies, failed_cookies)
    else:
        print("没有Cookie数据")
    
    # 询问是否要刷新
    print("\n2. 刷新Cookie令牌:")
    choice = input("是否要刷新Cookie令牌? (y/N): ").strip().lower()
    
    if choice == 'y':
        result = refresh_cookies()
        if result:
            # 等待一会儿让刷新完成
            print("\n等待3秒让刷新操作完成...")
            time.sleep(3)
            
            # 再次获取Cookie状态
            print("\n3. 刷新后的Cookie状态:")
            data = get_cookies()
            if data:
                cookies = data.get('cookies', [])
                failed_cookies = data.get('failed_cookies', [])
                
                print(f"\n总Cookie数: {data.get('count', 0)}")
                print(f"失败Cookie数: {data.get('failed_count', 0)}")
                print(f"可用Cookie数: {data.get('count', 0) - data.get('failed_count', 0)}\n")
                
                if cookies:
                    print("\n刷新后的Cookie列表:")
                    print_cookie_info(cookies, failed_cookies)
                
                # 检查是否有账号密码丢失
                print("\n4. 检查账号密码信息:")
                lost_credentials = 0
                preserved_credentials = 0
                
                for cookie in cookies:
                    if '----' in cookie:
                        parts = cookie.split('----')
                        if len(parts) >= 3:
                            email = parts[0]
                            password = parts[1]
                            if email and password and email != 'unknown' and password != 'unknown':
                                preserved_credentials += 1
                            else:
                                lost_credentials += 1
                        else:
                            lost_credentials += 1
                    else:
                        lost_credentials += 1
                
                print(f"保留账号密码的Cookie: {preserved_credentials}")
                print(f"丢失账号密码的Cookie: {lost_credentials}")
                
                if preserved_credentials > 0:
                    print("✅ 部分Cookie的账号密码信息已保留")
                else:
                    print("❌ 所有Cookie的账号密码信息都已丢失")
                
                if lost_credentials > 0:
                    print("⚠️  部分Cookie的账号密码信息已丢失")
    else:
        print("跳过刷新操作")

if __name__ == "__main__":
    main()