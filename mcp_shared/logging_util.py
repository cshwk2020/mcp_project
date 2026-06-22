import sys, os, threading
import io
import json
import logging
from mcp_project.config import LOGGER_FILE_PATH

# ========== LOGGING CONFIGURATION ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGGER_FILE_PATH)
    ]
)
logger = logging.getLogger(__name__)
