# rewrite dialogues into a story, add lewd details
# llm: Huihui-GLM-4.7-Flash-abliterated.Q5_K_M.gguf thinking: off
# llm: qwen3.5_27b thinking: off

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
    SHORT_NAME = "itlewd"    
    EPISODES_SHORTDESC_DIR = Path("summary_ru_replaced") # not used
    EPISODES_DIALOGUES_DIR = Path("itstoryrefined_split_en")
    EPISODES_LEWD_DIR = Path("episodes_Emmanuelle_eng_by_lines")
    EPISODES_TRANSLATED_DIR = Path(SHORT_NAME+"_en")    
    EPISODES_MAP = Path("chapters_split_list_3.json")    # not used
    NOVEL_BRIEF_INFO = Path("novel_brief_info.txt")
    OUTPUT_FILE = Path(SHORT_NAME+"_en.txt")
    PROGRESS_FILE = Path("progress_"+SHORT_NAME+".json")
    
    # OpenAI/LLM API Configuration
    #API_BASE_URL = "https://api.mistral.ai/v1" 
    API_BASE_URL = "http://127.0.0.1:8080/v1" 
    API_KEY = "None"  # set here for mistral or others
    MODEL = "mistral-large-latest"  # or "gpt-3.5-turbo", "claude-3-haiku", etc.
    
     # API settings
    MAX_RETRIES = 2
    RETRY_DELAY = 4  # seconds
    TIMEOUT = 900  # seconds, 15 min
    MAX_TOKENS = 16240  # max new tokens. Adjust based on model context window
    temperature = 0.6
    frequency_penalty = 1.1
    
    # Translation settings
    SYSTEM_PROMPT = """You are a professional lewd rewriter specializing in light novels."""

    USER_PROMPT_TEMPLATE = """We are creating a new novel called "Naughty IT Crowd". Transforming short plots chapter by chapter. In total there are 25 chapters with 150 short episodes.
Your tasks:
1. Take a story from dialogues_script add lots of clothes and body descriptions. add some spice from lewd_text and use the same writing style from style_reference_text_by_Nabokov. Try to use original dialogues from dialogues_script in English but modify them if needed to fit new lewd elements. 

Each time a new character enters the scene - describe it's clothes with naughty details. Add more clothes and body descriptions and make them lewd. Amplify Implied Subtext and expand vivid Descriptions, but do not invent major scenarios or alter plot-critical actions. When describing characters, outfits, or physically intimate situations you may elaborate slightly to emphasize appeal, using suggestive prose. Add character thoughts, body desciptions, lewd clothes desciptions. Find a way to create a long story, about 1500-2000 words, like a chapter of a light novel.


Brief info of the whole novel (dont rewrite it, it's just for reference here)
{novel_brief_info}
END OF Brief info

If there are no clothes descriptions in the original text - make it up on your own! We like vivid female clothes descriptions with naughty details. The series lack women - add more women (coworkers, relatives). And don't forget we changed Richmond to a goth woman Rachel.

2. Replace London places with Moscow equivalents. Location: center of Moscow, Russia. Cold weather, snow at winter. Tall skyscraper at Moscow city, IT department is in the basement. 

TEXTS of the current episode to convert:

dialogues_script:
{dialogues_script}
END OF dialogues_script.

lewd_text:
{lewd_text}
END OF lewd_text.

style_reference_text_by_Nabokov:
The front hall was graced with door chimes, a white-eyed wooden thingamabob of commercial Mexican origin, and that banal darling of the arty middle class, van Gogh’s “Arlsienne.” A door ajar to the right afforded a glimpse of a living room, with some more Mexican trash in a corner cabinet and a striped sofa along the wall. There was a staircase at the end of the hallway, and as I stood mopping my brow (only now did I realize how hot it had been out-of-doors) and staring, to stare at something, at an old gray tennis ball that lay on an oak chest, there came from the upper landing the contralto voice of her, who leaning over the banisters inquired melodiously, “Is that Monsieur?” A bit of cigarette ash dropped from there in addition. Presently, the lady herselfsandals, maroon slacks, yellow silk blouse, squarish face, in that ordercame down the steps, her index finger still tapping upon her cigarette.

Reluctantly I followed her downstairs again; then through the kitchen at the end of the hall, on the right side of the house the side where also the dining room and the parlor were (under “my” room, on the left, there was nothing but a garage). In the kitchen, the maid, a plump youngish woman, said, as she took her large glossy black purse from the knob of the door leading to the back porch: “I’ll go now, Mrs.” “Yes,” answered she with a sigh. “I’ll settle with you Friday.” We passed on to a small pantry and entered the dining room, parallel to the parlor we had already admired. I noticed a white sock on the floor. With a deprecatory grunt she stooped without stopping and threw it into a closet next to the pantry. We cursorily inspected a mahogany table with a fruit vase in the middle, containing nothing but the still glistening stone of one plum. I groped for the timetable I had in my pocket and surreptitiously fished it out to look as soon as possible for a train. I was still walking behind her though the dining room when, beyond it, there came a sudden burst of greenery ”the piazza,” sang out my leader, and then, without the least warning, a blue sea-wave swelled under my heart and, from a mat in a pool of sun, kneeling, turning about on her knees, there was she peering at me over dark glasses.
END OF style_reference_text_by_Nabokov.


Now create up with a brand new LONG chapter in English (soft cap is around 1500-2000 words, but it's not strict, may be less or more if needed). Use some naughty details described in a Brief info for characters + clothes and body desciptions. Try to use original dialogues from dialogues_script but modify them if needed to fit new lewd elements. Result must be lewd with lots of body desciptions. Copy Nabokov's writing style from style_reference_text_by_Nabokov. Use long place desciptions as in the example from Nabokov. Return the text of the chapter in English with lots of lewd details similar to ones in lewd_text. Now return just the text, without any preambles or explanations.
"""
# ALSO
# line 383 replace names: . print("names in lewd_text were replaced")


   
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
        if not config.API_KEY:
            raise ValueError("API_KEY not found. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(
            api_key=config.API_KEY,
            base_url=config.API_BASE_URL
        )
        
        self._episode_to_chapter: Optional[Dict[int, int]] = None
        
    def setup_directories(self):
        """Ensure necessary directories and files exist"""
        self.config.EPISODES_LEWD_DIR.mkdir(exist_ok=True)
        self.config.EPISODES_DIALOGUES_DIR.mkdir(exist_ok=True)
        self.config.EPISODES_TRANSLATED_DIR.mkdir(exist_ok=True)
        
        # Create output file if it doesn't exist
        if not self.config.OUTPUT_FILE.exists():
            self.config.OUTPUT_FILE.write_text(self.config.SHORT_NAME+"\n"+"=== English Translation ===\n\n", encoding='utf-8')
    
    def load_progress(self) -> int:
        """Load translation progress from JSON file"""
        if self.config.PROGRESS_FILE.exists():
            try:
                with open(self.config.PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    self.progress_data = json.load(f)
                last_episode = self.progress_data.get('last_episode', 0)
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
    
    def _load_episode_to_chapter_map(self) -> Dict[int, int]:
        """Load the JSON mapping file and return a dict episode_id -> chapter_id."""
        if self._episode_to_chapter is not None:
            return self._episode_to_chapter

        json_path = Path(self.config.EPISODES_MAP) 
        if not json_path.exists():
            self.logger.error(f"Chapters split list not found: {json_path}")
            self._episode_to_chapter = {}  # empty fallback
            return self._episode_to_chapter

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            mapping = {}
            for chapter_str, file_list in data.items():
                chapter_id = int(chapter_str)  # chapter ID as int
                for filename in file_list:
                    # filename like "1.txt" – extract episode ID
                    if filename.endswith('.txt'):
                        episode_str = filename[:-4]  # remove '.txt'
                        try:
                            episode_id = int(episode_str)
                            mapping[episode_id] = chapter_id
                        except ValueError:
                            self.logger.warning(f"Invalid episode filename (not an integer): {filename}")
                    else:
                        self.logger.warning(f"Unexpected filename format (missing .txt): {filename}")

            self._episode_to_chapter = mapping
            self.logger.info(f"Loaded chapter mapping for {len(mapping)} episodes")
            return mapping

        except Exception as e:
            self.logger.error(f"Failed to load chapters split list: {e}")
            self._episode_to_chapter = {}
            return self._episode_to_chapter

    def read_episode_files(self, episode_id: int) -> Optional[Tuple[str, str]]:
        """Read both funny (short) and lewd (subs) texts from episode files.
        
        The short file is now read from the chapter directory using the chapter ID
        obtained from chapters_split_list.json.
        The subs file is still read directly by episode ID.
        """
        # Ensure mapping is loaded
        #ep_to_ch = self._load_episode_to_chapter_map()
        #chapter_id = ep_to_ch.get(episode_id)

        #if chapter_id is None:
        #    self.logger.error(f"Episode {episode_id} not found in chapters split list")
        #    return None

        # Build file paths
        short_file_path = self.config.EPISODES_SHORTDESC_DIR / f"{episode_id}.txt"
        subs_file_path = self.config.EPISODES_DIALOGUES_DIR / f"{episode_id}.txt"
        
        # Get all .txt files in the lewd directory
        lewd_dir = self.config.EPISODES_LEWD_DIR
        if not lewd_dir.exists():
            self.logger.error(f"Lewd directory not found: {lewd_dir}")
            return None        
        lewd_files = list(lewd_dir.glob("*.txt"))
        if not lewd_files:
            self.logger.error(f"No .txt files found in lewd directory: {lewd_dir}")
            return None        
        # Select a random lewd file
        lewd_file_path = random.choice(lewd_files)        
        if not lewd_file_path.exists():
            self.logger.error(f"Lewd episode file not found: {lewd_file_path}")
            return None        
        lewd_text = ""
        
        #with open(short_file_path, 'r', encoding='utf-8') as f:
        #    short_plot_description = f.read()
        short_plot_description = ""
        
        with open(lewd_file_path, 'r', encoding='utf-8') as f:
            lewd_text = f.read()                
        print("Names in lewd_text were replaced!! Check them in code")
        lewd_text = lewd_text.replace("Emmanuelle", "Jen")

        # Check existence
        #if not short_file_path.exists():
        #    self.logger.error(f"chapter file not found: {short_file_path} (chapter {chapter_id})")
        #    return None
        if not subs_file_path.exists():
            self.logger.error(f"subs file not found: {subs_file_path}")
            return None

        try:
            #with open(short_file_path, 'r', encoding='utf-8') as f:
            #    short_plot_description = f.read()
            #    print(f"Short description {short_file_path} opened")
            short_plot_description = ""
            with open(subs_file_path, 'r', encoding='utf-8') as f:
                subs_text = f.read()
                print(f"Subs file {subs_file_path} opened")
            return short_plot_description, subs_text, lewd_text
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
    
    def prepare_translation_prompt(self, short_plot_description: str, dialogues_script: str, lewd_text: str) -> str:
        """Prepare the prompt for translation using both funny and lewd texts"""
        
        # Read novel brief info from file
        novel_brief_info = ""
        try:
            with open(self.config.NOVEL_BRIEF_INFO, 'r', encoding='utf-8') as f:
                novel_brief_info = f.read().strip()
        except FileNotFoundError:
            print(f"Warning: {self.config.NOVEL_BRIEF_INFO} not found")
            novel_brief_info = "No brief info txt file available"
            
        # Extract titles if present
        title_funny = self.extract_title_from_content(short_plot_description)
        title_lewd = self.extract_title_from_content(dialogues_script)
        
        # Format titles section if titles exist
        titles_text = ""
        if title_funny:
            titles_text += f"Funny Episode Title: {title_funny}\n"        
        
        special_tasks = ""
        
        # Format the full prompt with all placeholders
        return self.config.USER_PROMPT_TEMPLATE.format(
            titles_text=titles_text,
            special_rand_task=special_tasks,
            short_plot_description=short_plot_description,
            lewd_text=lewd_text,
            dialogues_script=dialogues_script,
            novel_brief_info=novel_brief_info
        )
    
    def translate_text(self, short_plot_description: str, subs_text: str, lewd_text: str, episode_id: int) -> Optional[str]:
        """Send text to LLM for translation with retry logic"""
        prompt = self.prepare_translation_prompt(short_plot_description, subs_text, lewd_text)
        
        print(prompt)
        #time.sleep(1)
        #return None
        
        for attempt in range(self.config.MAX_RETRIES):
            try:
                self.logger.info(f"Translating episode {episode_id} (attempt {attempt + 1}/{self.config.MAX_RETRIES})...")
                
                response = self.client.chat.completions.create(
                    model=self.config.MODEL,
                    messages=[
                        {"role": "system", "content": self.config.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    frequency_penalty=self.config.frequency_penalty,
                    max_tokens=self.config.MAX_TOKENS,
                    timeout=self.config.TIMEOUT
                )
                
                translation = response.choices[0].message.content.strip()
                
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
        
        ep_to_ch = self._load_episode_to_chapter_map()
        chapter_id = ep_to_ch.get(episode_id)
        
        # Format output
        output = [
            f"#Chapter {chapter_id}",
            f"#Episode {episode_id}",
            "\n",
            english_translation,
            "\n\n\n"
        ]
        
        return '\n'.join(output)
    
    def save_translation(self, episode_id: int, formatted_translation: str):
        """Append translation to output file"""
        try:
            # Save current translated episode to self.config.EPISODES_TRANSLATED_DIR/{episode_id}.txt
            # Create episodes directory if it doesn't exist
            episodes_dir = self.config.EPISODES_TRANSLATED_DIR
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
        """Process a single episode: read both texts, translate, save"""
        # Check if already translated
        if episode_id in self.progress_data.get('completed_episodes', []):
            self.logger.info(f"Episode {episode_id} already translated, skipping...")
            return True
        
        # Read both texts
        texts = self.read_episode_files(episode_id)
        if not texts:
            self.save_progress(episode_id, success=False)
            return False
        
        short_plot_description, subs_text, lewd_text = texts
        
        # Translate using both texts
        english_translation = self.translate_text(short_plot_description, subs_text, lewd_text, episode_id)
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
        """Get list of episodes to process (both funny and lewd files must exist)"""
        # Check which episode files exist in both directories
        available_episodes = []
        for episode_id in range(1, 99):  # 105 < 110 not inclusive
            #short_file_path = self.config.EPISODES_LEWD_DIR / f"{episode_id}.txt"
            subs_file_path = self.config.EPISODES_DIALOGUES_DIR / f"{episode_id}.txt"
            
            if subs_file_path.exists():
                available_episodes.append(episode_id)
            else:
                self.logger.warning(f"Episode files {episode_id}.txt not found in directory")
        
        return available_episodes
        
    def run(self):
        """Main translation loop"""
        self.logger.info("=" * 60)
        self.logger.info("Novel Generation Script (from funny + lewd texts)")
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
        
        # Estimate cost (very rough estimate)
        if successful > 0:
            # Assuming ~2000 tokens per episode
            estimated_tokens = successful * 2000
            self.logger.info(f"Estimated tokens used: ~{estimated_tokens:,}")

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
    
    # Check for API key
    if 0 and not os.environ.get("OPENAI_API_KEY"):
        print("\n" + "=" * 60)
        print("WARNING: OPENAI_API_KEY environment variable not set!")
        print("You can:")
        print("1. Set it in your terminal: export OPENAI_API_KEY='your-key'")
        print("2. Edit the script to add your key directly (not recommended)")
        print("3. For local models: Change API_BASE_URL to local endpoint")
        print("=" * 60)
        
        # Ask for key
        key = input("Enter API key (or press Enter to continue without): ").strip()
        if key:
            os.environ["OPENAI_API_KEY"] = key
            print("API key set for this session.")
        else:
            print("Continuing without API key. Script will fail if API is needed.")

def main():
    """Main entry point"""
    # Check requirements
    check_requirements()
    
    # Create configuration
    config = Config()
    
    # For local models, update these settings:
    # config.API_BASE_URL = "http://localhost:11434/v1"  # For Ollama
    # config.MODEL = "llama2"  # or "mistral", "mixtral", etc.
    # config.API_KEY = "not-needed-for-local"  # Can be any string for local
    
    #try:
    # Initialize and run translation manager
    manager = TranslationManager(config)
    manager.run()
        
    #except Exception as e:
    #    print(f"\nError: {e}")
    #    print("\nTroubleshooting tips:")
    #    print("1. Check your API key is valid")
    #    print("2. Verify the API endpoint is correct")
    #    print("3. Check internet connection")
    #    print("4. Ensure episode files exist in 'episodes/' folder")
    #    logging.error(f"Script failed: {e}")

if __name__ == "__main__":
    main()