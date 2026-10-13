"""
Routes package for the API interface.
This package contains all the route definitions for the API.
"""

from app.interfaces.api.routes.base import root_router
from app.interfaces.api.routes.router import main_router as router

__all__ = ["router", "root_router"]
