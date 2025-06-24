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
    from utils.logger import get_logger
    from bs4 import BeautifulSoup
    logger = get_logger()

    def extract_visible_input_fields(html):
        soup = BeautifulSoup(html, 'html.parser')
        visible_fields = set()
        for input_tag in soup.find_all('input'):
            style = input_tag.get('style', '').lower()
            input_type = input_tag.get('type', '').lower()
            if 'display:none' in style or input_type == 'hidden':
                continue
            identifier = (
                    input_tag.get('automation_id') or
                    input_tag.get('name') or
                    input_tag.get('id') or
                    input_tag.get('placeholder')
            )
            if identifier:
                visible_fields.add(identifier.strip())
        return visible_fields

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(os.getenv("APP_URL") or "https://myhubstaging.smdservers.net/" )
        page.wait_for_timeout(3000)

        phase = 1
        filled_fields = set()
        original_html = page.content()
        original_visible_fields = extract_visible_input_fields(original_html)

        while True:
            html = page.content()
            actions = get_next_actions(html, field_values, additional_goal)

            logger.info(f"\n🔁 Phase {phase}: Performing {len(actions)} actions.")
            for action in actions:
                logger.info(f" -> {action}")
                try:
                    action_type = action['action'].lower()
                    if action_type == 'click':
                        page.click(action['selector'])
                    elif action_type in ['type', 'fill']:
                        page.fill(action['selector'], action['value'])
                        for k, v in field_values.items():
                            if v == action['value']:
                                filled_fields.add(k)
                    elif action_type == 'upload':
                        page.set_input_files(action['selector'], action['value'])
                except Exception as e:
                    logger.error(f"⚠️ Failed to perform action {action}: {e}")

            page.wait_for_timeout(2000)
            new_html = page.content()
            current_visible_fields = extract_visible_input_fields(new_html)
            newly_visible_fields = current_visible_fields - original_visible_fields

            expected_new_fields = []
            for key in field_values:
                if key not in filled_fields:
                    for field in newly_visible_fields:
                        if key.lower() in field.lower():
                            expected_new_fields.append(key)
                            break

            if expected_new_fields:
                logger.info(f"🆕 Expected fields now visible: {expected_new_fields}")
                additional_goal = f"Fill newly appeared fields: {', '.join(expected_new_fields)}"

                # Recompute and perform phase 2 actions immediately
                actions = get_next_actions(new_html, field_values, additional_goal)
                logger.info(f"\n🔁 Phase {phase + 1}: Performing {len(actions)} follow-up actions.")
                for action in actions:
                    logger.info(f" -> {action}")
                    try:
                        action_type = action['action'].lower()
                        if action_type == 'click':
                            page.click(action['selector'])
                        elif action_type in ['type', 'fill']:
                            page.fill(action['selector'], action['value'])
                            for k, v in field_values.items():
                                if v == action['value']:
                                    filled_fields.add(k)
                        elif action_type == 'upload':
                            page.set_input_files(action['selector'], action['value'])
                    except Exception as e:
                        logger.error(f"⚠️ Failed to perform action {action}: {e}")

                original_visible_fields.update(current_visible_fields)
                phase += 1
                continue

            with open(f"phase_{phase}_ui.html", "w", encoding="utf-8") as f:
                f.write(new_html)

            logger.info("✅ No new fields detected. Finishing test.")
            break

        page.wait_for_timeout(2000)
        browser.close()

def split_goal_steps(goal_text):
    return [step.strip() for step in goal_text.split("then") if step.strip()]
