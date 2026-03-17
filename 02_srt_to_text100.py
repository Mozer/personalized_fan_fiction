#split .srt into .txt with 100 lines max

import re
import os
import json

def _is_russian_lower(char):
    """Return True if char is a lowercase Russian letter (а-я or ё)."""
    return '\u0430' <= char <= '\u044f' or char == '\u0451'

def merge_subtitle_lines(content):
    """
    Clean SRT content and merge lines that start with a lowercase Russian letter
    into the previous sentence.
    Returns a list of merged lines (strings).
    """
    # Remove subtitle numbers (lines with just digits)
    content = re.sub(r'^\d+\s*$', '', content, flags=re.MULTILINE)

    # Remove timecodes (--> format)
    content = re.sub(r'\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}', '', content)

    # Remove HTML-like tags (e.g., <i>, </i>)
    content = re.sub(r'<[^>]+>', '', content)

    # Split into lines and remove empty ones
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    # Merge lines that start with a lowercase Russian letter
    merged = []
    for line in lines:
        if not merged:
            merged.append(line)
            continue

        # If the line starts with a lowercase Russian letter, glue it to the previous line
        if line and _is_russian_lower(line[0]):
            merged[-1] = merged[-1] + " " + line
        else:
            merged.append(line)

    return merged

def process_all_srts(input_dir="srt", output_dir="subs_text", max_lines_per_file=100):
    """
    Process all SRT files named 1.srt .. 20.srt from input_dir.
    Write chunks into output_dir as sequentially numbered .txt files.
    Create a mapping JSON file.
    """
    os.makedirs(output_dir, exist_ok=True)

    global_file_counter = 1
    mapping = {}

    for i in range(1, 99):
        input_path = os.path.join(input_dir, f"{i}.srt")
        if not os.path.exists(input_path):
            print(f"Warning: {input_path} does not exist, skipping.")
            continue

        print(f"Processing {input_path} ...")

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  Error reading file: {e}")
            continue

        merged_lines = merge_subtitle_lines(content)
        if not merged_lines:
            print(f"  No subtitle text found, skipping.")
            continue

        # Split into chunks
        chunks = [merged_lines[i:i+max_lines_per_file]
                  for i in range(0, len(merged_lines), max_lines_per_file)]

        file_list_for_this_srt = []
        for chunk in chunks:
            output_filename = f"{global_file_counter}.txt"
            output_path = os.path.join(output_dir, output_filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(chunk))
            print(f"  Wrote {output_filename} ({len(chunk)} lines)")
            file_list_for_this_srt.append(output_filename)
            global_file_counter += 1

        mapping[str(i)] = file_list_for_this_srt

    # Write mapping JSON
    json_path = "chapters_split_list_1.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"\nMapping saved to {json_path}")

if __name__ == "__main__":
    process_all_srts()