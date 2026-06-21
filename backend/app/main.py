from fastapi import FastAPI
from app.routers import auth, users

app = FastAPI(
    title="FastAPI",
    openapi_url="/openapi.json"
)

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)