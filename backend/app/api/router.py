from fastapi import APIRouter

from app.api.routes import acts, auth, dashboard, docs, files, items, objects, sections, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(objects.router)
api_router.include_router(sections.router)
api_router.include_router(files.router)
api_router.include_router(items.router)
api_router.include_router(docs.router)
api_router.include_router(acts.router)
api_router.include_router(dashboard.router)
