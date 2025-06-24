from bs4 import BeautifulSoup
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
from utils.environment import load_env

# Load environment variables
load_dotenv()
print("Loaded API Key:", os.getenv("OPENAI_API_KEY"))

# Load the OpenAI API key from your custom loader
api_key = load_env()
client = OpenAI(api_key=api_key)

def get_next_actions(html, field_values, additional_goal="Click on the Login button."):
    soup = BeautifulSoup(html, 'html.parser')

    # Collect key UI elements for the prompt with their attributes
    elements = soup.find_all(['input', 'button', 'a', 'select', 'textarea', 'form'])[:100]
    ui_summary = "\n".join([
        f"{str(e)}\nAttributes: {e.attrs}" for e in elements
    ])

    # Combine user field entries and goals
    field_instructions = ", ".join([f'Fill "{k}" with "{v}"' for k, v in field_values.items()])
    goal = field_instructions
    if additional_goal:
        goal += ", then " + additional_goal

    prompt = f"""
You are an intelligent browser automation agent.

Below is the current HTML structure of a web page under test. Your job is to return a list of UI actions needed to fulfill the user input and achieve the given goal.

HTML content:
{ui_summary}

User wants to:
{goal}

Return ONLY a JSON array of actions.
Each action should be an object with the following format:
[
  {{
    "action": "fill" | "click" | "upload",
    "selector": "<valid CSS selector>",
    "value": "<value>"  # Only required for fill and upload
  }},
  ...
]

⚠️ Do NOT add explanations or extra text. Only respond with a valid JSON array.
Only include elements that are found in the HTML provided above.
"""

    print("[DEBUG] Prompt Sent to GPT:\n", prompt)
    print("[DEBUG] Field Values:", field_values)
    print("[DEBUG] Additional Goal:", additional_goal)

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
        print("[DEBUG] Raw GPT Output:", raw_output)

        return json.loads(raw_output)

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse GPT response as JSON: {e}")
        return []

    except Exception as e:
        print(f"[ERROR] Unexpected error from GPT call: {e}")
        return []
