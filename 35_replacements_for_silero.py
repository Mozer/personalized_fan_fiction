from pathlib import Path
import re

# Directories
INPUT_FILES_DIR = Path("textfortts_ru")
OUTPUT_FILES_DIR = Path("textfortts_ru_silero")

# Replacement mapping: digit -> Russian word + space
replacements_map = {
    "0": "ноль ",
    "1": "один ",
    "2": "два ",
    "3": "три ",
    "4": "четыре ",
    "5": "пять ",
    "6": "шесть ",
    "7": "семь ",
    "8": "восемь ",
    "9": "девять ",
}

def replace_digits(text: str) -> str:
    """Replace each digit in text with its Russian word using regex."""
    return re.sub(r"\d", lambda m: replacements_map[m.group()], text)

def main():
    # Create output directory if it doesn't exist
    OUTPUT_FILES_DIR.mkdir(parents=True, exist_ok=True)

    # Process all .txt files in input directory
    for txt_file in INPUT_FILES_DIR.glob("*.txt"):
        # Read original content
        with open(txt_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace digits
        new_content = replace_digits(content)

        # Write to output directory with same filename
        output_path = OUTPUT_FILES_DIR / txt_file.name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"Processed: {txt_file.name}")

if __name__ == "__main__":
    main()