#split lewd.txt into 2 .txt files, update mapping

import json
from pathlib import Path
from typing import Dict, List


class Config:
    """Configuration for splitting chapter files."""
    EPISODES_INPUT_DIR = Path("itlewd_en")
    EPISODES_OUTPUT_DIR = Path("itlewd_split_en")
    EPISODES_MAP_OUTPUT = Path("chapters_split_list_4.json")


def natural_sort_key(path: Path) -> int:
    """
    Extract integer from filename stem for natural sorting.
    Assumes filenames are like '1.txt', '2.txt', etc.
    """
    try:
        return int(path.stem)
    except ValueError:
        # Fallback for non‑integer names – sort lexicographically
        return path.stem


def split_file_by_lines(file_path: Path, output_dir: Path, start_counter: int) -> tuple[List[str], int]:
    """
    Split a text file into two halves by lines.

    Args:
        file_path: Path to the input file.
        output_dir: Directory where output files will be saved.
        start_counter: The starting number for the first output file.

    Returns:
        A tuple (output_filenames, next_counter):
            - output_filenames: list of two filenames (e.g., ['1.txt', '2.txt'])
            - next_counter: the next available counter after writing both parts.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_lines = len(lines)
    if total_lines == 0:
        # Handle empty file: create two empty files
        split_point = 0
    else:
        # First part gets ceil(total_lines/2), second part gets floor
        split_point = (total_lines + 1) // 2

    first_lines = lines[:split_point]
    second_lines = lines[split_point:]

    # Write first part
    first_filename = f"{start_counter}.txt"
    first_path = output_dir / first_filename
    with open(first_path, 'w', encoding='utf-8') as f:
        f.writelines(first_lines)

    # Write second part
    second_filename = f"{start_counter + 1}.txt"
    second_path = output_dir / second_filename
    with open(second_path, 'w', encoding='utf-8') as f:
        f.writelines(second_lines)

    output_filenames = [first_filename, second_filename]
    next_counter = start_counter + 2
    return output_filenames, next_counter


def main():
    config = Config()

    # Create output directory if it doesn't exist
    config.EPISODES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Gather all .txt files in input directory
    txt_files = list(config.EPISODES_INPUT_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {config.EPISODES_INPUT_DIR}")
        return

    # Sort files naturally (by integer stem when possible)
    txt_files.sort(key=natural_sort_key)

    mapping: Dict[str, List[str]] = {}
    output_counter = 1

    for input_file in txt_files:
        # Split the file and get the two output filenames
        output_names, output_counter = split_file_by_lines(
            input_file, config.EPISODES_OUTPUT_DIR, output_counter
        )
        # Store mapping using the original filename stem (as string)
        mapping[input_file.stem] = output_names
        print(f"Processed {input_file.name} -> {output_names}")

    # Write the mapping to JSON
    with open(config.EPISODES_MAP_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)

    print(f"\nMapping saved to {config.EPISODES_MAP_OUTPUT}")


if __name__ == "__main__":
    main()