import os
import json
from core.agent import get_next_actions
from core.feature_parser import extract_field_value_map
from utils.environment import load_env
from utils.memory import load_memory, save_memory
from utils.logger import get_logger
from playwright.sync_api import sync_playwright
from pages.loginpage import perform_actions

logger = get_logger()
memory = load_memory()
env = load_env()

def run_agent(field_values, additional_goal):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(os.getenv("TEST_URL"))
        page.wait_for_timeout(500)

        html = page.content()
        actions = get_next_actions(html, field_values, additional_goal)

        logger.info(f"Agent decided to perform {len(actions)} actions.")
        for action in actions:
            logger.info(f" -> {action}")

        # ✅ Just call the shared executor here
        perform_actions(page, actions)

        page.wait_for_timeout(500)
        browser.close()
