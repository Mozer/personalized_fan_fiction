# make sure chars have clothes, actions, backgrounds in json_scripts

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


class Config:
    """Configuration for the JSON processing pipeline."""
    def __init__(self):
        self.input_dir: Path = Path("jsons/json_scripts")        
        self.valid_char_file: Path = Path("jsons/valid_character_ids.json")
        self.valid_loc_file: Path = Path("jsons/valid_location_ids.json")
        self.output_dir: Path = Path("jsons/json_frame_prompts")

    def ensure_output_dir(self):
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)


def load_valid_ids(valid_char_path: Path, valid_loc_path: Path) -> tuple[List[str], List[str]]:
    """Load valid character and location IDs from JSON files."""
    with open(valid_char_path, 'r', encoding='utf-8') as f:
        char_data = json.load(f)
    with open(valid_loc_path, 'r', encoding='utf-8') as f:
        loc_data = json.load(f)

    valid_chars = char_data.get("character_ids", [])
    valid_locs = loc_data.get("locations", [])

    if not valid_chars:
        raise ValueError("No valid character IDs found.")
    if not valid_locs:
        raise ValueError("No valid location IDs found.")

    return valid_chars, valid_locs


def validate_character(raw_id: str, valid_chars: List[str]) -> str:
    """Return validated character ID (fallback to first valid if not found)."""
    return raw_id if raw_id in valid_chars else valid_chars[0]


def main():
    config = Config()
    config.ensure_output_dir()

    # Load valid IDs
    valid_chars, valid_locs = load_valid_ids(config.valid_char_file, config.valid_loc_file)

    # Process each JSON file in input directory
    for input_path in config.input_dir.glob("*.json"):
        episode_id = input_path.stem
        output_path = config.output_dir / f"{episode_id}.json"

        print(f"Processing {input_path.name} -> {output_path}")

        with open(input_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)

        # State tracking for clothing across frames
        clothes_state: Dict[str, str] = {}  # validated_id -> current clothes

        output_data = {}

        # Process frames in order (sorted by key)
        for frame_key in sorted(input_data.keys(), key=lambda x: int(x) if x.isdigit() else x):
            frame = input_data[frame_key]
            if not isinstance(frame, dict):
                print(f"Warning: Frame {frame_key} is not a dictionary, skipping.")
                continue

            # ---------- Location validation ----------
            location = frame.get("location", "")
            if location not in valid_locs:
                location = valid_locs[0]

            # ---------- Character IDs validation ----------
            raw_char_ids = frame.get("character_ids", [])
            validated_char_ids = [validate_character(cid, valid_chars) for cid in raw_char_ids]

            # ---------- Update clothes state from frame's character_clothes ----------
            char_clothes_input = frame.get("character_clothes", {})
            for raw_char, clothes_info in char_clothes_input.items():
                valid_char = validate_character(raw_char, valid_chars)
                new_clothes = clothes_info.get("clothes", "base")
                clothes_state[valid_char] = new_clothes

            # ---------- Ensure all present characters have a clothes entry ----------
            for char in validated_char_ids:
                if char not in clothes_state:
                    clothes_state[char] = "base"

            # ---------- Build prompt from character_actions (using original names) ----------
            char_actions = frame.get("character_actions", {})
            prompt_lines = []
            for char_name, action_info in char_actions.items():
                action_text = action_info.get("action", "").strip()
                if action_text:
                    prompt_lines.append(f"{char_name}: {action_text}")
            prompt = "\n".join(prompt_lines)
            if prompt:  # add trailing newline as in example
                prompt += "\n"

            # ---------- Prepare character_clothes for output ----------
            output_char_clothes = {}
            for char in validated_char_ids:
                output_char_clothes[char] = {"clothes": clothes_state[char]}
                
            action_type = frame.get("action_type", "")
            if action_type == "":
                if not raw_char_ids:
                    action_type = "background_empty"
                else:
                    action_type = "background_with_chars"
                
                

            # ---------- Assemble output frame ----------
            output_data[frame_key] = {
                "location_id": location,
                "character_ids": validated_char_ids,
                "character_clothes": output_char_clothes,
                "action_type": action_type,
                "prompt": prompt
            }

        # Write output JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("All files processed.")


if __name__ == "__main__":
    main()