# merge lines from different files into single json
# trying to find all characters
import json
import re
from pathlib import Path
from collections import defaultdict
from json_repair import repair_json

# Directories
INPUT_DIRS = [
    Path("prompts_for_lines_locations_char"),
    Path("prompts_for_actions_en"),
    Path("prompts_for_clothes_change_en"),
    Path("direct_speech"),
]
OUTPUT_DIR = Path("jsons/json_scripts")
VALID_CHARACTER_IDS = Path("jsons/valid_character_ids.json")

def parse_line(line: str):
    """
    Parse a line of the format "<number>. <json-like dict>"
    Returns (line_number, dict) or raises an exception if parsing fails.
    Handles JSON with unquoted keys by adding double quotes around them.
    """
    line = line.rstrip('\n')
    if not line:
        return None
    parts = line.split('. ', 1)
    if len(parts) != 2:
        raise ValueError(f"Line does not match expected format: {line}")
    num_str, json_str = parts
    try:
        line_num = int(num_str)
    except ValueError:
        raise ValueError(f"Invalid line number: {num_str}")
    
    json_str = repair_json(json_str)
    
    # Try parsing as normal JSON first
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Assume keys are unquoted – add double quotes around identifiers followed by colon
        fixed = re.sub(r'(\b[a-zA-Z_][a-zA-Z0-9_]*\b)(?=\s*:)', r'"\1"', json_str)
        try:
            data = json.loads(fixed)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON after fixing keys: {fixed}") from e
    return line_num, data

def merge_chapter_files(chapter_id: str):
    """Merge all files for a given chapter ID and return the combined data dict."""
    merged = defaultdict(dict)

    for dir_path in INPUT_DIRS:
        file_path = dir_path / f"{chapter_id}.txt"
        if not file_path.exists():
            continue  # chapter file missing in this directory

        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    num, data = parse_line(line)
                except Exception as e:
                    print(f"Warning: {file_path}:{line_num} skipped: {e}")
                    continue
                # Merge data for this line number
                merged[num].update(data)

    return merged

def find_chars_in_actions(line_data, pattern):
    """
    Search for any valid character name inside the "action" fields
    of all "character_actions" entries.
    Returns a list of names found (may contain duplicates).
    """
    found = []
    if 'character_actions' in line_data and isinstance(line_data['character_actions'], dict):
        for char_obj in line_data['character_actions'].values():
            if isinstance(char_obj, dict) and 'action' in char_obj:
                action_text = char_obj['action']
                # Find all whole‑word matches of any valid name
                matches = pattern.findall(action_text)
                found.extend(matches)
    return found

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load valid character IDs, excluding "woman" and "man"
    try:
        with open(VALID_CHARACTER_IDS, 'r', encoding='utf-8') as f:
            data = json.load(f)
        all_valid = data.get("character_ids", [])
    except Exception as e:
        print(f"Warning: could not load {VALID_CHARACTER_IDS}: {e}")
        all_valid = []
    valid_chars = [c for c in all_valid if c not in ("woman", "man")]
    
    # Compile a regex that matches any valid character name as a whole word
    if valid_chars:
        # Escape each name to handle special regex characters (none expected, but safe)
        pattern = re.compile(r'\b(' + '|'.join(re.escape(name) for name in valid_chars) + r')\b')
    else:
        pattern = None  # no names to search for

    # Collect all chapter IDs from all input directories
    all_chapters = set()
    for dir_path in INPUT_DIRS:
        if dir_path.exists():
            for txt_file in dir_path.glob("*.txt"):
                all_chapters.add(txt_file.stem)

    # Process each chapter
    for chapter_id in sorted(all_chapters):
        merged_data = merge_chapter_files(chapter_id)
        if not merged_data:
            print(f"No data for chapter {chapter_id}, skipping.")
            continue

        # Convert integer keys to strings and sort
        output_dict = {str(k): merged_data[k] for k in sorted(merged_data)}

        # --- Parse and set character_ids ---
        for line_data in output_dict.values():
            # Special case: direct speech line -> character_ids contains only the speaker
            if line_data.get('action_type') == 'direct_speech' and 'character' in line_data:
                line_data['character_ids'] = [line_data['character']]
                continue  # Skip the general collection for this line

            # General case: collect all character names from other sources
            names = []

            # Existing character_ids list
            if 'character_ids' in line_data and isinstance(line_data['character_ids'], list):
                names.extend(line_data['character_ids'])

            # Keys from character_actions
            if 'character_actions' in line_data and isinstance(line_data['character_actions'], dict):
                names.extend(line_data['character_actions'].keys())

            # Keys from character_clothes
            if 'character_clothes' in line_data and isinstance(line_data['character_clothes'], dict):
                names.extend(line_data['character_clothes'].keys())

            # Search for character names inside "action" fields
            if pattern is not None:
                found_in_action = find_chars_in_actions(line_data, pattern)
                names.extend(found_in_action)

            # Deduplicate while preserving order (Python 3.7+ dict maintains insertion order)
            unique_names = list(dict.fromkeys(names))

            # Update or add character_ids
            line_data['character_ids'] = unique_names
        # --- End of parsing step ---

        # Save the processed JSON
        out_path = OUTPUT_DIR / f"{chapter_id}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, ensure_ascii=False, indent=2)

        print(f"Created {out_path}")

if __name__ == "__main__":
    main()