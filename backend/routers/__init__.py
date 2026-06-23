from .recommendation import router as recommendation_router
from .config import router as config_router
from .playback import router as playback_router
from .health import router as health_router

__all__ = ["recommendation_router", "config_router", "playback_router", "health_router"]
