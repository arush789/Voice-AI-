from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.voice import router as voice_router
from app.routes.sos import router as sos_router


app = FastAPI(
    title="Rakhsha AI Backend",
    version="1.0.0",
    description="Women Safety & Emergency SOS Voice AI Backend"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(voice_router)
app.include_router(sos_router)


@app.get("/")
def root():
    return {
        "message": "Rakhsha AI Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }