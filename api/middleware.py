from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

logger = logging.getLogger(__name__)

class PerformanceTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, req: Request, call_next):
        t0 = time.perf_counter()
        
        res = await call_next(req)
        
        # calculate time
        t = (time.perf_counter() - t0) * 1000
        res.headers['X-Aura-Process-Time-ms'] = str(round(t, 2))
        
        logger.info(f"{req.method} {req.url.path} - {t:.2f}ms")
        
        return res