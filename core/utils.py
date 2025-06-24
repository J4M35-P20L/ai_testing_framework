
import json
import logging
import os

def load_memory():
    if os.path.exists("shortcuts.json"):
        with open("shortcuts.json", "r") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open("shortcuts.json", "w") as f:
        json.dump(memory, f, indent=2)

def get_logger(name="ai-framework"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
