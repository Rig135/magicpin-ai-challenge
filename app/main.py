from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="magicpin AI Challenge - Bot")

app.include_router(router)
