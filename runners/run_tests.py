import os
import json
from core.agent import get_next_actions
from core.feature_parser import extract_field_value_map
from utils.environment import load_env
from utils.memory import load_memory, save_memory
from utils.logger import get_logger
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

logger = get_logger()
memory = load_memory()
env = load_env()

def extract_visible_input_fields(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    visible_fields = set()
    for input_tag in soup.find_all('input'):
        style = (input_tag.get('style', '') or '').replace(" ", "").lower()
        input_type = (input_tag.get('type', '') or '').lower()
        if 'display:none' in style or 'visibility:hidden' in style or input_type == 'hidden':
            continue
        # Skip if parent is hidden
        parent = input_tag.parent
        parent_hidden = False
        while parent:
            parent_style = (parent.get('style', '') or '').replace(" ", "").lower()
            if 'display:none' in parent_style or 'visibility:hidden' in parent_style:
                parent_hidden = True
                break
            parent = parent.parent
        if parent_hidden:
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

def extract_visible_input_fields_with_values(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    fields = {}
    for input_tag in soup.find_all('input'):
        style = (input_tag.get('style', '') or '').replace(" ", "").lower()
        input_type = (input_tag.get('type', '') or '').lower()
        if 'display:none' in style or 'visibility:hidden' in style or input_type == 'hidden':
            continue
        # Skip if parent is hidden
        parent = input_tag.parent
        parent_hidden = False
        while parent:
            parent_style = (parent.get('style', '') or '').replace(" ", "").lower()
            if 'display:none' in parent_style or 'visibility:hidden' in parent_style:
                parent_hidden = True
                break
            parent = parent.parent
        if parent_hidden:
            continue
        identifier = (
                input_tag.get('automation_id') or
                input_tag.get('name') or
                input_tag.get('id') or
                input_tag.get('placeholder')
        )
        value = input_tag.get('value', '')
        if identifier and input_type != "password":
            fields[identifier.strip()] = value
    return fields

def extract_visible_login_buttons(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    buttons = []
    for btn in soup.find_all(['input', 'button']):
        style = (btn.get('style', '') or '').replace(" ", "").lower()
        btn_type = (btn.get('type', '') or '').lower()
        if 'display:none' in style or 'visibility:hidden' in style:
            continue
        if btn.name == 'input' and btn_type == 'submit':
            label = btn.get('value', '').lower()
            if 'login' in label:
                buttons.append(btn)
        elif btn.name == 'button':
            label = (btn.get_text() or '').lower()
            if 'login' in label:
                buttons.append(btn)
    return buttons

def perform_ui_actions(page, actions, field_values, filled_fields):
    """
    Perform actions. Mark fields as filled *when the action is performed*, not by checking the DOM afterward.
    """
    for action in actions:
        logger.info(f" -> {action}")
        try:
            action_type = action['action'].lower()
            selector = action['selector']
            if action_type == 'click':
                logger.info(f"Clicking {selector}")
                page.wait_for_selector(selector, timeout=4000)
                page.click(selector)
            elif action_type in ['type', 'fill']:
                page.wait_for_selector(selector, timeout=4000)
                page.fill(selector, action['value'])
                # Robust: Mark this key as filled immediately (even for password!)
                for k, v in field_values.items():
                    if v == action['value']:
                        filled_fields.add(k.lower())
            elif action_type == 'upload':
                page.wait_for_selector(selector, timeout=4000)
                page.set_input_files(selector, action['value'])
        except Exception as e:
            logger.error(f"⚠️ Failed to perform action {action}: {e}")

def get_unfilled_fields(field_values, filled_fields, html):
    visible_fields_with_values = extract_visible_input_fields_with_values(html)
    still_unfilled = []
    for key, expected_value in field_values.items():
        if key.lower() in filled_fields:
            continue  # Already filled (by action)
        found = False
        for ident, meta in visible_fields_with_values.items():
            # Match by substring, ignore case
            if key.replace(" ", "").lower() in ident.replace(" ", "").lower():
                # Only check value for non-passwords
                if meta['type'] == 'password':
                    continue  # Trust action, not HTML
                elif meta['value'].strip() == expected_value.strip():
                    found = True
                    break
        if not found:
            still_unfilled.append(key)
    return still_unfilled

def match_fields_to_visible(field_values, visible_fields, filled_fields):
    """
    Returns a dict of {key: value} for only the fields that are visible and not yet filled.
    Uses substring and case-insensitive matching.
    """
    matched = {}
    for key, value in field_values.items():
        if key in filled_fields:
            continue
        for vis in visible_fields:
            # Fuzzy match: key must be a substring in the visible field identifier
            if key.replace(" ", "").lower() in vis.replace(" ", "").lower():
                matched[key] = value
                break
    return matched

def run_agent(field_values, additional_goal):
    from collections import defaultdict
    from playwright.sync_api import sync_playwright
    import time

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(os.getenv("APP_URL") or "https://gmail.com/")
        page.wait_for_timeout(500)

        phase = 1
        max_phases = 8
        phase_htmls = defaultdict(str)
        filled_fields = set()
        login_clicked = False

        while phase <= max_phases:
            logger.info(f"\n🔁 Phase {phase}: Starting with goal: {additional_goal}")
            current_html = page.content()
            visible_fields = extract_visible_input_fields(current_html)
            visible_fields_with_values = extract_visible_input_fields_with_values(current_html)

            # Decide what still needs to be filled (exclude those we've already filled, or that are already filled in the DOM)
            to_fill_fields = {}
            for key, expected_value in field_values.items():
                key_lc = key.lower()
                if key_lc in filled_fields:
                    continue
                # For non-password fields, check if visible and already filled in the DOM
                is_password = "password" in key_lc
                if is_password:
                    # For password, rely only on filled_fields
                    if key_lc not in filled_fields and any(key_lc in ident.lower() for ident in visible_fields):
                        to_fill_fields[key] = expected_value
                else:
                    found = False
                    for ident, val in visible_fields_with_values.items():
                        if key_lc in ident.lower() and val.strip() == expected_value.strip():
                            found = True
                            filled_fields.add(key_lc)
                            break
                    if not found and any(key_lc in ident.lower() for ident in visible_fields):
                        to_fill_fields[key] = expected_value

            logger.info(f"🖼️ Visible fields: {visible_fields}")
            logger.info(f"🖼️ Visible fields with values: {visible_fields_with_values}")
            logger.info(f"✏️ Fields to fill this phase: {to_fill_fields}")

            actions = []
            if to_fill_fields:
                actions = get_next_actions(page, to_fill_fields, "")

            # Add login button click if visible and not already clicked
            visible_login_buttons = extract_visible_login_buttons(current_html)
            btn_selector = None
            if visible_login_buttons and not login_clicked:
                for btn in visible_login_buttons:
                    if btn.get('automation_id'):
                        btn_selector = f"[automation_id='{btn.get('automation_id')}']"
                        break
                    elif btn.get('id'):
                        btn_selector = f"#{btn.get('id')}"
                        break
                    elif btn.get('name'):
                        btn_selector = f"[name='{btn.get('name')}']"
                        break
                    elif btn.get('value'):
                        btn_selector = f"input[value='{btn.get('value')}']"
                        break
                if btn_selector:
                    actions.append({'action': 'click', 'selector': btn_selector})
                    login_clicked = True

            logger.info(f"🔁 Performing {len(actions)} actions.")
            perform_ui_actions(page, actions, field_values, filled_fields)

            page.wait_for_timeout(1000)
            new_html = page.content()
            phase_htmls[phase] = new_html

            # Check: Are all fields filled as per the feature file?
            all_filled = True
            for key in field_values.keys():
                if key.lower() not in filled_fields:
                    all_filled = False
                    break

            if all_filled:
                logger.info("✅ All expected fields present and filled in the UI. Ending test.")
                break
            else:
                not_filled = [k for k in field_values.keys() if k.lower() not in filled_fields]
                logger.info(f"⚠️ Still unfilled fields in the UI: {not_filled}")

            phase += 1

        with open(f"phase_{phase}_ui.html", "w", encoding="utf-8") as f:
            f.write(new_html)
        page.wait_for_timeout(2000)
        browser.close()

def split_goal_steps(goal_text):
    return [step.strip() for step in goal_text.split("then") if step.strip()]
