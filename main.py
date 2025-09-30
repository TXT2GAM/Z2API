"""
Z.AI Proxy - OpenAI-compatible API for Z.AI
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from models import ChatCompletionRequest, ModelsResponse, ModelInfo, ErrorResponse
from proxy_handler import ProxyHandler
from cookie_manager import cookie_manager
from admin_api import router as admin_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer(auto_error=False)

async def auto_refresh_periodic():
    """Periodic auto-refresh task for tokens"""
    while True:
        try:
            if settings.AUTO_REFRESH_TOKENS:
                logger.info("Starting periodic auto-refresh of tokens")
                result = await cookie_manager.batch_refresh_tokens()
                if result["refreshed_count"] > 0:
                    # Update settings with refreshed cookies
                    settings.COOKIES = cookie_manager.cookies
                    
                    # Update environment file if it exists
                    import os
                    from dotenv import set_key
                    env_file = os.path.join(os.getcwd(), '.env')
                    if os.path.exists(env_file):
                        try:
                            set_key(env_file, 'Z_AI_COOKIES', ','.join(settings.COOKIES))
                            logger.info("Updated environment file with refreshed cookies")
                        except Exception as e:
                            logger.warning(f"Could not update .env file: {e}")
                    
                    logger.info(f"Auto-refresh completed: {result['refreshed_count']} tokens refreshed")
                else:
                    logger.info(f"Auto-refresh completed: no tokens needed refreshing")
            
            # Wait for the configured interval
            await asyncio.sleep(settings.REFRESH_CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Error in auto-refresh task: {e}")
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Start background tasks
    health_check_task = asyncio.create_task(cookie_manager.periodic_health_check())
    
    # Start auto-refresh task if enabled
    auto_refresh_task = None
    if settings.AUTO_REFRESH_TOKENS:
        logger.info("Auto-refresh tokens enabled, starting background task")
        auto_refresh_task = asyncio.create_task(auto_refresh_periodic())
    
    try:
        yield
    finally:
        # Cleanup
        health_check_task.cancel()
        try:
            await health_check_task
        except asyncio.CancelledError:
            pass
        
        if auto_refresh_task:
            auto_refresh_task.cancel()
            try:
                await auto_refresh_task
            except asyncio.CancelledError:
                pass

# Create FastAPI app
app = FastAPI(
    title="Z.AI Proxy",
    description="OpenAI-compatible API proxy for Z.AI",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include admin API routes
app.include_router(admin_router, prefix="", tags=["admin"])

async def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify authentication with fixed API key"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Verify the API key matches our configured key
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return credentials.credentials

@app.get("/v1/models", response_model=ModelsResponse)
async def list_models():
    """List available models"""
    models = [
        ModelInfo(
            id=settings.MODEL_ID,
            object="model",
            owned_by="z-ai"
        ),
        ModelInfo(
            id=settings.THINKING_MODEL_ID,
            object="model",
            owned_by="z-ai"
        ),
        ModelInfo(
            id=settings.MODEL_46_ID,
            object="model",
            owned_by="z-ai"
        ),
        ModelInfo(
            id=settings.THINKING_MODEL_46_ID,
            object="model",
            owned_by="z-ai"
        )
    ]
    return ModelsResponse(data=models)

@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    auth_token: str = Depends(verify_auth)
):
    """Create chat completion"""
    try:
        # Check if cookies are configured
        if not settings or not settings.COOKIES:
            raise HTTPException(
                status_code=503,
                detail="Service unavailable: No Z.AI cookies configured. Please set Z_AI_COOKIES environment variable."
            )

        # Validate model
        if request.model not in [
            settings.MODEL_NAME,
            settings.THINKING_MODEL_NAME,
            settings.MODEL_46_NAME,
            settings.THINKING_MODEL_46_NAME
        ]:
            supported_models = [
                settings.MODEL_NAME,
                settings.THINKING_MODEL_NAME,
                settings.MODEL_46_NAME,
                settings.THINKING_MODEL_46_NAME
            ]
            raise HTTPException(
                status_code=400,
                detail=f"Model '{request.model}' not supported. Use one of: {', '.join(supported_models)}"
            )

        async with ProxyHandler() as handler:
            return await handler.handle_chat_completion(request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "model": settings.MODEL_NAME}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "invalid_request_error",
                "code": exc.status_code
            }
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower()
    )
