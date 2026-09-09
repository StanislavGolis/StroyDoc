from fastapi import APIRouter

from app.api.routes import auth, files, items, objects, sections, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(objects.router)
api_router.include_router(sections.router)
api_router.include_router(files.router)
api_router.include_router(items.router)
