"""启动入口：python run.py"""

import uvicorn

from backend.config import app_config

if __name__ == "__main__":
    cfg = app_config()
    uvicorn.run(
        "backend.main:app",
        host=cfg.get("host", "127.0.0.1"),
        port=int(cfg.get("port", 8000)),
        reload=False,
    )
