# core/agent.py

from bs4 import BeautifulSoup
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
from utils.environment import load_env
from time import sleep

# Load environment variables
load_dotenv()
api_key = load_env()
client = OpenAI(api_key=api_key)

def get_ui_summary(html):
    soup = BeautifulSoup(html, 'html.parser')
    elements = []
    for e in soup.find_all(['input', 'button', 'a', 'select', 'textarea', 'form'])[:100]:
        style = (e.get('style', '') or '').replace(" ", "").lower()
        e_type = (e.get('type', '') or '').lower()
        hidden_by_css = 'display:none' in style or 'visibility:hidden' in style
        hidden_by_type = e_type == 'hidden'
        # Skip hidden or not visible elements
        if hidden_by_css or hidden_by_type:
            continue
        # Also skip if input is outside of the viewport (optionally add more checks)
        elements.append(f"{str(e)}\nAttributes: {e.attrs}")
    return "\n".join(elements)

def build_prompt(ui_summary, field_values, additional_goal):
    field_instructions = "\n".join([
        f'- Field "{k}" MUST be filled with exactly: "{v}"' for k, v in field_values.items()
    ])

    goal = f"""
You must complete the following:
{field_instructions}
"""
    if additional_goal:
        goal += f"\nThen: {additional_goal}"

    return f"""
You are an intelligent browser automation agent.

Below is the current HTML structure of a web page under test. Your job is to return a list of UI actions needed to fulfill the user input and achieve the given goal.

HTML content:
{ui_summary}

User wants to:
{goal}

⚠️ IMPORTANT:
- DO NOT invent or guess any values. Use ONLY the values provided.
- Fill all known fields immediately if they are visible in the current HTML.
- Do not delay filling fields that already appear.
- Return ONLY a JSON array of UI actions in this format:

[
  {{
    "action": "fill" | "click" | "upload",
    "selector": "<valid CSS selector>",
    "value": "<value>"  # Only for fill and upload
  }},
  ...
]

DO NOT include any explanation or extra text.
DO NOT fill any value unless it's in the provided field list.
Only interact with elements that appear in the HTML summary above.
"""

def get_next_actions(page, field_values, additional_goal="Click on the Login button."):
    actions_to_perform = []
    seen_selectors = set()

    for step in range(2):  # Retry cycle: before and after login UI update
        html = page.content()
        ui_summary = get_ui_summary(html)
        prompt = build_prompt(ui_summary, field_values, additional_goal)

        print("[DEBUG] Prompt sent to GPT:\n", prompt)

        try:
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are an automation agent."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )

            raw_output = response.choices[0].message.content.strip()
            if raw_output.startswith("```json"):
                raw_output = raw_output[7:]
            elif raw_output.startswith("```"):
                raw_output = raw_output[3:]

            if raw_output.endswith("```"):
                raw_output = raw_output[:-3]

            print("[DEBUG] Cleaned GPT Output:", raw_output)

            new_actions = json.loads(raw_output)

            filtered = [a for a in new_actions if a['selector'] not in seen_selectors]
            for a in filtered:
                seen_selectors.add(a['selector'])

            actions_to_perform.extend(filtered)

            if any(a['action'] == 'click' and 'login' in a['selector'].lower() for a in filtered):
                print("[INFO] Detected login click. Waiting for UI changes...")
                page.wait_for_timeout(3000)  # Give time for the next screen to load

        except Exception as e:
            print(f"[ERROR] GPT failed: {e}")
            break

    return actions_to_perform
