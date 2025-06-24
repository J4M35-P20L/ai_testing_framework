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
                if "enter" in line.lower() and "as" in line.lower():
                    parts = line.split("as")
                    if len(parts) == 2:
                        field = parts[0].split("enter")[-1].strip()
                        value = parts[1].strip()
                        field_map[field] = value
                elif "click on" in line.lower():
                    button = line.split("click on")[-1].strip()
                    additional_steps.append(f'Click on the button labeled "{button}"')
                else:
                    additional_steps.append(line)
    return field_map, ", then ".join(additional_steps)