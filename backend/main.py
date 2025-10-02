import os
import uvicorn

if __name__ == "__main__":
    port = os.getenv("PORT")

    if port is None:
        uvicorn.run('src.server:app', port=8000, reload=True)
    else:
        uvicorn.run(
            "src.server:app",
            host="0.0.0.0",
            port=int(port),
            log_level="info",
        )
