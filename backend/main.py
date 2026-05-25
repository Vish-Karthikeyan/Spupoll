from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from routers import auth, sessions, questions, responses, results

app = FastAPI(title="Spupoll API", version="1.0.0")

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(questions.router)
app.include_router(responses.router)
app.include_router(results.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "Spupoll API"}
