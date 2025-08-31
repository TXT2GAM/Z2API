"""
Cookie pool manager for Z.AI tokens with round-robin rotation
"""
import asyncio
import logging
import json
from typing import List, Optional, Dict, Any
from asyncio import Lock
import httpx
import aiohttp
from config import settings

logger = logging.getLogger(__name__)

class CookieManager:
    def __init__(self, cookies: List[str]):
        self.cookies = cookies or []
        self.cookie_info = {}  # 存储cookie的额外信息
        self.current_index = 0
        self.lock = Lock()
        self.failed_cookies = set()

        # 解析cookies，提取账号密码信息
        self._parse_cookies()
        
        if self.cookies:
            logger.info(f"Initialized CookieManager with {len(cookies)} cookies")
        else:
            logger.warning("CookieManager initialized with no cookies")
    
    def _parse_cookies(self):
        """解析cookies，提取账号密码信息"""
        for cookie in self.cookies:
            self.cookie_info[cookie] = {
                'email': '',
                'password': '',
                'has_credentials': False
            }
            
            # 检查是否包含分隔符
            if '----' in cookie:
                parts = cookie.split('----')
                if len(parts) == 3:
                    # 格式: email----password----token
                    email, password, token = parts
                    self.cookie_info[token] = {
                        'email': email,
                        'password': password,
                        'has_credentials': True,
                        'raw_cookie': cookie
                    }
                elif len(parts) == 2:
                    # 格式: email----password，需要后续获取token
                    email, password = parts
                    self.cookie_info[cookie] = {
                        'email': email,
                        'password': password,
                        'has_credentials': True,
                        'needs_token': True,
                        'raw_cookie': cookie
                    }
    
    def _extract_token(self, cookie: str) -> Optional[str]:
        """Extract the actual token from cookie string"""
        if not cookie:
            return None
            
        # If it's a full format cookie (email----password----token)
        if '----' in cookie:
            parts = cookie.split('----')
            if len(parts) >= 3:
                return parts[-1]  # Return the last part (actual token)
        
        # If it's already a pure token, return as is
        return cookie
    
    async def get_next_cookie(self) -> Optional[str]:
        """Get the next available cookie token using round-robin"""
        if not self.cookies:
            return None

        async with self.lock:
            attempts = 0
            while attempts < len(self.cookies):
                cookie = self.cookies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.cookies)

                # Skip failed cookies
                if cookie not in self.failed_cookies:
                    # Extract the actual token (last part after ----)
                    actual_token = self._extract_token(cookie)
                    if actual_token:
                        return actual_token

                attempts += 1

            # All cookies failed, reset failed set and try again
            if self.failed_cookies:
                logger.warning(f"All {len(self.cookies)} cookies failed, resetting failed set and retrying")
                self.failed_cookies.clear()
                first_cookie = self.cookies[0]
                return self._extract_token(first_cookie)

            return None
    
    async def mark_cookie_failed(self, token: str):
        """Mark a cookie token as failed"""
        async with self.lock:
            # Find the full cookie that contains this token
            full_cookie = self._find_full_cookie_by_token(token)
            if full_cookie:
                self.failed_cookies.add(full_cookie)
                logger.warning(f"Marked cookie as failed: {full_cookie[:20]}...")
            else:
                logger.warning(f"Could not find full cookie for token: {token[:20]}...")
    
    async def mark_cookie_success(self, token: str):
        """Mark a cookie token as working (remove from failed set)"""
        async with self.lock:
            # Find the full cookie that contains this token
            full_cookie = self._find_full_cookie_by_token(token)
            if full_cookie and full_cookie in self.failed_cookies:
                self.failed_cookies.discard(full_cookie)
                logger.info(f"Cookie recovered: {full_cookie[:20]}...")
    
    def _find_full_cookie_by_token(self, token: str) -> Optional[str]:
        """Find the full cookie string that contains the given token"""
        for full_cookie in self.cookies:
            if full_cookie == token or self._extract_token(full_cookie) == token:
                return full_cookie
        return None
    
    async def health_check(self, cookie: str) -> bool:
        """Check if a cookie is still valid"""
        try:
            # Extract the actual token from cookie string
            actual_token = self._extract_token(cookie)
            if not actual_token:
                return False
            
            # Use a shared client configuration for health checks
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0, read=5.0),
                limits=httpx.Limits(
                    max_connections=settings.MAX_CONNECTIONS, 
                    max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS, 
                    keepalive_expiry=settings.KEEPALIVE_EXPIRY
                ),
                http2=False,
                verify=False
            ) as client:
                # Use the same payload format as actual requests
                import uuid
                test_payload = {
                    "stream": True,
                    "model": "0727-360B-API",
                    "messages": [{"role": "user", "content": "hi"}],
                    "background_tasks": {
                        "title_generation": False,
                        "tags_generation": False
                    },
                    "chat_id": str(uuid.uuid4()),
                    "features": {
                        "image_generation": False,
                        "code_interpreter": False,
                        "web_search": False,
                        "auto_web_search": False
                    },
                    "id": str(uuid.uuid4()),
                    "mcp_servers": [],
                    "model_item": {
                        "id": "0727-360B-API",
                        "name": "GLM-4.5",
                        "owned_by": "openai"
                    },
                    "params": {},
                    "tool_servers": [],
                    "variables": {
                        "{{USER_NAME}}": "User",
                        "{{USER_LOCATION}}": "Unknown",
                        "{{CURRENT_DATETIME}}": "2025-08-04 16:46:56"
                    }
                }
                response = await client.post(
                    "https://chat.z.ai/api/chat/completions",
                    headers={
                        "Authorization": f"Bearer {actual_token}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                        "Accept": "application/json, text/event-stream",
                        "Accept-Language": "zh-CN",
                        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"macOS"',
                        "x-fe-version": "prod-fe-1.0.53",
                        "Origin": "https://chat.z.ai",
                        "Referer": "https://chat.z.ai/c/069723d5-060b-404f-992c-4705f1554c4c"
                    },
                    json=test_payload,
                    timeout=10.0
                )
                # Consider 200 as success
                is_healthy = response.status_code == 200
                if not is_healthy:
                    logger.debug(f"Health check failed for cookie {cookie[:20]}...: HTTP {response.status_code}")
                else:
                    logger.debug(f"Health check passed for cookie {cookie[:20]}...")

                return is_healthy
        except Exception as e:
            logger.debug(f"Health check failed for cookie {cookie[:20]}...: {e}")
            logger.debug(f"Health check error type: {type(e).__name__}")
            return False
    
    async def periodic_health_check(self):
        """Periodically check all cookies health"""
        while True:
            try:
                # Only check if we have cookies and some are marked as failed
                if self.cookies and self.failed_cookies:
                    logger.info(f"Running health check for {len(self.failed_cookies)} failed cookies")

                    for cookie in list(self.failed_cookies):  # Create a copy to avoid modification during iteration
                        token = self._extract_token(cookie)
                        if token and await self.health_check(token):
                            await self.mark_cookie_success(token)
                            logger.info(f"Cookie recovered: {cookie[:20]}...")
                        else:
                            logger.debug(f"Cookie still failed: {cookie[:20]}...")

                # Wait 10 minutes before next check (reduced frequency)
                await asyncio.sleep(600)
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}")
                logger.error(f"Periodic health check error type: {type(e).__name__}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def refresh_token(self, email: str, password: str) -> Optional[str]:
        """通过账号密码刷新token"""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                payload = {
                    "email": email,
                    "password": password
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
                }
                
                async with session.post(
                    "https://chat.z.ai/api/v1/auths/signin",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        token = data.get("token")
                        if token:
                            logger.info(f"Successfully refreshed token for {email}")
                            return token
                        else:
                            logger.error(f"No token in response for {email}")
                            return None
                    else:
                        logger.error(f"Failed to refresh token for {email}: HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error refreshing token for {email}: {e}")
            return None
    
    async def batch_refresh_tokens(self, max_concurrent: int = 20) -> Dict[str, Any]:
        """批量刷新tokens"""
        refresh_tasks = []
        refreshed_count = 0
        failed_count = 0
        
        # 收集需要刷新的cookies
        cookies_to_refresh = []
        
        for cookie, info in self.cookie_info.items():
            # 只处理有账号密码信息的cookie
            if info.get('has_credentials') and info.get('email') and info.get('password'):
                # 获取密码（现在显示的是真实密码）
                password = info.get('password')
                
                # 如果cookie格式是email----password----token，需要使用真实的token
                refresh_cookie = cookie
                if info.get('raw_cookie') and info.get('raw_cookie') != cookie:
                    refresh_cookie = info.get('raw_cookie')
                
                # 确保有密码
                if password:
                    cookies_to_refresh.append((refresh_cookie, info['email'], password))
        
        if not cookies_to_refresh:
            return {
                "success": True,
                "message": "没有需要刷新的令牌",
                "refreshed_count": 0,
                "failed_count": 0,
                "total_count": 0,
                "updated_cookies": []
            }
        
        total_count = len(cookies_to_refresh)
        logger.info(f"Starting batch refresh for {total_count} tokens")
        
        # 创建并发任务
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def refresh_with_semaphore(cookie, email, password):
            async with semaphore:
                new_token = await self.refresh_token(email, password)
                return cookie, new_token
        
        # 提交所有任务
        for cookie, email, password in cookies_to_refresh:
            task = refresh_with_semaphore(cookie, email, password)
            refresh_tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*refresh_tasks, return_exceptions=True)
        
        # 处理结果
        updated_cookies = []
        old_cookies_list = self.cookies.copy()
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Refresh task failed: {result}")
                failed_count += 1
                continue
            
            old_cookie, new_token = result
            if new_token:
                # 刷新成功，更新cookie列表
                # 需要找到old_cookie在cookie列表中的位置
                cookie_found = False
                
                # 检查old_cookie是否直接在cookie列表中
                if old_cookie in old_cookies_list:
                    index = old_cookies_list.index(old_cookie)
                    cookie_found = True
                    cookie_index = index
                else:
                    # 如果不是，可能是email----password----token格式，需要找到对应的token
                    for i, cookie in enumerate(old_cookies_list):
                        if cookie == old_cookie or (self.cookie_info.get(cookie) and self.cookie_info[cookie].get('raw_cookie') == old_cookie):
                            cookie_found = True
                            cookie_index = i
                            break
                
                if cookie_found:
                    # 找到并替换旧的cookie，存储完整格式
                    email = ''
                    real_password = ''
                    
                    # 优先从当前cookie_info中获取信息
                    if old_cookie in self.cookie_info:
                        old_info = self.cookie_info[old_cookie].copy()
                        email = old_info['email']
                        real_password = old_info['password']
                    else:
                        # 查找包含这个raw_cookie的entry
                        for cookie_key, info in self.cookie_info.items():
                            if info.get('raw_cookie') == old_cookie:
                                email = info['email']
                                real_password = info['password']
                                break
                    
                    # 如果仍然找不到信息，尝试从原始格式解析
                    if not email and '----' in old_cookie:
                        parts = old_cookie.split('----')
                        if len(parts) >= 2:
                            email = parts[0]
                            real_password = parts[1]
                    
                    if email:
                        # 创建完整格式的新cookie
                        full_format_cookie = f"{email}----{real_password}----{new_token}"
                        
                        # 更新cookie列表为完整格式
                        old_cookies_list[cookie_index] = full_format_cookie
                        
                        # 创建新的cookie_info
                        new_info = {
                            'email': email,
                            'password': real_password,  # 显示真实密码
                            'has_credentials': True,
                            'raw_cookie': full_format_cookie,
                            'token': new_token
                        }
                        self.cookie_info[full_format_cookie] = new_info
                        self.cookie_info[new_token] = new_info
                        
                        # 清理旧的entry
                        if old_cookie in self.cookie_info and old_cookie != new_token:
                            del self.cookie_info[old_cookie]
                        
                        updated_cookies.append(full_format_cookie)
                        refreshed_count += 1
                    else:
                        # 如果找不到邮箱信息，但原始cookie是完整格式，保持完整格式
                        if '----' in old_cookie:
                            parts = old_cookie.split('----')
                            if len(parts) >= 3:
                                # 已经是完整格式，更新token
                                email = parts[0] or 'unknown'
                                real_password = parts[1] or 'unknown'
                                full_format_cookie = f"{email}----{real_password}----{new_token}"
                                old_cookies_list[cookie_index] = full_format_cookie
                                
                                # 创建新的cookie_info
                                new_info = {
                                    'email': email,
                                    'password': real_password,
                                    'has_credentials': True,
                                    'raw_cookie': full_format_cookie,
                                    'token': new_token
                                }
                                self.cookie_info[full_format_cookie] = new_info
                                self.cookie_info[new_token] = new_info
                                
                                updated_cookies.append(full_format_cookie)
                                refreshed_count += 1
                            else:
                                # 不是完整格式，转换为完整格式
                                full_format_cookie = f"unknown----unknown----{new_token}"
                                old_cookies_list[cookie_index] = full_format_cookie
                                
                                self.cookie_info[full_format_cookie] = {
                                    'email': 'unknown',
                                    'password': 'unknown',
                                    'has_credentials': True,
                                    'raw_cookie': full_format_cookie,
                                    'token': new_token
                                }
                                self.cookie_info[new_token] = self.cookie_info[full_format_cookie]
                                
                                updated_cookies.append(full_format_cookie)
                                refreshed_count += 1
                        else:
                            # 纯token格式，转换为完整格式
                            full_format_cookie = f"unknown----unknown----{new_token}"
                            old_cookies_list[cookie_index] = full_format_cookie
                            
                            self.cookie_info[full_format_cookie] = {
                                'email': 'unknown',
                                'password': 'unknown',
                                'has_credentials': True,
                                'raw_cookie': full_format_cookie,
                                'token': new_token
                            }
                            self.cookie_info[new_token] = self.cookie_info[full_format_cookie]
                            
                            updated_cookies.append(full_format_cookie)
                            refreshed_count += 1
                    
                    email_info = email if email else 'unknown'
                    logger.info(f"Updated token for {email_info}")
                else:
                    logger.warning(f"Cookie not found in list: {old_cookie}")
                    failed_count += 1
            else:
                # 刷新失败，保持原样
                email_info = self.cookie_info.get(old_cookie, {}).get('email', 'unknown')
                if email_info == 'unknown':
                    # 尝试从raw_cookie中查找
                    for info in self.cookie_info.values():
                        if info.get('raw_cookie') == old_cookie:
                            email_info = info.get('email', 'unknown')
                            break
                logger.error(f"Failed to refresh token for {email_info}")
                failed_count += 1
        
        # 更新cookies列表
        async with self.lock:
            self.cookies = old_cookies_list
        
        return {
            "success": True,
            "message": f"批量刷新完成: {refreshed_count} 个刷新成功, {failed_count} 个刷新失败",
            "refreshed_count": refreshed_count,
            "failed_count": failed_count,
            "total_count": total_count,
            "updated_cookies": updated_cookies
        }

    async def refresh_single_token(self, cookie_value: str) -> Dict[str, Any]:
        """刷新单个Cookie的token"""
        try:
            # 智能查找cookie信息
            cookie_info = self._find_cookie_info_with_credentials(cookie_value)
            
            if not cookie_info:
                return {
                    "success": False,
                    "message": "该Cookie没有账号密码信息，无法刷新",
                    "refreshed_count": 0
                }
            
            email = cookie_info['email']
            password = cookie_info['password']
            
            # 刷新token
            new_token = await self.refresh_token(email, password)
            if not new_token:
                return {
                    "success": False,
                    "message": "刷新token失败",
                    "refreshed_count": 0
                }
            
            # 更新cookie列表
            old_cookies_list = self.cookies.copy()
            cookie_found = False
            cookie_index = -1
            
            # 查找并替换旧的cookie
            if cookie_value in old_cookies_list:
                index = old_cookies_list.index(cookie_value)
                cookie_found = True
                cookie_index = index
            else:
                # 查找包含这个raw_cookie的entry
                for i, cookie in enumerate(old_cookies_list):
                    if cookie == cookie_value or (self.cookie_info.get(cookie) and self.cookie_info[cookie].get('raw_cookie') == cookie_value):
                        cookie_found = True
                        cookie_index = i
                        break
            
            if not cookie_found:
                return {
                    "success": False,
                    "message": "未找到对应的Cookie",
                    "refreshed_count": 0
                }
            
            # 创建完整格式的新cookie
            full_format_cookie = f"{email}----{password}----{new_token}"
            
            # 更新cookie列表
            old_cookies_list[cookie_index] = full_format_cookie
            
            # 创建新的cookie_info
            new_info = {
                'email': email,
                'password': password,
                'has_credentials': True,
                'raw_cookie': full_format_cookie,
                'token': new_token
            }
            self.cookie_info[full_format_cookie] = new_info
            self.cookie_info[new_token] = new_info
            
            # 清理旧的entry
            if cookie_value in self.cookie_info and cookie_value != new_token:
                del self.cookie_info[cookie_value]
            
            # 更新cookies列表
            async with self.lock:
                self.cookies = old_cookies_list
            
            logger.info(f"Single token refreshed for {email}")
            
            return {
                "success": True,
                "message": f"单个Cookie刷新成功: {email}",
                "refreshed_count": 1
            }
            
        except Exception as e:
            logger.error(f"Single token refresh failed: {e}")
            return {
                "success": False,
                "message": f"刷新失败: {str(e)}",
                "refreshed_count": 0
            }
    
    def _find_cookie_info_with_credentials(self, cookie_value: str) -> Optional[Dict[str, Any]]:
        """智能查找包含账号密码信息的cookie对象"""
        if not cookie_value:
            return None
            
        # 1. 尝试直接查找
        cookie_info = self.get_cookie_info(cookie_value)
        if cookie_info.get('has_credentials') and cookie_info.get('email') and cookie_info.get('password'):
            return cookie_info
        
        # 2. 尝试提取token后查找
        token_from_value = self._extract_token(cookie_value)
        if token_from_value and token_from_value != cookie_value:
            cookie_info = self.get_cookie_info(token_from_value)
            if cookie_info.get('has_credentials') and cookie_info.get('email') and cookie_info.get('password'):
                return cookie_info
        
        # 3. 遍历所有cookie_info，查找匹配的raw_cookie或token
        for cookie_key, info in self.cookie_info.items():
            if (info.get('raw_cookie') == cookie_value or 
                info.get('token') == cookie_value or
                (info.get('has_credentials') and cookie_value in [cookie_key, info.get('raw_cookie'), info.get('token')])):
                if info.get('has_credentials') and info.get('email') and info.get('password'):
                    return info
        
        # 4. 最后尝试：如果cookie_value是完整格式，手动解析
        if '----' in cookie_value:
            parts = cookie_value.split('----')
            if len(parts) >= 2:
                # 至少有邮箱和密码
                return {
                    'email': parts[0],
                    'password': parts[1],
                    'has_credentials': True,
                    'raw_cookie': cookie_value
                }
        
        return None
    
    def get_cookie_info(self, cookie: str) -> Dict[str, Any]:
        """获取cookie的附加信息"""
        return self.cookie_info.get(cookie, {
            'email': '',
            'password': '',
            'has_credentials': False
        })
    
    def update_cookies(self, new_cookies: List[str]):
        """更新cookies列表"""
        self.cookies = new_cookies
        self.cookie_info = {}
        self._parse_cookies()
        logger.info(f"Updated cookies: {len(new_cookies)} cookies loaded")

# Global cookie manager instance
cookie_manager = CookieManager(settings.COOKIES if settings else [])
