#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob
import base64
import uuid
from datetime import datetime
from xml.sax.saxutils import escape

# ===== CONFIGURATION =====
CHAPTERS_DIR = "itlewderru_ru"   # folder with 1.txt, 2.txt, ...
IMAGES_DIR = "images"               # folder with 1.jpg, 2.png, ...
OUTPUT_FILE = "itlewd_50.fb2"      # resulting FB2 file

# Book metadata (change as needed)
BOOK_TITLE = "Naughty IT Crowd, фанфик с иллюстрациями"
BOOK_AUTHOR_FIRST = "Автор"
BOOK_AUTHOR_LAST = "Неизвестен"
BOOK_LANG = "ru"

# ===== HELPER FUNCTIONS =====

def extract_title_and_text(file_path, chap_num):
    """
    Reads a chapter file and returns:
        - title (str or None): the extracted title if it passes the length check,
          otherwise None.
        - text (str): full chapter text (including the candidate line if it was
          too long to be a title).
    The title is accepted only if it has ≤10 words AND ≤50 characters.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    title = None
    title_index = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            # Found the first non‑empty, non‑comment line → candidate for title
            words = stripped.split()
            if len(words) <= 10 and len(stripped) <= 50:
                # Valid title
                title = stripped
                title_index = i
                break
            else:
                # Too long → it's not a title; keep it as part of the text
                title = None
                title_index = -1   # signal that all lines are text
                break
    else:
        # No suitable line found at all (e.g., empty file or only comments)
        title = None
        title_index = -1

    # Build the full text based on title_index
    if title_index is None:
        # No candidate found (should not happen, but handle gracefully)
        text = ''.join(lines).strip()
    elif title_index >= 0:
        # Valid title found – text starts after the title line
        text = ''.join(lines[title_index+1:]).strip()
    else:  # title_index == -1
        # The candidate was too long → all lines (including that one) are text
        text = ''.join(lines).strip()

    return title, text

def find_image_for_chapter(chapter_num):
    """
    Checks for chapter_num.jpg or chapter_num.png in IMAGES_DIR.
    Returns (image_path, mime_type) or (None, None) if not found.
    """
    for ext in ['.jpg', '.png']:
        fname = f"{chapter_num}{ext}"
        path = os.path.join(IMAGES_DIR, fname)
        if os.path.isfile(path):
            mime = 'image/jpeg' if ext == '.jpg' else 'image/png'
            return path, mime
    return None, None

def encode_image_base64(image_path):
    """Reads an image file and returns its base64-encoded string."""
    with open(image_path, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode('ascii')

def split_paragraphs(text):
    """
    Splits text into paragraphs (by double newline) and returns a list.
    Each paragraph is stripped and internal newlines replaced with spaces.
    """
    raw_paras = re.split(r'\n\s*\n', text)
    paragraphs = []
    for para in raw_paras:
        para = para.strip()
        if para:
            para = ' '.join(para.splitlines())
            paragraphs.append(para)
    return paragraphs

# ===== MAIN SCRIPT =====

def main():
    # 1. Collect and sort chapter files
    pattern = os.path.join(CHAPTERS_DIR, "*.txt")
    chapter_files = glob.glob(pattern)
    if not chapter_files:
        print(f"Нет файлов .txt в папке '{CHAPTERS_DIR}'.")
        return

    def extract_number(fname):
        base = os.path.basename(fname)
        match = re.search(r'\d+', base)
        return int(match.group()) if match else 0

    chapter_files.sort(key=extract_number)

    # 2. Prepare data for each chapter
    chapters = []          # list of dicts: num, final_title, text, image_path, image_mime

    for fpath in chapter_files:
        base = os.path.basename(fpath)
        num_match = re.search(r'\d+', base)
        if not num_match:
            print(f"Пропускаем файл без номера: {base}")
            continue
        chap_num = int(num_match.group())

        raw_title, text = extract_title_and_text(fpath, chap_num)

        # Build the final title: always include the chapter number
        if raw_title:
            final_title = f"{raw_title}"
        else:
            final_title = f"Глава {chap_num}."

        img_path, img_mime = find_image_for_chapter(chap_num)

        chapters.append({
            'num': chap_num,
            'final_title': final_title,
            'text': text,
            'image_path': img_path,
            'image_mime': img_mime
        })

    # 3. Build FB2 XML
    xml_parts = []
    xml_parts.append('<?xml version="1.0" encoding="utf-8"?>\n')
    xml_parts.append('<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" '
                     'xmlns:l="http://www.w3.org/1999/xlink">\n')

    # ---- Description ----
    doc_id = str(uuid.uuid4())
    today = datetime.now().strftime('%Y-%m-%d')
    xml_parts.append('  <description>\n')
    xml_parts.append('    <title-info>\n')
    xml_parts.append(f'      <book-title>{escape(BOOK_TITLE)}</book-title>\n')
    xml_parts.append('      <author>\n')
    xml_parts.append(f'        <first-name>{escape(BOOK_AUTHOR_FIRST)}</first-name>\n')
    xml_parts.append(f'        <last-name>{escape(BOOK_AUTHOR_LAST)}</last-name>\n')
    xml_parts.append('      </author>\n')
    xml_parts.append(f'      <lang>{BOOK_LANG}</lang>\n')
    xml_parts.append('    </title-info>\n')
    xml_parts.append('    <document-info>\n')
    xml_parts.append('      <author>\n')
    xml_parts.append(f'        <first-name>{escape(BOOK_AUTHOR_FIRST)}</first-name>\n')
    xml_parts.append(f'        <last-name>{escape(BOOK_AUTHOR_LAST)}</last-name>\n')
    xml_parts.append('      </author>\n')
    xml_parts.append('      <program-used>Python FB2 generator</program-used>\n')
    xml_parts.append(f'      <date>{today}</date>\n')
    xml_parts.append(f'      <id>{doc_id}</id>\n')
    xml_parts.append('      <version>1.0</version>\n')
    xml_parts.append('    </document-info>\n')
    xml_parts.append('  </description>\n')

    # ---- Body ----
    xml_parts.append('  <body>\n')

    for chap in chapters:
        xml_parts.append('    <section>\n')
        # Title (now includes chapter number)
        xml_parts.append(f'      <title><p>{escape(chap["final_title"])}</p></title>\n')
        # Image (if any)
        if chap['image_path']:
            img_id = f"img{chap['num']}"
            xml_parts.append(f'      <image l:href="#{img_id}"/>\n')
        # Chapter text as paragraphs
        paragraphs = split_paragraphs(chap['text'])
        for para in paragraphs:
            xml_parts.append(f'      <p>{escape(para)}</p>\n')
        xml_parts.append('    </section>\n')

    xml_parts.append('  </body>\n')

    # ---- Binary images ----
    for chap in chapters:
        if chap['image_path']:
            img_id = f"img{chap['num']}"
            mime = chap['image_mime']
            b64_data = encode_image_base64(chap['image_path'])
            xml_parts.append(f'  <binary id="{img_id}" content-type="{mime}">\n')
            # Wrap base64 at 76 chars for readability (optional)
            for i in range(0, len(b64_data), 76):
                xml_parts.append(b64_data[i:i+76] + '\n')
            xml_parts.append('  </binary>\n')

    xml_parts.append('</FictionBook>\n')

    # 4. Write to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(xml_parts)

    print(f"FB2 книга успешно создана: {OUTPUT_FILE}")
    print(f"Обработано глав: {len(chapters)}")

if __name__ == "__main__":
    main()