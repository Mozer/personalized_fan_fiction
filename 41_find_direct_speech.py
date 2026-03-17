from pathlib import Path

# Директории
INPUT_FILES_DIR = Path("textfortts_en_enumerated")
OUTPUT_FILES_DIR = Path("direct_speech")

def process_text(text: str) -> str:
    """
    Extract lines with direct speech from the input text.
    Expected line format: "<number>. <text>"
    A line contains direct speech if <text> starts with a word ending with a colon.
    Returns a string where each kept line is formatted as:
        <number>. {action_type: "direct_speech", character: "<character_name>"}
    """
    lines = text.splitlines()
    output_lines = []

    for line in lines:
        line = line.rstrip('\n')
        if not line:
            continue

        # Split into number and the rest using the first ". " as separator
        parts = line.split('. ', 1)
        if len(parts) != 2:
            continue  # skip lines that do not match the expected format

        number, rest = parts

        # Get the first word of the rest (strip leading spaces just in case)
        rest_stripped = rest.lstrip()
        if not rest_stripped:
            continue

        first_word = rest_stripped.split(maxsplit=1)[0]
        if first_word.endswith(':'):
            character = first_word[:-1]  # remove the colon
            action = f'{{"action_type": "direct_speech", "character": "{character}"}}'
            output_lines.append(f"{number}. {action}")

    return "\n".join(output_lines)

def main():
    # Create output directory if it doesn't exist
    OUTPUT_FILES_DIR.mkdir(parents=True, exist_ok=True)

    # Process every .txt file in the input directory
    for txt_file in INPUT_FILES_DIR.glob("*.txt"):
        with open(txt_file, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = process_text(content)

        output_path = OUTPUT_FILES_DIR / txt_file.name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"Processed: {txt_file.name}")

if __name__ == "__main__":
    main()