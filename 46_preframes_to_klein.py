import os
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
    JSON_PROMPTS_DIR = Path("jsons/json_frame_prompts")
    CHAR_DESC_PATH = Path("jsons/characters_descriptions.json")
    PREFRAMES_DIR = Path("images/preframes")
    OUTPUT_BASE_DIR = Path("images/frames")
    WORKFLOW_PATH = Path("workflows/workflow_klein_frames.json")
    PROGRESS_FILE = Path("progress_klein_frames.json")
    
    # ComfyUI API
    PROMPT_URL = 'http://127.0.0.1:8188/prompt'
    HISTORY_URL = 'http://127.0.0.1:8188/history'
    VIEW_URL_BASE = 'http://127.0.0.1:8188/view'
    UPLOAD_URL = 'http://127.0.0.1:8188/upload/image'
    
    HEADERS = {'Content-Type': 'application/json'}

class VNImageManager:
    def __init__(self):
        self.setup_logging()
        self.char_descriptions = self.load_json(Config.CHAR_DESC_PATH)
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
        return {"completed_frames": []} # Format: "episode_id/frame_id"

    def save_progress(self, ep_id, frame_id):
        key = f"{ep_id}/{frame_id}"
        if key not in self.progress["completed_frames"]:
            self.progress["completed_frames"].append(key)
            with open(Config.PROGRESS_FILE, 'w') as f:
                json.dump(self.progress, f, indent=2)

    def upload_image(self, image_path):
        """Uploads the preframe to ComfyUI so the API can reference it."""
        with open(image_path, 'rb') as f:
            files = {'image': (image_path.name, f)}
            resp = requests.post(Config.UPLOAD_URL, files=files)
            return resp.json().get('name')

    def construct_prompt(self, char_ids, raw_prompt_text):
        """
        Gathers character descriptions and applies spatial logic.
        Only includes characters that are mentioned in raw_prompt_text.
        Positions are based on the full char_ids list.
        """
        # Parse the prompt to extract per-character text
        char_to_prompt = self._parse_prompt_by_character(raw_prompt_text)
        mentioned_chars = set(char_to_prompt.keys())

        # If it's a single character, return just the raw prompt text
        # (but we still need to ensure it's mentioned)
        if len(char_ids) == 1:
            if char_ids[0] in mentioned_chars:
                return raw_prompt_text
            else:
                return ""  # No mentioned characters in a single‑char scene? Should not happen.

        # Limit to maximum 3 characters
        full_char_ids = char_ids[:3]  # Keep only first 3 characters for positioning
        count = len(full_char_ids)

        final_parts = []

        for i, char_id in enumerate(full_char_ids):
            if char_id not in mentioned_chars:
                continue  # Skip characters not mentioned in the prompt

            desc = self.char_descriptions.get(char_id, "")
            current_prompt = char_to_prompt.get(char_id, "").strip()

            # Position Logic (based on full list of characters)
            if count == 1:
                pos_prefix = "\nNow "
            elif count == 2:
                pos_prefix = "\nNow on the left " if i == 0 else "\nNow on the right "
            else:  # 3 characters
                positions = ["\nNow on the left ", "\nNow in the middle ", "\nNow on the right "]
                pos_prefix = positions[i] if i < 3 else "\nNow "

            # Build the part for this character
            final_parts.append(f"{char_id} {desc}{pos_prefix}{current_prompt}")

        return " ".join(final_parts)

    def _parse_prompt_by_character(self, raw_prompt):
        """
        Splits a multi‑character prompt into a dictionary mapping character name
        to their dialogue/action text.
        """
        if not raw_prompt:
            return {}
        lines = raw_prompt.strip().split('\n')
        char_to_prompt = {}
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                char_name = parts[0].strip()
                text = parts[1].strip()
                if char_name in char_to_prompt:
                    # Concatenate multiple lines for the same character with a space
                    char_to_prompt[char_name] += ' ' + text
                else:
                    char_to_prompt[char_name] = text
            # Lines without a colon are ignored (assumed not character‑specific)
        return char_to_prompt
    
    def update_workflow(self, workflow, prompt_text, image_name, seed):
        """
        Recursively injects variables into the workflow JSON.
        Matches your specific workflow's logic.
        """
        def _inject(data):
            if isinstance(data, dict):
                for k, v in data.items():
                    if k == "noise_seed" or k == "seed": data[k] = seed
                    if isinstance(v, str):
                        if "%prompt%" in v: data[k] = v.replace("%prompt%", prompt_text)
                        if "%input_image%" in v: data[k] = image_name
                    _inject(v)
            elif isinstance(data, list):
                for item in data: _inject(item)
        
        _inject(workflow)
        return workflow

    def process_frame(self, ep_id, frame_id, data):
        frame_key = f"{ep_id}/{frame_id}"
        if frame_key in self.progress["completed_frames"]:
            return

        out_dir = Config.OUTPUT_BASE_DIR / str(ep_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{frame_id}.jpg"
        
        preframe_path = Config.PREFRAMES_DIR / str(ep_id) / f"{frame_id}.jpg"
        action = data.get("action_type")

        # RULE 1: Direct Copy
        if action in ["background_empty", "direct_speech"]:
            if preframe_path.exists():
                shutil.copy(preframe_path, out_path)
                self.logger.info(f"Copied preframe: {frame_key}")
                self.save_progress(ep_id, frame_id)
            return

        # RULE 2: Image2Image
        if action == "background_with_chars":
            self.logger.info(f"Generating I2I for {frame_key}...")
            
            # Prepare Prompt
            full_prompt = self.construct_prompt(data["character_ids"], data["prompt"])
            print(f"#Episode {ep_id}, frame {frame_id}, prompt: {full_prompt}")
            
            # Upload Image to ComfyUI
            comfy_img_name = self.upload_image(preframe_path)
            #print("uploaded comfy_img_name")
            #print(comfy_img_name)
            
            # Load Workflow template
            workflow = self.load_json(Config.WORKFLOW_PATH)
            workflow = self.update_workflow(workflow, full_prompt, comfy_img_name, random.randint(0, 10**9))

            # Send to API
            pre_uuids = set(requests.get(f"{Config.HISTORY_URL}?max_items=10").json().keys())
            requests.post(Config.PROMPT_URL, json={"prompt": workflow})

            # Poll for result (Simplified version of your history logic)
            start_time = time.time()
            while time.time() - start_time < 300: # 5 min timeout
                time.sleep(3)
                history = requests.get(f"{Config.HISTORY_URL}?max_items=5").json()
                new_uuids = set(history.keys()) - pre_uuids
                
                if new_uuids:
                    # Logic: pick the newest uuid that has outputs
                    latest_uuid = list(new_uuids)[0]
                    outputs = history[latest_uuid].get('outputs', {})
                    for node_id in outputs:
                        if 'images' in outputs[node_id]:
                            img_data = outputs[node_id]['images'][0]
                            # Download
                            view_url = f"{Config.VIEW_URL_BASE}?filename={img_data['filename']}&subfolder={img_data['subfolder']}&type={img_data['type']}"
                            img_resp = requests.get(view_url)
                            if img_resp.status_code == 200:
                                with Image.open(io.BytesIO(img_resp.content)) as img:
                                    img.convert("RGB").save(out_path, "JPEG", quality=95)
                                self.save_progress(ep_id, frame_id)
                                self.logger.info(f"Generated: {out_path}")
                                return
            self.logger.error(f"Timeout on {frame_key}")

    def run(self):
        # Iterate through episode JSONs
        for json_file in sorted(Config.JSON_PROMPTS_DIR.glob("*.json")):
            ep_id = json_file.stem
            frames_data = self.load_json(json_file)
            
            self.logger.info(f"Starting Episode {ep_id}")
            for frame_id, data in frames_data.items():
                self.process_frame(ep_id, frame_id, data)

if __name__ == "__main__":
    VNImageManager().run()