# core/feature_parser.py

import re

def extract_field_value_map(feature_path, scenario_name):
    field_map = {}
    additional_steps = []

    with open(feature_path, "r") as file:
        recording = False
        for line in file:
            line = line.strip()

            if line.startswith("Scenario:") and scenario_name in line:
                recording = True
                continue
            elif line.startswith("Scenario:") and recording:
                break

            if recording:
                # Match: enter <field> as <value> or enters <field> as <value>
                match = re.search(r'enter(?:s)?\s+"?([^"]+)"?\s+as\s+"?([^"]+)"?', line, re.IGNORECASE)
                if match:
                    field = match.group(1).strip().lower().replace(" ", "")
                    value = match.group(2).strip()
                    field_map[field] = value
                elif "click on" in line.lower():
                    button = line.split("click on")[-1].strip().strip('"')
                    additional_steps.append(f'Click on the button labeled "{button}"')
                else:
                    additional_steps.append(line)

    return field_map, ", then ".join(additional_steps)
