import os
from runners.run_tests import run_agent
from utils.memory import load_memory, save_memory
from core.feature_parser import extract_field_value_map

if __name__ == "__main__":
    memory = load_memory()

    shortcut = input("Enter shortcut or feature path (e.g., features/login.feature::Valid login): ").strip()

    if ".feature" in shortcut and "::" in shortcut:
        feature_path, scenario = shortcut.split("::")
        feature_path = feature_path.strip()
        scenario = scenario.strip()

        # Extract field values dynamically every time
        field_values, additional_goal = extract_field_value_map(feature_path, scenario)
        print("Extracted field_values:", field_values)

        save = input("Would you like to save this as a shortcut? (y/n): ").strip().lower()
        if save == 'y':
            name = input("Enter shortcut name: ").strip()
            memory[name] = {
                "feature_path": feature_path,
                "scenario": scenario
            }
            save_memory(memory)

        run_agent(field_values, additional_goal)

    elif shortcut in memory:
        saved = memory[shortcut]
        feature_path = saved.get("feature_path")
        scenario = saved.get("scenario")
        if not feature_path or not scenario:
            print("Shortcut is missing required fields.")
        else:
            field_values, additional_goal = extract_field_value_map(feature_path, scenario)
            run_agent(field_values, additional_goal)

    else:
        print("Invalid shortcut or feature path.")
