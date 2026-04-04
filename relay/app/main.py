from __future__ import annotations

import uvicorn

from app.config import load_bootstrap_settings
from app.http_app import create_app
from app.logging_setup import configure_logging


bootstrap = load_bootstrap_settings()
configure_logging(bootstrap)
app = create_app(bootstrap)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=bootstrap.host, port=bootstrap.port, reload=False)
