"""
Cookie pool manager for Z.AI tokens with round-robin rotation
"""
import asyncio
import logging
from typing import List, Optional
from asyncio import Lock
import httpx
from config import settings

logger = logging.getLogger(__name__)

class CookieManager:
    def __init__(self, cookies: List[str]):
        self.cookies = cookies or []
        self.current_index = 0
        self.lock = Lock()
        self.failed_cookies = set()

        if self.cookies:
            logger.info(f"Initialized CookieManager with {len(cookies)} cookies")
        else:
            logger.warning("CookieManager initialized with no cookies")
    
    async def get_next_cookie(self) -> Optional[str]:
        """Get the next available cookie using round-robin"""
        if not self.cookies:
            return None

        async with self.lock:
            attempts = 0
            while attempts < len(self.cookies):
                cookie = self.cookies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.cookies)

                # Skip failed cookies
                if cookie not in self.failed_cookies:
                    return cookie

                attempts += 1

            # All cookies failed, reset failed set and try again
            if self.failed_cookies:
                logger.warning(f"All {len(self.cookies)} cookies failed, resetting failed set and retrying")
                self.failed_cookies.clear()
                return self.cookies[0]

            return None
    
    async def mark_cookie_failed(self, cookie: str):
        """Mark a cookie as failed"""
        async with self.lock:
            self.failed_cookies.add(cookie)
            logger.warning(f"Marked cookie as failed: {cookie[:20]}...")
    
    async def mark_cookie_success(self, cookie: str):
        """Mark a cookie as working (remove from failed set)"""
        async with self.lock:
            if cookie in self.failed_cookies:
                self.failed_cookies.discard(cookie)
                logger.info(f"Cookie recovered: {cookie[:20]}...")
    
    async def health_check(self, cookie: str) -> bool:
        """Check if a cookie is still valid"""
        try:
            # Use a shared client configuration for health checks
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0, read=5.0),
                limits=httpx.Limits(max_connections=3, max_keepalive_connections=1, keepalive_expiry=15),
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
                        "Authorization": f"Bearer {cookie}",
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
                        if await self.health_check(cookie):
                            await self.mark_cookie_success(cookie)
                            logger.info(f"Cookie recovered: {cookie[:20]}...")
                        else:
                            logger.debug(f"Cookie still failed: {cookie[:20]}...")

                # Wait 10 minutes before next check (reduced frequency)
                await asyncio.sleep(600)
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}")
                logger.error(f"Periodic health check error type: {type(e).__name__}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

# Global cookie manager instance
cookie_manager = CookieManager(settings.COOKIES if settings else [])
