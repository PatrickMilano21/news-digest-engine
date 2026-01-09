from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return{"service": "news-digest-engine", "try": ["/health", "/docs"]}

@app.get("/health")
def health():
    return {"status": "ok"}
