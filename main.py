from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "ReqPrint API is running"}