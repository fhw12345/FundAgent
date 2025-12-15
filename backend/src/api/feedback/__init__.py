"""
Feedback API endpoints for user feature requests and bug reports.

This module provides REST API endpoints for the Feedback & Community Roadmap platform.
The endpoints are split into logical modules:
- crud: Core CRUD operations (create, list, get, vote)
- upload: Image upload functionality
- comments: Comment management
- admin: Admin-only operations (status updates, exports)
"""

from fastapi import APIRouter

from . import admin, comments, crud, upload

# Main router that aggregates all sub-routers
router = APIRouter(prefix="/api/feedback", tags=["feedback"])

# Include sub-routers
router.include_router(crud.router)
router.include_router(upload.router)
router.include_router(comments.router)
router.include_router(admin.router)

__all__ = ["router"]
