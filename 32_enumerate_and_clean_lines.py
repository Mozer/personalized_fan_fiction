# remove empty lines
# enumerate all lines

from pathlib import Path

# Директории
INPUT_FILES_DIR_EN = Path("textfortts_en")
OUTPUT_FILES_DIR_EN = Path("textfortts_en_enumerated")

INPUT_FILES_DIR_RU = Path("textfortts_ru_silero")
OUTPUT_FILES_DIR_RU = Path("textfortts_ru_enumerated")

def process_text(text: str) -> str:
    """Удаляет пустые строки и добавляет нумерацию '0. '."""
    # Разделяем текст на строки и убираем лишние пробелы по краям
    lines = text.splitlines()
    
    # Оставляем только непустые строки (strip() удаляет пробелы и табуляцию)
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    
    # Нумеруем строки, начиная с 0
    numbered_lines = []
    for index, line in enumerate(non_empty_lines):
        numbered_lines.append(f"{index}. {line}")
    
    # Собираем обратно в один текст
    return "\n".join(numbered_lines)

def main():
    # Создаем выходную директорию, если её нет
    OUTPUT_FILES_DIR_EN.mkdir(parents=True, exist_ok=True)
    
    # Создаем выходную директорию, если её нет
    OUTPUT_FILES_DIR_RU.mkdir(parents=True, exist_ok=True)

    # Обрабатываем все .txt файлы
    for txt_file in INPUT_FILES_DIR_EN.glob("*.txt"):
        # Читаем содержимое
        with open(txt_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Обрабатываем текст (удаляем пустые строки и нумеруем)
        new_content = process_text(content)

        # Записываем результат
        output_path = OUTPUT_FILES_DIR_EN / txt_file.name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"Processed EN: {txt_file.name}")
        
    # Обрабатываем все .txt файлы
    for txt_file in INPUT_FILES_DIR_RU.glob("*.txt"):
        # Читаем содержимое
        with open(txt_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Обрабатываем текст (удаляем пустые строки и нумеруем)
        new_content = process_text(content)

        # Записываем результат
        output_path = OUTPUT_FILES_DIR_RU / txt_file.name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"Processed RU: {txt_file.name}")    
        

if __name__ == "__main__":
    main()
