# en text into text for text2image AI (klein-9b-edit)
# recommended LLM: Qwen3.5-27B-Q6_K.gguf with thinking off

import os
import json
import time
from pathlib import Path
import logging
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI
from openai.types.chat import ChatCompletion
import random

# Configuration
class Config:
    SHORT_NAME = "prompts_for_lines_locations_char"
    EPISODES_INPUT_DIR = Path("textfortts_en_enumerated")
    EPISODES_OUTPUT_DIR = Path(SHORT_NAME)    
    OUTPUT_FILE = Path(SHORT_NAME+"_en.txt")
    PROGRESS_FILE = Path("progress_"+SHORT_NAME+".json")
    
    # OpenAI/LLM API Configuration
    #API_BASE_URL = "https://api.mistral.ai/v1" 
    API_BASE_URL = "http://127.0.0.1:8080/v1" 
    API_KEY = "None"  # use none with llama.cpp server
    MODEL = "mistral-large-latest"  # or "gpt-3.5-turbo", "claude-3-haiku", etc.
    
     # API settings
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    TIMEOUT = 900  # seconds, 15 min
    MAX_TOKENS = 10536  # Adjust based on model context window
    temperature = 0.5
    frequency_penalty = 1.1

    USER_PROMPT_TEMPLATE = """
- Analyze given INPUT_TEXT and for each line create a json set describing location and characters are present in this line: {{location:"location_id", character_ids:{{[character_ids, ...]}}}}
- if no characters or location are present in this line, use none, [location:None, character_ids:[]]
- If no one mentioned for the line - try to guess.

E.g. input
10. Sunny and Anna are sleeping. Then go to kitchen.
11. Anna: Where is he?
12. She asked suddenly, her eyes wide, standing in the kitchen.
13. Alex looked up from the table.
14. She stepped forward, standing near his table.

output:
10. {{"location": "bedroom", "character_ids": {{["Anna", "Sunny"] }}}}
11. {{"location": "kitchen", "character_ids": {{["Anna"]}}}}
12. {{"location": "kitchen", "character_ids": {{["Anna"]}}}}
13. {{"location": "kitchen", "character_ids": {{["Anna", "Alex"]}}}}
14. {{"location": "kitchen", "character_ids": {{["Anna", "Alex"]}}}}


Use following location_ids:
["it_basement_office", "reynholm_industries_exterior", "server_room",  "executive_floor_lobby", "cubicals", "jens_office", "boss_office"]
if location is not in this list, make it up, use simple words and underscore.

Use following character_ids:
- Roy - is a work-shy Irish IT technician and geek who spends much of his time playing video games or reading comics in the office.
- Moss - is a computer nerd, socially awkward  and his complex and in-depth knowledge of specialised technical subjects, including chemistry and electronic engineering.
- Jen - becomes Head of the IT department de facto 'Relationship Manager', she knows very little about electronics and computers.
- Denholm - director of Reynholm Industries at chapters 1-8, he enjoys setting up initiatives intended to boost performance in a company. He dies at chapter 7 by walking out of the window.
- Douglas - is introduced only in Chapter 8 where he takes over Reynholm Industries after his father Denholm's death. He described as awful, sex-crazed, and a serial dater. He has a history of sexual harassment, He flirts with Jen.
- Rachel - is a mild-mannered, 20yo posh-accented goth woman who resides in the IT department server room, she discovered black metal band Cradle of Filth and changed her appearance
if character_id is not in this list, make it up, use a single word name, don't use underscore, just a simple short name, like John.

In your response, return only the text with line numbers and valid jsons for each line
INPUT_TEXT:
{funny_text} End of INPUT_TEXT.
"""

class TranslationManager:
    def __init__(self, config: Config):
        self.config = config
        self.progress_data: Dict[str, Any] = {}
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('translation.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=config.API_KEY,
            base_url=config.API_BASE_URL
        )
        
    def setup_directories(self):
        """Ensure necessary directories and files exist"""
        self.config.EPISODES_INPUT_DIR.mkdir(exist_ok=True)
        self.config.EPISODES_OUTPUT_DIR.mkdir(exist_ok=True)
        
        # Create output file if it doesn't exist
        if not self.config.OUTPUT_FILE.exists():
            self.config.OUTPUT_FILE.write_text(self.config.SHORT_NAME+"\n"+"=== English Translation ===\n\n", encoding='utf-8')
    
    def load_progress(self) -> int:
        """Load translation progress from JSON file"""
        if self.config.PROGRESS_FILE.exists():
            try:
                with open(self.config.PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    self.progress_data = json.load(f)
                last_episode = self.progress_data.get('last_episode', 1)
                self.logger.info(f"Resuming translation from episode {last_episode + 1}")
                return last_episode
            except Exception as e:
                self.logger.error(f"Error loading progress: {e}")
        
        # Default starting point
        self.progress_data = {
            'last_episode': 0,
            'started_at': time.strftime("%Y-%m-%d %H:%M:%S"),
            'completed_episodes': [],
            'failed_episodes': []
        }
        return 0
    
    def save_progress(self, episode_id: int, success: bool = True):
        """Save translation progress to JSON file"""
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
    
    def read_episode_file(self, episode_id: int) -> Optional[str]:
        """Read funny text from episode file"""
        funny_file_path = self.config.EPISODES_INPUT_DIR / f"{episode_id}.txt"
        
        if not funny_file_path.exists():
            self.logger.error(f"Funny episode file not found: {funny_file_path}")
            return None
        
        try:
            with open(funny_file_path, 'r', encoding='utf-8') as f:
                funny_text = f.read()
            return funny_text
        except Exception as e:
            self.logger.error(f"Error reading episode {episode_id}: {e}")
            return None
    
    def extract_title_from_content(self, content: str) -> str:
        """Extract title from content (first line before empty line)"""
        lines = content.strip().split('\n')
        if lines:
            # First non-empty line is usually the title
            for line in lines:
                if line.strip():
                    return line.strip()
        return ""
    
    def prepare_translation_prompt(self, funny_text: str) -> str:
        """Prepare the prompt for translation"""
        return self.config.USER_PROMPT_TEMPLATE.format(
            funny_text=funny_text
        )
    
    def translate_text(self, funny_text: str, episode_id: int) -> Optional[str]:
        """Send text to LLM for translation with retry logic"""
        prompt = self.prepare_translation_prompt(funny_text)
        
        for attempt in range(self.config.MAX_RETRIES):
            try:
                self.logger.info(f"Translating episode {episode_id} (attempt {attempt + 1}/{self.config.MAX_RETRIES})...")
                
                response = self.client.chat.completions.create(
                    model=self.config.MODEL,
                    messages=[                        
                        {
                            "role": "user", 
                            "content": prompt,
                        }
                    ],                   
                    temperature=self.config.temperature,
                    frequency_penalty=self.config.frequency_penalty,
                    max_tokens=self.config.MAX_TOKENS,
                    timeout=self.config.TIMEOUT,
                    extra_body={
                        "chat_template_kwargs": { 
                            "source_lang_code": "en", 
                            "target_lang_code": "ru"
                        }
                    }
                )
                
                translation = response.choices[0].message.content.strip()
                
                translation = translation.replace("End of chapter.", "") # without these tags gemma doubles the text sometimes
                
                if translation:
                    self.logger.info(f"Successfully translated episode {episode_id}")
                    return translation
                else:
                    self.logger.warning(f"Empty translation received for episode {episode_id}")
                    
            except Exception as e:
                self.logger.error(f"Translation attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.MAX_RETRIES - 1:
                    wait_time = self.config.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    self.logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"All translation attempts failed for episode {episode_id}")
        
        return None
    
    def format_translation_for_output(self, episode_id: int, english_translation: str) -> str:
        """Format the translation for output file"""
        # Extract English title (first line of translation)
        eng_lines = english_translation.strip().split('\n')
        english_title = eng_lines[0] if eng_lines else f"Episode {episode_id}"
        
        english_translation = english_translation.replace("*", "")
        print(english_translation)
        
        # Format output
        output = [
            english_translation            
        ]
        
        return '\n'.join(output)
    
    def save_translation(self, episode_id: int, formatted_translation: str):
        """Append translation to output file"""
        try:
            # Save current translated episode to self.config.EPISODES_OUTPUT_DIR/{episode_id}.txt
            episodes_dir = self.config.EPISODES_OUTPUT_DIR
            os.makedirs(episodes_dir, exist_ok=True)
            
            # 1. Save individual episode to its own file
            episode_filename = f"{episode_id}.txt"
            episode_filepath = os.path.join(episodes_dir, episode_filename)
            
            with open(episode_filepath, 'w', encoding='utf-8') as f:
                f.write(formatted_translation)
            self.logger.info(f"Saved individual translation to: {episode_filepath}")
            
            # And save full translation
            with open(self.config.OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(formatted_translation)
                print("LLM resp length:")
                print(len(formatted_translation))
            self.logger.info(f"Saved translation for episode {episode_id}")
        except Exception as e:
            self.logger.error(f"Error saving translation for episode {episode_id}: {e}")
    
    def process_episode(self, episode_id: int) -> bool:
        """Process a single episode: read text, translate, save"""
        # Check if already translated
        if episode_id in self.progress_data.get('completed_episodes', []):
            self.logger.info(f"Episode {episode_id} already translated, skipping...")
            return True
        
        # Read text
        funny_text = self.read_episode_file(episode_id)
        if not funny_text:
            self.save_progress(episode_id, success=False)
            return False
        
        # Translate text
        english_translation = self.translate_text(funny_text, episode_id)
        if not english_translation:
            self.save_progress(episode_id, success=False)
            return False
        
        # Format and save
        formatted = self.format_translation_for_output(episode_id, english_translation)
        self.save_translation(episode_id, formatted)
        
        # Update progress
        self.save_progress(episode_id, success=True)
        return True
    
    def get_episodes_to_process(self) -> list:
        """Get list of episodes to process"""
        available_episodes = []
        for episode_id in range(1, 99):  # 105 < 110 not inclusive
            funny_file_path = self.config.EPISODES_INPUT_DIR / f"{episode_id}.txt"
            
            if funny_file_path.exists():
                available_episodes.append(episode_id)
            else:
                if episode_id > 0:  # Adjust this threshold as needed
                    self.logger.warning(f"Episode file {episode_id}.txt not found")
        
        return available_episodes
        
    def run(self):
        """Main translation loop"""
        self.logger.info("=" * 60)
        self.logger.info("Novel Translation Script (from English to Russian)")
        self.logger.info(f"Model: {self.config.MODEL}")
        self.logger.info("=" * 60)
        
        # Setup
        self.setup_directories()
        last_processed = self.load_progress()
        
        # Get episodes to process
        episodes_to_process = self.get_episodes_to_process()
        
        # Filter episodes that haven't been processed
        episodes_to_process = [
            ep for ep in episodes_to_process 
            if ep > last_processed and ep not in self.progress_data.get('completed_episodes', [])
        ]
        
        if not episodes_to_process:
            self.logger.info("No new episodes to process.")
            return
        
        self.logger.info(f"Found {len(episodes_to_process)} episodes to process")
        
        # Process episodes
        successful = 0
        failed = 0
        
        for episode_id in sorted(episodes_to_process):
            self.logger.info(f"\n--- Processing Episode {episode_id} ---")
            
            success = self.process_episode(episode_id)
            
            if success:
                successful += 1
            else:
                failed += 1
            
            # Rate limiting delay (adjust based on your API limits)
            if episode_id != episodes_to_process[-1]:
                self.logger.info("Waiting "+str(self.config.RETRY_DELAY)+" seconds before next translation...")
                time.sleep(self.config.RETRY_DELAY)
        
        # Summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Processing Summary")
        self.logger.info("=" * 60)
        self.logger.info(f"Successfully processed: {successful} episodes")
        self.logger.info(f"Failed: {failed} episodes")
        
        if failed > 0:
            self.logger.info(f"Failed episodes: {self.progress_data.get('failed_episodes', [])}")
        
        self.logger.info(f"\nOutput saved to: {self.config.OUTPUT_FILE.absolute()}")
        self.logger.info(f"Progress saved to: {self.config.PROGRESS_FILE.absolute()}")

def check_requirements():
    """Check and install required packages"""
    try:
        import openai
    except ImportError:
        print("Installing required packages...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openai"])
        import openai

def main():
    """Main entry point"""
    # Check requirements
    check_requirements()
    
    # Create configuration
    config = Config()
    
    # Initialize and run translation manager
    manager = TranslationManager(config)
    manager.run()

if __name__ == "__main__":
    main()