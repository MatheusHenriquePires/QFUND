from fastapi import FastAPI
from routes import router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/index.html", include_in_schema=False)
def index_html():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/history", include_in_schema=False)
def history():
    return FileResponse(BASE_DIR / "history.html")


@app.get("/history.html", include_in_schema=False)
def history_html():
    return FileResponse(BASE_DIR / "history.html")


app.include_router(router)
