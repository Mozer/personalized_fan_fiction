import os
import re
import shutil

# Define name replacements (source -> target) for all grammatical cases
replacements = {
    "Алексей": "Юрий",
    "Алексея": "Юрия",
    "Алексею": "Юрию",
    "Алексеем": "Юрием",
    "Алексее": "Юрие",
}

def replace_names_in_file(input_path, output_path):
    """Read file, replace names, write to output_path."""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {input_path}: {e}")
        return

    # Apply each replacement as a whole word
    for old, new in replacements.items():
        # Use word boundaries with Unicode support
        pattern = r'\b' + re.escape(old) + r'\b'
        content = re.sub(pattern, new, content, flags=re.UNICODE)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Processed: {input_path} -> {output_path}")
    except Exception as e:
        print(f"Error writing {output_path}: {e}")

def process_directory(input_dir, output_dir):
    """Process all .txt files in input_dir, write to output_dir."""
    if not os.path.isdir(input_dir):
        print(f"Input directory not found: {input_dir}")
        return

    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            replace_names_in_file(input_path, output_path)

def main():
    # Process first group
    process_directory("dialogues_glued", "dialogues_replaced")
    # Process second group
    process_directory("short_descriptions", "short_descriptions_replaced")
    # Process thrid group
    process_directory("summary_ru", "summary_ru_replaced")

if __name__ == "__main__":
    main()