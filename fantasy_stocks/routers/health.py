from fastapi import APIRouter

route = APIRouter(prefix="/health", tags=["health"])


@route.get("/ping")
def ping():
    return {"ok": True}
