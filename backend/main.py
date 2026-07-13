from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.admin.adminUsers import router as admin_users_router
from backend.routers.admin.adminJobs import router as admin_jobs_router
from backend.routers.admin.adminTasks import router as admin_tasks_router
from backend.routers.admin.adminSystem import router as admin_system_router
from backend.routers.admin.adminVideoManagement import router as admin_video_management_router

import sys
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import (
    auth,
    dashboard,
    products,
    trends,
    videos,
    fashion_items,
    hashtags,
    account,
    analytics,
)

app = FastAPI(
    title="TikTok Fashion Trend API",
    description="API phân tích và dự đoán xu hướng thời trang TikTok bằng AI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# USER / PUBLIC ROUTERS
# =========================
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(dashboard.router)
app.include_router(products.router)
app.include_router(trends.router)
app.include_router(videos.router)
app.include_router(fashion_items.router)
app.include_router(hashtags.router)
app.include_router(analytics.router)

# =========================
# ADMIN ROUTERS
# =========================
app.include_router(admin_users_router)
app.include_router(admin_jobs_router)
app.include_router(admin_tasks_router)
app.include_router(admin_system_router)
app.include_router(admin_video_management_router)


@app.get("/")
def root():
    return {
        "message": "TikTok Fashion Trend API is running"
    }