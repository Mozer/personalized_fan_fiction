# put char sprites on backgrounds to make preframes

import os
import json
import time
import shutil
from pathlib import Path
import logging
from PIL import Image
import random
import re
from typing import List, Optional

class Config:
    SHORT_NAME = "preframes"
    
    # Updated paths based on your folder structure
    JSON_DIR = Path("jsons/json_frame_prompts")
    LOCATIONS_DIR = Path("images/locations")
    CHARACTERS_DIR = Path("images/characters")
    FRAMES_DIR = Path("images/preframes")
    
    PROGRESS_FILE = Path(f"progress_{SHORT_NAME}.json")
    
    # Constants
    BG_WIDTH = 1488
    BG_HEIGHT = 832
    CHAR_HEIGHT = 832

class ImageGenerationManager:
    def __init__(self, config: Config):
        self.config = config
        self.progress_data = {}
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('frame_generation.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_directories(self):
        """Ensure necessary directories exist"""
        self.config.JSON_DIR.mkdir(parents=True, exist_ok=True)
        self.config.LOCATIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.config.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
        self.config.FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    def load_progress(self) -> int:
        """Load image generation progress from JSON file"""
        if self.config.PROGRESS_FILE.exists():
            try:
                with open(self.config.PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    self.progress_data = json.load(f)
                last_episode = self.progress_data.get('last_episode', 0)
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

    def get_existing_file(self, base_path: Path) -> Path:
        """Helper to find a file checking multiple extensions."""
        for ext in ['.jpeg', '.jpg', '.png']:
            p = base_path.with_suffix(ext)
            if p.exists():
                return p
        return None

    def process_episode(self, episode_id: int) -> bool:
        json_path = self.config.JSON_DIR / f"{episode_id}.json"
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                frames_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read JSON for episode {episode_id}: {e}")
            return False

        # Create output directory for this episode
        episode_out_dir = self.config.FRAMES_DIR / str(episode_id)
        episode_out_dir.mkdir(parents=True, exist_ok=True)

        for frame_id, data in frames_data.items():
            try:
                self.process_frame(episode_id, frame_id, data, episode_out_dir)
            except Exception as e:
                self.logger.error(f"Failed to process frame {frame_id} in episode {episode_id}: {e}")
                return False
                
        return True

    def get_speaking_variants(self, character_id: str, clothes_name: str) -> List[Path]:
        """Return all matching image paths in the character's speaking folder."""
        speaking_dir = self.config.CHARACTERS_DIR / character_id / "clothes" / "speaking"
        if not speaking_dir.exists():
            return []
        valid_ext = {'.png', '.jpg', '.jpeg'}
        variants = []
        for file in speaking_dir.iterdir():
            if file.is_file() and file.suffix.lower() in valid_ext:
                if file.stem.startswith(clothes_name):
                    variants.append(file)
        return variants

    def get_regular_clothes_variants(self, character_id: str, clothes_name: str) -> List[Path]:
        """Return all matching image paths in the character's regular clothes folder."""
        clothes_dir = self.config.CHARACTERS_DIR / character_id / "clothes/speaking"
        if not clothes_dir.exists():
            return []
        valid_ext = {'.png', '.jpg', '.jpeg'}
        variants = []
        for file in clothes_dir.iterdir():
            if file.is_file() and file.suffix.lower() in valid_ext:
                if file.stem.startswith(clothes_name):
                    variants.append(file)
        return variants

    def sanitize_filename(self, text):
        """Converts a descriptive string into a safe, underscore-separated filename."""
        # Replace invalid characters (anything not alphanumeric or hyphen) with spaces
        safe_name = re.sub(r'[^a-zA-Z0-9\-]', ' ', text)
        # Split by spaces and join with underscores to collapse multiple spaces
        safe_name = "_".join(safe_name.split())
        return safe_name.lower()
        
    def process_frame(self, episode_id: int, frame_id: str, data: dict, output_dir: Path):
        action_type = data.get("action_type")
        location_id = data.get("location_id", "living_room")

        # 1. Background resolution (unchanged) ...
        bg_path = self.get_existing_file(self.config.LOCATIONS_DIR / location_id)
        if not bg_path:
            self.logger.warning(f"Location '{location_id}' not found. Defaulting to living_room.")
            bg_path = self.get_existing_file(self.config.LOCATIONS_DIR / "living_room")
            if not bg_path:
                raise FileNotFoundError("Even the default living_room background is missing!")

        output_path = output_dir / f"{frame_id}.jpg"

        if action_type == "background_empty":
            bg_img = Image.open(bg_path).convert("RGB")
            bg_img.save(output_path, "JPEG", quality=95)
            self.logger.info(f"Saved empty background frame: {output_path}")
            return

        if action_type in ["direct_speech", "background_with_chars"]:
            bg_img = Image.open(bg_path).convert("RGBA")

            char_ids = data.get("character_ids", [])[:3]
            clothes_data = data.get("character_clothes", {})

            char_images = []

            for cid in char_ids:
                cloth_name = clothes_data.get(cid, {}).get("clothes", "base")
                cloth_name_safe = self.sanitize_filename(cloth_name)
                cloth_path = None

                # ----- DIRECT SPEECH: try speaking variants, then fallback with randomization -----
                if action_type == "direct_speech":
                    variants = self.get_speaking_variants(cid, cloth_name_safe)
                    if variants:
                        cloth_path = random.choice(variants)
                        self.logger.debug(f"Selected speaking variant for {cid} ({cloth_name}): {cloth_path.name}")
                    else:
                        self.logger.warning(
                            f"No speaking variants for {cid} with clothes '{cloth_name}'. "
                            "Trying regular clothes variants."
                        )
                        # Try random regular variant of the same clothes
                        reg_variants = self.get_regular_clothes_variants(cid, cloth_name)
                        
                        if reg_variants:
                            cloth_path = random.choice(reg_variants)
                            self.logger.debug(f"Fallback to regular variant for {cid} ({cloth_name}): {cloth_path.name}")
                        else:
                            # No regular variant for desired clothes → fallback to random base variant
                            base_variants = self.get_regular_clothes_variants(cid, "base")
                            if base_variants:
                                cloth_path = random.choice(base_variants)
                                print(cloth_path)
                                self.logger.debug(f"Fallback to base variant for {cid}: {cloth_path.name}")
                            else:
                                self.logger.error(f"No clothes found for {cid} (including base). Skipping character.")
                                continue

                # ----- BACKGROUND_WITH_CHARS: original deterministic logic (no randomization) -----
                else:  # action_type == "background_with_chars"
                    base_cloth_path = self.config.CHARACTERS_DIR / cid / "clothes" / cloth_name_safe
                    print(base_cloth_path)
                    cloth_path = self.get_existing_file(base_cloth_path)

                    if not cloth_path:
                        self.logger.warning(f"Clothes '{cloth_name}' for {cid} not found. Defaulting to 'base'.")
                        cloth_path = self.get_existing_file(self.config.CHARACTERS_DIR / cid / "clothes" / "base")

                    if not cloth_path:
                        self.logger.error(f"Base clothes for {cid} missing. Skipping character.")
                        continue

                # Open and resize character sprite (common for both cases)
                char_img = Image.open(cloth_path).convert("RGBA")
                aspect_ratio = char_img.width / char_img.height
                new_width = int(self.config.CHAR_HEIGHT * aspect_ratio)
                char_img = char_img.resize((new_width, self.config.CHAR_HEIGHT), Image.Resampling.LANCZOS)
                char_images.append(char_img)

            # 3. Compositing (unchanged) ...
            if char_images:
                total_char_width = sum(img.width for img in char_images)
                total_padding_space = self.config.BG_WIDTH - total_char_width
                padding_segment = total_padding_space // (len(char_images) + 1)

                current_x = padding_segment
                y_pos = self.config.BG_HEIGHT - self.config.CHAR_HEIGHT

                for char_img in char_images:
                    bg_img.alpha_composite(char_img, (current_x, y_pos))
                    current_x += char_img.width + padding_segment

            # 4. Save (unchanged)
            bg_img.convert("RGB").save(output_path, "JPEG", quality=95)
            self.logger.info(f"Saved frame {frame_id} ({len(char_images)} chars): {output_path}")

    def run(self):
        self.setup_directories()
        last_processed = self.load_progress()
        
        # Look for episode IDs based on json files
        available_episodes = []
        for file in self.config.JSON_DIR.glob('*.json'):
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
            self.logger.info(f"\n--- Generating Frames for Episode {episode_id} ---")
            
            success = self.process_episode(episode_id)
            self.save_progress(episode_id, success=success)
            
            if success:
                self.logger.info(f"Successfully processed Episode {episode_id}")
            else:
                self.logger.warning(f"Failed to process Episode {episode_id}")

def main():
    config = Config()
    manager = ImageGenerationManager(config)
    manager.run()

if __name__ == "__main__":
    main()