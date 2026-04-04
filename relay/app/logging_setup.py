from __future__ import annotations

import logging

from app.config import BootstrapSettings


def configure_logging(configured_settings: BootstrapSettings) -> None:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler) for handler in root_logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    log_file = configured_settings.logs_dir / "relay.log"
    try:
        resolved_log_file = str(log_file.resolve())
        if not any(
            isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == resolved_log_file
            for handler in root_logger.handlers
        ):
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
    except PermissionError:
        logging.getLogger("relay.main").warning("relay.log is locked; continuing with console logging only.")
