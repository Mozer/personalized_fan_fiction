import os
import re
import json
import time
import shutil
import random
import requests
import io
import logging
from pathlib import Path
from PIL import Image

class Config:
    # Directories
    PROMPTS_DIR = Path("prompts_for_clothes_change_en")
    CHARS_DIR = Path("images/characters")
    WORKFLOW_PATH = Path("workflows/workflow_klein_clothes.json")
    PROGRESS_FILE = Path("progress_klein_clothes.json")
    
    # ComfyUI API
    PROMPT_URL = 'http://127.0.0.1:8188/prompt'
    HISTORY_URL = 'http://127.0.0.1:8188/history'
    VIEW_URL_BASE = 'http://127.0.0.1:8188/view'
    UPLOAD_URL = 'http://127.0.0.1:8188/upload/image'
    
    HEADERS = {'Content-Type': 'application/json'}

class VNImageManager:
    def __init__(self):
        self.setup_logging()
        self.progress = self.load_progress()

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def load_json(self, path):
        if not path.exists(): return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_progress(self):
        if Config.PROGRESS_FILE.exists():
            return self.load_json(Config.PROGRESS_FILE)
        return {"completed_clothes": []} # Format: "character_id/safe_clothes_name"

    def save_progress(self, char_id, safe_name):
        key = f"{char_id}/{safe_name}"
        if key not in self.progress["completed_clothes"]:
            self.progress["completed_clothes"].append(key)
            with open(Config.PROGRESS_FILE, 'w') as f:
                json.dump(self.progress, f, indent=2)

    def sanitize_filename(self, text):
        """Converts a descriptive string into a safe, underscore-separated filename."""
        # Replace invalid characters (anything not alphanumeric or hyphen) with spaces
        safe_name = re.sub(r'[^a-zA-Z0-9\-]', ' ', text)
        # Split by spaces and join with underscores to collapse multiple spaces
        safe_name = "_".join(safe_name.split())
        return safe_name.lower()

    def upload_image(self, image_path):
        """Uploads the base character image to ComfyUI."""
        with open(image_path, 'rb') as f:
            files = {'image': (image_path.name, f)}
            resp = requests.post(Config.UPLOAD_URL, files=files)
            return resp.json().get('name')

    def update_workflow(self, workflow, prompt_text, image_name, seed):
        """Recursively injects variables into the workflow JSON."""
        def _inject(data):
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in ["noise_seed", "seed"]: data[k] = seed
                    if isinstance(v, str):
                        if "%prompt%" in v: data[k] = v.replace("%prompt%", "Now in "+prompt_text + ". Speaking")
                        if "%input_image%" in v: data[k] = image_name
                    _inject(v)
            elif isinstance(data, list):
                for item in data: _inject(item)
        
        _inject(workflow)
        return workflow

    def process_clothes(self, char_id, clothes_prompt):
        safe_name = self.sanitize_filename(clothes_prompt)
        progress_key = f"{char_id}/{safe_name}"
        
        # 1. Define output directories and paths
        clothes_dir = Config.CHARS_DIR / char_id / "clothes"
        speaking_dir = clothes_dir / "speaking"
        
        clothes_dir.mkdir(parents=True, exist_ok=True)
        speaking_dir.mkdir(parents=True, exist_ok=True)
        
        out_path_1 = clothes_dir / f"{safe_name}.png"
        out_path_2 = speaking_dir / f"{safe_name}.png"
        
        # 2. Check if already exists (Skip generation if it does)
        if out_path_1.exists():
            self.logger.info(f"Skipping: {char_id} '{safe_name}' already exists.")
            return

        # 3. Verify base image exists
        base_image_path = Config.CHARS_DIR / f"{char_id}.jpeg"
        if not base_image_path.exists():
            self.logger.warning(f"Missing base image for {char_id}: {base_image_path}")
            return

        self.logger.info(f"Generating clothes for {char_id}: '{clothes_prompt}' -> {safe_name}.png")
        
        # 4. Upload base image to ComfyUI
        comfy_img_name = self.upload_image(base_image_path)
        
        # 5. Prepare and send Workflow
        workflow = self.load_json(Config.WORKFLOW_PATH)
        workflow = self.update_workflow(workflow, clothes_prompt, comfy_img_name, random.randint(0, 10**9))

        pre_uuids = set(requests.get(f"{Config.HISTORY_URL}?max_items=10").json().keys())
        requests.post(Config.PROMPT_URL, json={"prompt": workflow})

        # 6. Poll for result
        start_time = time.time()
        while time.time() - start_time < 300: # 5 min timeout
            time.sleep(3)
            history = requests.get(f"{Config.HISTORY_URL}?max_items=5").json()
            new_uuids = set(history.keys()) - pre_uuids
            
            if new_uuids:
                latest_uuid = list(new_uuids)[0]
                outputs = history[latest_uuid].get('outputs', {})
                for node_id in outputs:
                    if 'images' in outputs[node_id]:
                        img_data = outputs[node_id]['images'][0]
                        view_url = f"{Config.VIEW_URL_BASE}?filename={img_data['filename']}&subfolder={img_data['subfolder']}&type={img_data['type']}"
                        img_resp = requests.get(view_url)
                        
                        if img_resp.status_code == 200:
                            # 7. Save Image to both locations
                            with Image.open(io.BytesIO(img_resp.content)) as img:
                                img.save(out_path_1, "PNG")
                            
                            shutil.copy(out_path_1, out_path_2)
                            
                            self.save_progress(char_id, safe_name)
                            self.logger.info(f"Successfully saved to:\n  - {out_path_1}\n  - {out_path_2}")
                            return
        self.logger.error(f"Timeout on generation for {char_id}: {clothes_prompt}")

    def run(self):
        # Iterate through all .txt files
        for txt_file in sorted(Config.PROMPTS_DIR.glob("*.txt")):
            ep_id = txt_file.stem
            self.logger.info(f"--- Starting Episode {ep_id} ---")
            
            with open(txt_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Extract JSON payload from the line (e.g., "3. {...}")
                    match = re.match(r'^\d+\.\s*(\{.*\})$', line)
                    if not match:
                        continue
                        
                    try:
                        data = json.loads(match.group(1))
                        char_clothes = data.get("character_clothes", {})
                        
                        # Process each character found in the line
                        for char_id, details in char_clothes.items():
                            clothes_prompt = details.get("clothes")
                            if clothes_prompt:
                                self.process_clothes(char_id, clothes_prompt)
                                
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to parse JSON in file {txt_file.name}: {line}")

if __name__ == "__main__":
    VNImageManager().run()