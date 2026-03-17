import os
import json
import time
from pathlib import Path
import logging
import random
import requests
import io
from PIL import Image

class Config:
    SHORT_NAME = "images"
    PROMPTS_DIR = Path("prompts")
    OUTPUT_DIR = Path("images")
    WORKFLOW_PATH = Path("workflows/workflow_klein_chapters.json")
    PROGRESS_FILE = Path(f"progress_images_{SHORT_NAME}.json")
    
    # ComfyUI API Configuration
    PROMPT_URL = 'http://127.0.0.1:8188/prompt'
    HISTORY_URL = 'http://127.0.0.1:8188/history?max_items=64'
    VIEW_URL_BASE = 'http://127.0.0.1:8188/view'
    
    HEADERS = {
        'Accept': '*/*',
        'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8,zh-CN;q=0.7,zh-TW;q=0.6,zh;q=0.5',
        'Cache-Control': 'max-age=0',
        'Comfy-User': '',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
    }

class ImageGenerationManager:
    def __init__(self, config: Config):
        self.config = config
        self.progress_data = {}
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('image_generation.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_directories(self):
        """Ensure necessary directories exist"""
        self.config.PROMPTS_DIR.mkdir(exist_ok=True)
        self.config.OUTPUT_DIR.mkdir(exist_ok=True)
        os.makedirs(os.path.dirname(self.config.WORKFLOW_PATH), exist_ok=True)

    def load_progress(self) -> int:
        """Load image generation progress from JSON file"""
        if self.config.PROGRESS_FILE.exists():
            try:
                with open(self.config.PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    self.progress_data = json.load(f)
                last_episode = self.progress_data.get('last_episode', 1)
                self.logger.info(f"Resuming from episode {last_episode + 1}")
                return last_episode
            except Exception as e:
                self.logger.error(f"Error loading progress: {e}")
        
        self.progress_data = {
            'last_episode': 0,
            'started_at': time.strftime("%Y-%m-%d %H:%M:%S"),
            'completed_episodes': [],
            'failed_episodes': []
        }
        return 0

    def save_progress(self, episode_id: int, success: bool = True):
        """Save generation progress to JSON file"""
        if success:
            self.progress_data['last_episode'] = episode_id
            if episode_id not in self.progress_data['completed_episodes']:
                self.progress_data['completed_episodes'].append(episode_id)
            if episode_id in self.progress_data['failed_episodes']:
                self.progress_data['failed_episodes'].remove(episode_id)
        else:
            if episode_id not in self.progress_data['failed_episodes']:
                self.progress_data['failed_episodes'].append(episode_id)
        
        self.progress_data['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(self.config.PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.progress_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving progress: {e}")

    def update_noise_seed(self, data, new_seed):
        """Recursively finds all 'noise_seed' keys and updates them."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "noise_seed":
                    data[key] = new_seed
                else:
                    self.update_noise_seed(value, new_seed)
        elif isinstance(data, list):
            for item in data:
                self.update_noise_seed(item, new_seed)

    def inject_prompt(self, data, real_prompt):
        """Recursively search for the %prompt% needle and replace it."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and "%prompt%" in value:
                    data[key] = value.replace("%prompt%", real_prompt)
                else:
                    self.inject_prompt(value, real_prompt)
        elif isinstance(data, list):
            for item in data:
                self.inject_prompt(item, real_prompt)

    def get_history_uuids(self) -> set:
        """Fetch current history UUIDs from ComfyUI."""
        try:
            response = requests.get(self.config.HISTORY_URL, headers=self.config.HEADERS)
            return set(response.json().keys())
        except Exception as e:
            self.logger.error(f"Error getting history: {e}")
            return set()

    def process_episode(self, episode_id: int) -> bool:
        prompt_path = self.config.PROMPTS_DIR / f"{episode_id}.txt"
        
        if not prompt_path.exists():
            return False

        with open(prompt_path, 'r', encoding='utf-8') as f:
            real_prompt = f.read().strip()

        # Read the workflow JSON template
        try:
            with open(self.config.WORKFLOW_PATH, 'r', encoding='utf-8') as file:
                workflow_data = json.load(file)
        except Exception as e:
            self.logger.error(f"Failed to load workflow.json: {e}")
            return False

        # Randomize seed and inject the prompt text
        new_seed = random.randint(0, 10**5)
        self.update_noise_seed(workflow_data, new_seed)
        self.inject_prompt(workflow_data, real_prompt)
        print(real_prompt)

        pre_uuids = self.get_history_uuids()
        
        # Send prompt payload
        payload = {"prompt": workflow_data}
        try:
            response = requests.post(
                self.config.PROMPT_URL,
                headers=self.config.HEADERS,
                json=payload,
                timeout=30
            )
            if response.status_code != 200:
                self.logger.error(f"Failed to send prompt: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"API Error sending prompt: {e}")
            return False

        # Wait for the async generation and poll history
        self.logger.info(f"Prompt sent for Episode {episode_id}. Waiting for ComfyUI...")
        
        return self.poll_and_save_image(pre_uuids, episode_id)

    def poll_and_save_image(self, pre_uuids: set, episode_id: int) -> bool:
        """Polls ComfyUI history until the new job finishes, then downloads the image."""
        timeout = time.time() + 180 # 3 min timeout just in case
        
        while time.time() < timeout:
            time.sleep(2) # Polling interval
            try:
                current_uuids = self.get_history_uuids()
                new_uuids = current_uuids - pre_uuids
                
                for uuid in new_uuids:
                    response = requests.get(self.config.HISTORY_URL, headers=self.config.HEADERS)
                    history = response.json().get(uuid, {})
                    outputs = history.get('outputs', {})
                    
                    for node_id in outputs:
                        images = outputs[node_id].get('images', [])
                        for image in images:
                            filename = image.get('filename')
                            if filename:
                                return self.download_and_save(filename, episode_id)
                pre_uuids.update(current_uuids)
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
        
        self.logger.error(f"Timeout waiting for ComfyUI on Episode {episode_id}")
        return False

    def download_and_save(self, filename: str, episode_id: int) -> bool:
        """Fetch the generated image from ComfyUI and save it locally."""
        rand = random.random()
        view_url = f"{self.config.VIEW_URL_BASE}?filename={filename}&subfolder=&type=output&rand={rand}"
        
        try:
            response = requests.get(view_url)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                
                # Convert to RGB to ensure saving as JPEG works smoothly
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                save_path = self.config.OUTPUT_DIR / f"{episode_id}.jpg"
                img.save(save_path, "JPEG", quality=95)
                self.logger.info(f"Saved generated image to {save_path}")
                return True
        except Exception as e:
            self.logger.error(f"Error fetching image {filename}: {e}")
        return False

    def run(self):
        self.setup_directories()
        last_processed = self.load_progress()
        
        # Look for episode IDs inside the prompts directory
        available_episodes = []
        for file in self.config.PROMPTS_DIR.glob('*.txt'):
            try:
                available_episodes.append(int(file.stem))
            except ValueError:
                pass
                
        episodes_to_process = sorted([
            ep for ep in available_episodes 
            if ep > last_processed and ep not in self.progress_data.get('completed_episodes', [])
        ])
        
        if not episodes_to_process:
            self.logger.info("No new episodes to process.")
            return

        for episode_id in episodes_to_process:
            self.logger.info(f"\n--- Generating Image for Chapter {episode_id} ---")
            
            success = self.process_episode(episode_id)
            self.save_progress(episode_id, success=success)
            
            if success:
                self.logger.info(f"Successfully processed Chapter {episode_id}")
            else:
                self.logger.warning(f"Failed to process Chapter {episode_id}")

def main():
    config = Config()
    manager = ImageGenerationManager(config)
    manager.run()

if __name__ == "__main__":
    main()