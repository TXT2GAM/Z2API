"""
Management API endpoints for Z.AI Proxy
"""
import os
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import set_key, get_key, unset_key

from config import settings
from cookie_manager import cookie_manager

router = APIRouter()

class CookieUpdateRequest(BaseModel):
    cookies: List[str]
    
class ConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    show_think_tags: Optional[bool] = None
    default_stream: Optional[bool] = None
    log_level: Optional[str] = None
    max_requests_per_minute: Optional[int] = None
    port: Optional[int] = None
    host: Optional[str] = None
    auto_refresh_tokens: Optional[bool] = None
    refresh_check_interval: Optional[int] = None

@router.get("/api/cookies")
async def get_cookies():
    """获取当前 Cookie 列表"""
    return {
        "cookies": settings.COOKIES,
        "count": len(settings.COOKIES),
        "failed_count": len(cookie_manager.failed_cookies),
        "failed_cookies": list(cookie_manager.failed_cookies)
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
    
    # 更新 cookie_manager
    cookie_manager.cookies = valid_cookies
    cookie_manager.failed_cookies.clear()
    cookie_manager.current_index = 0
    
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
    
    # 更新 cookie_manager
    cookie_manager.cookies = []
    cookie_manager.failed_cookies.clear()
    cookie_manager.current_index = 0
    
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

@router.get("/api/config")
async def get_config():
    """获取当前配置"""
    return {
        "api_key": settings.API_KEY,
        "show_think_tags": settings.SHOW_THINK_TAGS,
        "default_stream": settings.DEFAULT_STREAM,
        "log_level": settings.LOG_LEVEL,
        "max_requests_per_minute": settings.MAX_REQUESTS_PER_MINUTE,
        "port": settings.PORT,
        "host": settings.HOST,
        "auto_refresh_tokens": settings.AUTO_REFRESH_TOKENS,
        "refresh_check_interval": settings.REFRESH_CHECK_INTERVAL,
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
        
        # 设置内存中的值
        if hasattr(settings, env_key):
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
        # 更新 cookie_manager
        cookie_manager.cookies = settings.COOKIES
        cookie_manager.failed_cookies.clear()
        cookie_manager.current_index = 0
        
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