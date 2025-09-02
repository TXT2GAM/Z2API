"""
Proxy handler for Z.AI API requests
"""

import json
import logging
import re
import time
from typing import AsyncGenerator, Dict, Any, Optional
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from config import settings
from cookie_manager import cookie_manager
from models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
)

logger = logging.getLogger(__name__)


class ProxyHandler:
    def __init__(self):
        # Configure httpx client with configurable timeout settings
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                settings.CONNECT_TIMEOUT, 
                read=settings.RESPONSE_TIMEOUT, 
                connect=settings.CONNECT_TIMEOUT, 
                write=30.0
            ),
            limits=httpx.Limits(
                max_connections=settings.MAX_CONNECTIONS, 
                max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS, 
                keepalive_expiry=settings.KEEPALIVE_EXPIRY
            ),
            http2=False,  # Disable HTTP/2 to reduce connection overhead
            verify=False   # Skip SSL verification to reduce overhead
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Ensure client is properly closed with explicit timeout
        try:
            if hasattr(self, 'client') and self.client:
                await self.client.aclose()
                # Force garbage collection of the client
                del self.client
        except Exception as e:
            logger.error(f"Error closing client: {e}")

    def transform_content(self, content: str) -> str:
        """Transform content by converting details tags to think tags and removing summary labels"""
        if not content:
            return content

        # Handle the complete thinking block replacement from edit_content
        # This pattern matches the complete thinking block that needs to be replaced
        # Pattern: 'true" duration="X">\n<summary>Thought for X seconds</summary>\n> thinking...\n</details>\nactual_answer'
        # Should become: '</think>\nactual_answer'
        
        # Match from 'true"' at start to '</details>' and replace with '</think>'
        if 'true"' in content and 'duration=' in content and '</details>' in content:
            content = re.sub(
                r'^true"[^>]*>\s*<summary>.*?</summary>\s*>\s*(.*?)\s*</details>\s*',
                r'</think>\n',
                content,
                flags=re.DOTALL | re.MULTILINE
            )
        
        # Handle simple tag replacements for partial content
        content = re.sub(r'<details[^>]*>', '<think>', content)
        content = content.replace('</details>', '</think>')

        # Remove <summary> tags and their content
        content = re.sub(r'<summary>.*?</summary>\s*', '', content, flags=re.DOTALL)

        # Clean up "> " prefixes in thinking content
        content = re.sub(r'<think>\s*>\s*', '<think>\n', content)
        content = re.sub(r'\n>\s*', '\n', content)

        return content.strip()

    async def proxy_request(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Proxy request to Z.AI API"""
        cookie = await cookie_manager.get_next_cookie()
        if not cookie:
            raise HTTPException(status_code=503, detail="No available cookies")

        # Transform model name and check if thinking is enabled
        is_thinking_model = request.model == settings.THINKING_MODEL_NAME
        target_model = (
            settings.UPSTREAM_MODEL
            if request.model in [settings.MODEL_NAME, settings.THINKING_MODEL_NAME]
            else request.model
        )

        # Determine if this should be a streaming response
        is_streaming = (
            request.stream if request.stream is not None else settings.DEFAULT_STREAM
        )

        # Note: Thinking content is always processed for both streaming and non-streaming

        # Prepare request data
        request_data = request.model_dump(exclude_none=True)
        request_data["model"] = target_model

        # Build request data based on actual Z.AI format from zai-messages.md
        import uuid

        request_data = {
            "stream": True,  # Always request streaming from Z.AI for processing
            "model": target_model,
            "messages": request_data["messages"],
            "background_tasks": {"title_generation": True, "tags_generation": True},
            "chat_id": str(uuid.uuid4()),
            "features": {
                "image_generation": False,
                "code_interpreter": False,
                "web_search": False,
                "auto_web_search": False,
                "enable_thinking": is_thinking_model,  # Enable thinking for GLM-4.5-thinking model
            },
            "id": str(uuid.uuid4()),
            "mcp_servers": ["deep-web-search"],
            "model_item": {"id": target_model, "name": "GLM-4.5", "owned_by": "openai"},
            "params": {},
            "tool_servers": [],
            "variables": {
                "{{USER_NAME}}": "User",
                "{{USER_LOCATION}}": "Unknown",
                "{{CURRENT_DATETIME}}": "2025-08-04 16:46:56",
            },
        }


        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cookie}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "Accept": "application/json, text/event-stream",
            "Accept-Language": "zh-CN",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "x-fe-version": "prod-fe-1.0.53",
            "Origin": "https://chat.z.ai",
            "Referer": "https://chat.z.ai/c/069723d5-060b-404f-992c-4705f1554c4c",
        }

        try:
            # Use client.stream() for TRUE streaming response - this is the key fix!
            async with self.client.stream(
                "POST",
                settings.UPSTREAM_URL,
                json=request_data,
                headers=headers,
                timeout=httpx.Timeout(settings.CONNECT_TIMEOUT, read=settings.RESPONSE_TIMEOUT)
            ) as response:

                if response.status_code == 401:
                    await cookie_manager.mark_cookie_failed(cookie)
                    raise HTTPException(status_code=401, detail="Invalid authentication")

                if response.status_code != 200:
                    # For streaming, we need to read the error response properly
                    try:
                        error_text = await response.aread()
                        error_detail = error_text.decode('utf-8')
                    except:
                        error_detail = f"HTTP {response.status_code}"

                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Upstream error: {error_detail}",
                    )

                await cookie_manager.mark_cookie_success(cookie)
                return {"response": response, "cookie": cookie}

        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            logger.error(f"Request error type: {type(e).__name__}")
            logger.error(f"Request URL: {settings.UPSTREAM_URL}")
            logger.error(f"Request timeout: {self.client.timeout}")
            await cookie_manager.mark_cookie_failed(cookie)
            raise HTTPException(
                status_code=503, detail=f"Upstream service unavailable: {str(e)}"
            )

    async def process_streaming_response(
        self, response: httpx.Response
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process streaming response with memory-efficient handling"""
        buffer = ""
        MAX_BUFFER_SIZE = 65536  # 64KB buffer limit to prevent memory overflow

        # Use aiter_text with controlled chunk size
        async for chunk in response.aiter_text(chunk_size=2048):
            if not chunk:
                continue

            # Check buffer size to prevent memory overflow
            if len(buffer) + len(chunk) > MAX_BUFFER_SIZE:
                logger.warning("Buffer size limit reached, clearing buffer")
                buffer = buffer[-32768:]  # Keep last 32KB

            buffer += chunk

            # Process complete lines immediately
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                buffer = buffer.lstrip()  # Trim leading whitespace to reduce memory

                if not line.startswith("data: "):
                    continue

                payload = line[6:].strip()
                if payload == "[DONE]":
                    return

                try:
                    parsed = json.loads(payload)

                    # Check for errors first
                    if parsed.get("error") or (parsed.get("data", {}).get("error")):
                        error_detail = (
                            parsed.get("error", {}).get("detail")
                            or parsed.get("data", {}).get("error", {}).get("detail")
                            or "Unknown error from upstream"
                        )
                        logger.error(f"Upstream error: {error_detail}")
                        # Instead of raising HTTPException, log and stop processing
                        # The error will be handled at the streaming level
                        return

                    # Clean up response data to reduce memory
                    if parsed.get("data"):
                        parsed["data"].pop("edit_index", None)
                        parsed["data"].pop("edit_content", None)

                    yield parsed

                except json.JSONDecodeError as e:
                    buffer = ""  # Clear buffer on JSON errors
                    continue

    async def handle_chat_completion(self, request: ChatCompletionRequest):
        """Handle chat completion request"""
        # Determine final streaming mode
        is_streaming = (
            request.stream if request.stream is not None else settings.DEFAULT_STREAM
        )

        if is_streaming:
            # For streaming responses, use direct streaming proxy
            return StreamingResponse(
                self.stream_proxy_response(request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            # For non-streaming responses, collect with memory limits
            chunks = []
            MAX_CONTENT_LENGTH = 1048576  # 1MB max content length
            current_length = 0
            
            async for chunk_data in self.stream_proxy_response(request):
                if chunk_data.startswith("data: ") and not chunk_data.startswith("data: [DONE]"):
                    try:
                        chunk_json = json.loads(chunk_data[6:])
                        content = chunk_json.get("choices", [{}])[0].get("delta", {}).get("content")
                        if content:
                            # Check memory limits
                            if current_length + len(content) > MAX_CONTENT_LENGTH:
                                logger.warning("Content length limit reached, stopping collection")
                                break
                            chunks.append(content)
                            current_length += len(content)
                    except:
                        continue

            # Combine all content and clear chunks list
            full_content = "".join(chunks)
            chunks.clear()  # Explicitly clear to free memory

            # Return as non-streaming response
            import time
            import uuid
            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:29]}",
                created=int(time.time()),
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": full_content},
                        "finish_reason": "stop",
                    }
                ],
            )

    async def stream_response(self, response: httpx.Response, model: str) -> AsyncGenerator[str, None]:
        """Generate TRUE streaming response in OpenAI format - real-time processing"""
        import uuid
        import time

        # Generate a unique completion ID
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        current_phase = None

        try:
            # Real-time streaming: process each chunk immediately as it arrives
            async for parsed in self.process_streaming_response(response):
                try:
                    data = parsed.get("data", {})
                    delta_content = data.get("delta_content", "")
                    phase = data.get("phase", "")

                    # Track phase changes
                    if phase != current_phase:
                        current_phase = phase

                    # Process and send all content with thinking transformation
                    if delta_content:
                        # Minimal transformation for real-time streaming
                        transformed_delta = delta_content

                        # Handle thinking tags for streaming
                        if '<details type="reasoning"' in transformed_delta and 'done="false"' in transformed_delta:
                            # Replace the complete opening pattern with <think>
                            transformed_delta = re.sub(
                                r'<details type="reasoning"[^>]*>\s*<summary>.*?</summary>\s*>\s*',
                                '<think>\n',
                                transformed_delta,
                                flags=re.DOTALL
                            )
                        else:
                            # Simple tag replacement for other cases
                            transformed_delta = re.sub(r'<details[^>]*>', '<think>', transformed_delta)
                            transformed_delta = transformed_delta.replace('</details>', '</think>')
                            # Remove summary tags
                            transformed_delta = re.sub(r'<summary>.*?</summary>\s*', '', transformed_delta, flags=re.DOTALL)
                            # Clean up "> " prefixes
                            transformed_delta = re.sub(r'\n>\s*', '\n', transformed_delta)

                        # Create and send OpenAI-compatible chunk immediately
                        openai_chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "content": transformed_delta
                                },
                                "finish_reason": None
                            }]
                        }

                        # Yield immediately for real-time streaming
                        yield f"data: {json.dumps(openai_chunk)}\n\n"

                except Exception as e:
                    logger.error(f"Error processing streaming chunk: {e}")
                    continue

            # Send final completion chunk
            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }

            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            # Send error in OpenAI format
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "server_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

    async def non_stream_response(
        self, response: httpx.Response, model: str
    ) -> ChatCompletionResponse:
        """Generate non-streaming response"""
        chunks = []
        async for parsed in self.process_streaming_response(response):
            chunks.append(parsed)

        if not chunks:
            raise HTTPException(status_code=500, detail="No response from upstream")

        # Aggregate content - prioritize edit_content for formatted thinking content
        edit_contents = []
        for chunk in chunks:
            edit_content = chunk.get("data", {}).get("edit_content", "")
            if edit_content:
                edit_contents.append(edit_content)
        
        if edit_contents:
            # Use the last edit_content as it contains the complete formatted content
            full_content = edit_contents[-1]
        else:
            # Fallback to delta_content if no edit_content found
            full_content = "".join(
                chunk.get("data", {}).get("delta_content", "") for chunk in chunks
            )

        # Apply content transformation (including think tag filtering)
        transformed_content = self.transform_content(full_content)

        # Create OpenAI-compatible response
        return ChatCompletionResponse(
            id=chunks[0].get("data", {}).get("id", "chatcmpl-unknown"),
            created=int(time.time()),
            model=model,
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": transformed_content},
                    "finish_reason": "stop",
                }
            ],
        )

    async def stream_proxy_response(self, request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        """TRUE streaming proxy - direct pass-through with minimal processing"""
        import uuid
        import time

        # Get cookie
        cookie = await cookie_manager.get_next_cookie()
        if not cookie:
            raise HTTPException(status_code=503, detail="No valid authentication available")

        # Prepare request data
        request_data_dict = request.model_dump(exclude_none=True)
        
        # Check if thinking is enabled
        is_thinking_model = request.model == settings.THINKING_MODEL_NAME
        target_model = "0727-360B-API"  # Map GLM-4.5 and GLM-4.5-thinking to Z.AI model

        # Build Z.AI request format
        request_data = {
            "stream": True,  # Always request streaming from Z.AI
            "model": target_model,
            "messages": request_data_dict["messages"],
            "background_tasks": {
                "title_generation": True,
                "tags_generation": True
            },
            "chat_id": str(uuid.uuid4()),
            "features": {
                "image_generation": False,
                "code_interpreter": False,
                "web_search": False,
                "auto_web_search": False,
                "enable_thinking": is_thinking_model,  # Enable thinking for GLM-4.5-thinking model
            },
            "id": str(uuid.uuid4()),
            "mcp_servers": ["deep-web-search"],
            "model_item": {
                "id": target_model,
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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cookie}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "Accept": "application/json, text/event-stream",
            "Accept-Language": "zh-CN",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "x-fe-version": "prod-fe-1.0.53",
            "Origin": "https://chat.z.ai",
            "Referer": "https://chat.z.ai/c/069723d5-060b-404f-992c-4705f1554c4c",
        }

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        current_phase = None

        try:
            # Create a new client for this streaming request to avoid conflicts
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.CONNECT_TIMEOUT, read=settings.RESPONSE_TIMEOUT),
                limits=httpx.Limits(
                    max_connections=settings.MAX_CONNECTIONS, 
                    max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS, 
                    keepalive_expiry=settings.KEEPALIVE_EXPIRY
                ),
                http2=True
            ) as stream_client:
                async with stream_client.stream(
                    "POST",
                    settings.UPSTREAM_URL,
                    json=request_data,
                    headers=headers
                ) as response:

                    if response.status_code == 401:
                        await cookie_manager.mark_cookie_failed(cookie)
                        # Instead of raising HTTPException, yield an error message and return
                        error_data = {
                            "error": {
                                "message": "Invalid authentication",
                                "type": "authentication_error",
                                "code": 401
                            }
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    if response.status_code != 200:
                        await cookie_manager.mark_cookie_failed(cookie)
                        # Instead of raising HTTPException, yield an error message and return
                        error_data = {
                            "error": {
                                "message": f"Upstream error: HTTP {response.status_code}",
                                "type": "upstream_error",
                                "code": response.status_code
                            }
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    await cookie_manager.mark_cookie_success(cookie)

                    # Process streaming response with memory-efficient handling
                    buffer = ""
                    MAX_BUFFER_SIZE = 65536  # 64KB buffer limit
                    async for chunk in response.aiter_text(chunk_size=2048):
                        if not chunk:
                            continue

                        # Prevent buffer overflow
                        if len(buffer) + len(chunk) > MAX_BUFFER_SIZE:
                            logger.warning("Stream buffer limit reached, clearing buffer")
                            buffer = buffer[-16384:]  # Keep last 16KB

                        buffer += chunk

                        # Process complete lines immediately
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            buffer = buffer.lstrip()  # Reduce memory usage

                            if not line.startswith("data: "):
                                continue

                            payload = line[6:].strip()
                            if payload == "[DONE]":
                                # Send final chunk and done
                                final_chunk = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": request.model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(final_chunk)}\n\n"
                                yield "data: [DONE]\n\n"
                                return

                            try:
                                parsed = json.loads(payload)
                                data = parsed.get("data", {})
                                delta_content = data.get("delta_content", "")
                                edit_content = data.get("edit_content", "")
                                phase = data.get("phase", "")

                                # Track phase changes
                                if phase != current_phase:
                                    current_phase = phase

                                # Handle edit_content for complete thinking block replacement
                                if edit_content and phase == "answer":
                                    # This is the complete thinking block replacement
                                    # Apply full transformation to edit_content
                                    transformed_delta = self.transform_content(edit_content)
                                    # For edit_content, we need to send it as delta
                                    content_to_send = transformed_delta
                                else:
                                    # Process delta_content for incremental updates
                                    content_to_send = delta_content

                                # Process and send content
                                if content_to_send:
                                    # Transform thinking tags for streaming
                                    transformed_delta = content_to_send
                                    
                                    # Handle thinking start pattern: <details...><summary>Thinking…</summary>> 
                                    if '<details type="reasoning"' in transformed_delta and 'done="false"' in transformed_delta:
                                        # Replace the complete opening pattern with <think>
                                        transformed_delta = re.sub(
                                            r'<details type="reasoning"[^>]*>\s*<summary>.*?</summary>\s*>\s*',
                                            '<think>\n',
                                            transformed_delta,
                                            flags=re.DOTALL
                                        )
                                    else:
                                        # Simple tag replacement for other cases
                                        transformed_delta = re.sub(r'<details[^>]*>', '<think>', transformed_delta)
                                        transformed_delta = transformed_delta.replace('</details>', '</think>')
                                        # Remove summary tags
                                        transformed_delta = re.sub(r'<summary>.*?</summary>\s*', '', transformed_delta, flags=re.DOTALL)
                                        # Clean up "> " prefixes
                                        transformed_delta = re.sub(r'\n>\s*', '\n', transformed_delta)

                                    # Create and send OpenAI-compatible chunk immediately
                                    openai_chunk = {
                                        "id": completion_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": request.model,
                                        "choices": [{
                                            "index": 0,
                                            "delta": {
                                                "content": transformed_delta
                                            },
                                            "finish_reason": None
                                        }]
                                    }

                                    # Yield immediately for real-time streaming
                                    yield f"data: {json.dumps(openai_chunk)}\n\n"

                            except json.JSONDecodeError:
                                buffer = ""  # Clear buffer on JSON errors
                                continue  # Skip non-JSON lines

        except httpx.RequestError as e:
            logger.error(f"Streaming request error: {e}")
            await cookie_manager.mark_cookie_failed(cookie)
            raise HTTPException(status_code=503, detail=f"Upstream service unavailable: {str(e)}")
