# glue short (100 lines) dialogues into bigger (1000 lines)

import json
from pathlib import Path

class Config:
    EPISODES_INPUT_DIR = Path("dialogues")
    EPISODES_GLUED_OUTPUT_DIR = Path("dialogues_glued")
    EPISODES_MAP = Path("chapters_split_list_1.json")
    EPISODES_MAP_UPDATED = Path("chapters_split_list_2.json")
    TARGET_LINES_PER_EPISODE = 1000

def main():
    # Create output directory
    Config.EPISODES_GLUED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load the original chapter → episodes mapping
    with open(Config.EPISODES_MAP, 'r', encoding='utf-8') as f:
        episodes_map = json.load(f)

    # Global counters
    chapter_counter = 1
    episode_counter = 1

    # New mapping: chapter number (str) -> list of new episode filenames (str)
    new_map = {}

    # Process chapters in numeric order
    for chapter_key in sorted(episodes_map.keys(), key=lambda k: int(k)):
        episode_files = episodes_map[chapter_key]
        if not episode_files:
            print(f"Warning: Chapter {chapter_key} has no episodes, skipping.")
            continue

        # Collect all non‑header lines from all episodes of this chapter
        all_lines = []
        for ep_file in episode_files:
            file_path = Config.EPISODES_INPUT_DIR / ep_file
            if not file_path.exists():
                print(f"Error: {file_path} not found, skipping this file.")
                continue

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    # Skip old chapter/episode headers
                    if stripped.startswith("#Chapter") or stripped.startswith("#Episode"):
                        continue
                    all_lines.append(line)   # keep the line exactly as read (including newline)

        if not all_lines:
            print(f"Warning: No content found for chapter {chapter_key}. No episodes created.")
            # Still increment chapter counter? Probably yes, because we move to next chapter.
            chapter_counter += 1
            continue

        # Split into preliminary chunks of max TARGET_LINES_PER_EPISODE
        chunk_size = Config.TARGET_LINES_PER_EPISODE
        chunks = [all_lines[i:i + chunk_size] for i in range(0, len(all_lines), chunk_size)]

        # If the last chunk is too small (<50) and there is more than one chunk, merge it with the previous one
        if len(chunks) > 1 and len(chunks[-1]) < 50:
            chunks[-2].extend(chunks[-1])
            chunks.pop()

        # Now chunks are final episodes for this chapter
        chapter_filenames = []
        for chunk in chunks:
            # Output filename based on global episode counter
            out_filename = f"{episode_counter}.txt"
            out_path = Config.EPISODES_GLUED_OUTPUT_DIR / out_filename

            with open(out_path, 'w', encoding='utf-8') as out_f:
                # Write new headers
                out_f.write(f"#Chapter {chapter_counter}\n")
                out_f.write(f"#Episode {episode_counter}\n")
                # Write the chunk lines (they already contain newlines)
                out_f.writelines(chunk)

            chapter_filenames.append(out_filename)
            episode_counter += 1

        # Store the list for this chapter in the new map
        new_map[str(chapter_counter)] = chapter_filenames
        chapter_counter += 1

    # Save the updated map
    with open(Config.EPISODES_MAP_UPDATED, 'w', encoding='utf-8') as f:
        json.dump(new_map, f, indent=2, ensure_ascii=False)

    print("All chapters processed. New episodes written to", Config.EPISODES_GLUED_OUTPUT_DIR)
    print("Updated map saved to", Config.EPISODES_MAP_UPDATED)

if __name__ == "__main__":
    main()