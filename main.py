"""Local dev entry — production uses `./start.sh` (Hub) or uvicorn astrophysics.main:app."""

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("astrophysics.main:app", host="0.0.0.0", port=5112, reload=True)
