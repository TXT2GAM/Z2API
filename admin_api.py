"""
Management API endpoints for Z.AI Proxy
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import set_key, get_key, unset_key

from config import settings
from cookie_manager import cookie_manager

logger = logging.getLogger(__name__)

router = APIRouter()

class CookieUpdateRequest(BaseModel):
    cookies: List[str]

class SingleCookieRequest(BaseModel):
    cookie: str
    
class ConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    admin_access_key: Optional[str] = None
    default_stream: Optional[bool] = None
    log_level: Optional[str] = None
    port: Optional[int] = None
    host: Optional[str] = None
    auto_refresh_tokens: Optional[bool] = None
    refresh_check_interval: Optional[int] = None
    response_timeout: Optional[int] = None
    connect_timeout: Optional[int] = None
    max_connections: Optional[int] = None
    max_keepalive_connections: Optional[int] = None
    keepalive_expiry: Optional[int] = None

@router.get("/api/cookies")
async def get_cookies():
    """获取当前 Cookie 列表"""
    # 确保返回的cookies格式一致，都包含账号密码信息
    processed_cookies = []
    for cookie in settings.COOKIES:
        # 如果cookie不是完整格式，转换为完整格式
        if '----' not in cookie:
            # 纯token格式，转换为完整格式
            cookie_info = cookie_manager.get_cookie_info(cookie)
            if cookie_info.get('has_credentials') and cookie_info.get('email'):
                # 如果cookie_info中有账号密码信息，使用完整格式
                full_cookie = f"{cookie_info['email']}----{cookie_info['password']}----{cookie}"
                processed_cookies.append(full_cookie)
            else:
                processed_cookies.append(cookie)
        else:
            # 已经是完整格式，直接使用
            processed_cookies.append(cookie)

    # 计算失败的cookie数量 - 基于处理后的cookies列表
    processed_failed_cookies = []
    for failed_cookie in cookie_manager.failed_cookies:
        # 检查失败的cookie是否在处理后的列表中
        if failed_cookie in processed_cookies:
            processed_failed_cookies.append(failed_cookie)
        else:
            # 查找对应的处理后的cookie
            for processed_cookie in processed_cookies:
                # 检查token部分是否匹配
                if '----' in processed_cookie:
                    token_part = processed_cookie.split('----')[-1]
                    if token_part == failed_cookie or failed_cookie == processed_cookie:
                        processed_failed_cookies.append(processed_cookie)
                        break
                elif processed_cookie == failed_cookie:
                    processed_failed_cookies.append(processed_cookie)
                    break

    return {
        "cookies": processed_cookies,
        "count": len(processed_cookies),
        "failed_count": len(processed_failed_cookies),
        "failed_cookies": processed_failed_cookies
    }

@router.post("/api/cookies")
async def update_cookies(request: CookieUpdateRequest):
    """批量更新 Cookie"""
    # 过滤空字符串
    valid_cookies = [cookie.strip() for cookie in request.cookies if cookie.strip()]
    
    if not valid_cookies:
        raise HTTPException(status_code=400, detail="至少需要一个有效的 Cookie")
    
    # 更新 settings 实例
    settings.COOKIES = valid_cookies
    
    # 使用新的update_cookies方法更新cookie_manager
    cookie_manager.update_cookies(valid_cookies)
    
    # 更新环境文件（如果存在）
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        try:
            set_key(env_file, 'Z_AI_COOKIES', ','.join(valid_cookies))
        except Exception as e:
            # 如果写入失败，只记录日志不报错
            print(f"Warning: Could not update .env file: {e}")
    
    return {
        "message": f"成功更新 {len(valid_cookies)} 个 Cookie",
        "cookies": valid_cookies
    }

@router.delete("/api/cookies")
async def clear_cookies():
    """清空所有 Cookie"""
    # 更新 settings 实例
    settings.COOKIES = []
    
    # 使用update_cookies方法重置cookie_manager
    cookie_manager.update_cookies([])
    
    # 更新环境文件（如果存在）
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        try:
            set_key(env_file, 'Z_AI_COOKIES', '')
        except Exception as e:
            print(f"Warning: Could not update .env file: {e}")
    
    return {"message": "已清空所有 Cookie"}

@router.post("/api/cookies/test")
async def test_cookie(request: Dict[str, str]):
    """测试单个 Cookie 有效性"""
    cookie = request.get("cookie")
    
    if not cookie:
        raise HTTPException(status_code=400, detail="请提供 Cookie")
    
    try:
        is_valid = await cookie_manager.health_check(cookie)
        return {
            "cookie": cookie[:20] + "..." if len(cookie) > 20 else cookie,
            "is_valid": is_valid,
            "message": "Cookie 有效" if is_valid else "Cookie 无效"
        }
    except Exception as e:
        return {
            "cookie": cookie[:20] + "..." if len(cookie) > 20 else cookie,
            "is_valid": False,
            "message": f"测试失败: {str(e)}"
        }

@router.post("/api/cookies/refresh")
async def refresh_cookies():
    """批量刷新 cookies 令牌"""
    try:
        result = await cookie_manager.batch_refresh_tokens()
        
        # 刷新成功后更新settings
        if result["success"] and result["refreshed_count"] > 0:
            settings.COOKIES = cookie_manager.cookies
            
            # 更新环境文件（如果存在）
            env_file = os.path.join(os.getcwd(), '.env')
            if os.path.exists(env_file):
                try:
                    set_key(env_file, 'Z_AI_COOKIES', ','.join(settings.COOKIES))
                    logger.info(f"Updated {len(settings.COOKIES)} cookies in .env file")
                except Exception as e:
                    print(f"Warning: Could not update .env file: {e}")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新 Cookies 失败: {str(e)}")

@router.post("/api/cookies/refresh/single")
async def refresh_single_cookie(request: SingleCookieRequest):
    """刷新单个 Cookie 令牌"""
    try:
        cookie = request.cookie
        if not cookie:
            raise HTTPException(status_code=400, detail="请提供 Cookie")
        
        # 尝试刷新单个cookie
        result = await cookie_manager.refresh_single_token(cookie)
        
        # 如果刷新成功，更新settings
        if result["success"]:
            settings.COOKIES = cookie_manager.cookies
            
            # 更新环境文件（如果存在）
            env_file = os.path.join(os.getcwd(), '.env')
            if os.path.exists(env_file):
                try:
                    set_key(env_file, 'Z_AI_COOKIES', ','.join(settings.COOKIES))
                    logger.info(f"Updated single cookie in .env file")
                except Exception as e:
                    print(f"Warning: Could not update .env file: {e}")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新单个 Cookie 失败: {str(e)}")

@router.post("/api/cookies/verify")
async def verify_cookie(request: SingleCookieRequest):
    """验证单个 Cookie 有效性"""
    try:
        cookie = request.cookie
        if not cookie:
            raise HTTPException(status_code=400, detail="请提供 Cookie")
        
        # 发送测试消息验证cookie有效性
        is_valid = await cookie_manager.health_check(cookie)
        
        return {
            "valid": is_valid,
            "cookie": cookie[:20] + "..." if len(cookie) > 20 else cookie,
            "message": "Cookie 有效" if is_valid else "Cookie 无效"
        }
    except Exception as e:
        return {
            "valid": False,
            "cookie": cookie[:20] + "..." if len(cookie) > 20 else cookie,
            "message": f"验证失败: {str(e)}"
        }

@router.get("/api/config")
async def get_config():
    """获取当前配置"""
    return {
        "api_key": settings.API_KEY,
        "admin_access_key": settings.ADMIN_ACCESS_KEY,
        "default_stream": settings.DEFAULT_STREAM,
        "log_level": settings.LOG_LEVEL,
        "port": settings.PORT,
        "host": settings.HOST,
        "auto_refresh_tokens": settings.AUTO_REFRESH_TOKENS,
        "refresh_check_interval": settings.REFRESH_CHECK_INTERVAL,
        "response_timeout": settings.RESPONSE_TIMEOUT,
        "connect_timeout": settings.CONNECT_TIMEOUT,
        "max_connections": settings.MAX_CONNECTIONS,
        "max_keepalive_connections": settings.MAX_KEEPALIVE_CONNECTIONS,
        "keepalive_expiry": settings.KEEPALIVE_EXPIRY,
        "model_name": settings.MODEL_NAME,
        "upstream_model": settings.UPSTREAM_MODEL
    }

@router.put("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    env_file = os.path.join(os.getcwd(), '.env')
    updated_fields = []
    
    # 更新配置
    update_dict = request.model_dump(exclude_unset=True)
    
    for key, value in update_dict.items():
        # 将驼峰命名转换为环境变量的大写下划线命名
        env_key = key.upper()
        
        # 设置内存中的值 - 直接设置，不需要hasattr检查
        # 因为这些属性都在__init__中动态创建
        setattr(settings, env_key, value)
        
        # 更新环境文件
        if os.path.exists(env_file):
            try:
                if isinstance(value, bool):
                    set_key(env_file, env_key, str(value).lower())
                else:
                    set_key(env_file, env_key, str(value))
                updated_fields.append(key)
            except Exception as e:
                print(f"Warning: Could not update {env_key} in .env file: {e}")
    
    return {
        "message": f"已更新配置: {', '.join(updated_fields)}",
        "updated_fields": updated_fields
    }

@router.post("/api/config/reload")
async def reload_config():
    """重新加载配置"""
    try:
        # 使用update_cookies方法重新加载cookie_manager
        cookie_manager.update_cookies(settings.COOKIES)
        
        return {"message": "配置已重新加载"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新加载配置失败: {str(e)}")

@router.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """管理界面主页"""
    html_file = os.path.join(os.path.dirname(__file__), 'static', 'admin.html')
    if os.path.exists(html_file):
        return FileResponse(html_file)
    else:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Z2API 管理界面</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .error { color: red; }
                .success { color: green; }
            </style>
        </head>
        <body>
            <h1>Z2API 管理界面</h1>
            <p class="error">管理界面文件未找到。请确保 static/admin.html 文件存在。</p>
        </body>
        </html>
        """, status_code=404)