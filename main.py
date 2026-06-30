from fastapi import FastAPI, Request
from routes import auth_router, router, SESSION_COOKIE
from services.auth_service import auth_service
from services.question_persistence_service import question_persistence_service
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="QFund",
    version="1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")


@app.on_event("shutdown")
def drain_question_writes():
    question_persistence_service.wait_until_empty(timeout=30)


@app.get("/", include_in_schema=False)
def login_page(request: Request):
    if auth_service.user_from_token(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/app", status_code=303)
    return FileResponse(BASE_DIR / "login.html")


@app.get("/app", include_in_schema=False)
def index(request: Request):
    if not auth_service.user_from_token(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=303)
    return FileResponse(BASE_DIR / "index.html")


@app.get("/index.html", include_in_schema=False)
def index_html(request: Request):
    return index(request)


@app.get("/history", include_in_schema=False)
def history(request: Request):
    if not auth_service.user_from_token(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=303)
    return FileResponse(BASE_DIR / "history.html")


@app.get("/history.html", include_in_schema=False)
def history_html(request: Request):
    return history(request)


app.include_router(auth_router)
app.include_router(router)
