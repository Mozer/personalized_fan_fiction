#genrate mp3's for each line using silero + qwen-tts
# for qwen put wavs into speakers/
# for comfy-vibevoice put wavs into comfyui/input/

import os
import re
import json
import time
import torch
import io
import requests
import random
import base64
import soundfile as sf
from pydub import AudioSegment
from datetime import datetime
from pathlib import Path

# --- CONFIGURATION ---

class Config:
    input_folder = "textfortts_ru_silero"
    output_folder = "mp3"
    progress_file = "progress_tts.json"
    
    # Silero Settings
    language = 'ru'
    model_id = 'v5_ru'
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    sample_rate = 48000
    put_accent = True
    put_yo = True
    put_stress_homo=True
    put_yo_homo=True
    
    # ComfyUI API Configuration
    COMFY_URL = "http://127.0.0.1:8188"
    WORKFLOW_PATH = "workflows/workflow_vibe.json" 
    
    # Qwen3-TTS API Configuration
    # use this server: https://github.com/andimarafioti/faster-qwen3-tts
    QWEN3_URL = "http://127.0.0.1:7860/generate"
    SPEAKERS_DIR = "speakers" # Folder containing the .wav reference files
    
    # Name replacements
    name_replacements = {
        "Рой Треннеман:": "Рой:",
        "Джен Барбер:": "Джен:",
        "Морисс Мосс:": "Мосс:",
        "Денхольм:": "Денхолм:",
        "Даглас:": "Дуглас:",        
        "Ричмонд Авенал:": "Рэйчел:",
        "Ричмонд:": "Рэйчел:",
        "Рейчел:": "Рэйчел:",
    }
    
    # TTS Mapping
    # Engines: silero, comfyui, qwen3_tts
    characters_tts_map = {
        "author": {"engine": "silero", "voice": "xenia", "ref_text": ""},
        "Мосс": {"engine": "qwen3_tts", "voice": "moss_2.wav", "ref_text": "Remove safety clip. I'll just put this over here with the rest. Ах, прощу прощения, системное столкновение. Джен, термодинамика вашего наряда довольно эффективна"},        
        "Рой": {"engine": "qwen3_tts", "voice": "roy_1.wav", "ref_text": "What? No, no, hold on now. I basicaly live on sugar. And I'v never had these problems before. I feel deliicate. You don't think that aunt Irma is visiting us."},     
        "Джен": {"engine": "qwen3_tts", "voice": "jen_1.wav", "ref_text": "what's wrong with you? Oh my god, you are crying. Maybe it's all the stuff that you both eat. Ok, Moss, what do you have for breakfast? I didn't even know that smarties made a cerial."},      
        "Денхолм": {"engine": "qwen3_tts", "voice": "denholm_2.wav", "ref_text": "Hello, security? Everyone on floor four is fired. And do it as a team. Remember you are a team and if you can't act as a team you are fired too. Don, get on to recruitment."},      
        "Дуглас": {"engine": "qwen3_tts", "voice": "douglas_2.wav", "ref_text": "Wonderfull, thanks, guys. I'll be working very closely with your department. And I have a feeling I'll be needing you for a lot more then deleting incremenating files. By the way where's that hootsie-tootsie hum dinging coochie mama boss of yours?"},      
        "Рэйчел": {"engine": "qwen3_tts", "voice": "rachel_1.wav", "ref_text": "I often work nights here. Perhaps that's you haven't see me. Air conditioning. Keeps these things cool. I don't know any these stuff even does. What's going on there?"},      
    }
        
        

# --- ENGINES ---

class SileroEngine:
    def __init__(self, config):
        print("Loading Silero to VRAM...")
        self.model, _ = torch.hub.load(repo_or_dir='snakers4/silero-models',
                                      model='silero_tts',
                                      language=config.language,
                                      speaker=config.model_id)
        self.model.to(config.device)
        self.config = config

    def split_text(self, text, max_chars=800):
        parts = re.split(r'(?<=[.!?])\s+|\n+', text)
        chunks = []
        current_chunk = ""
        
        for part in parts:
            if not part.strip():
                continue
            if len(current_chunk) + len(part) + 1 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = part
            else:
                if current_chunk:
                    current_chunk += " " + part
                else:
                    current_chunk = part
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    def generate(self, text, voice, output_path):
        if len(text) > 800:
            text_parts = self.split_text(text)
            print(f"   Text length {len(text)} > 800, splitting into {len(text_parts)} parts")
        else:
            text_parts = [text]

        audio_segments = []
        for idx, part in enumerate(text_parts):
            if not part.strip():
                continue
            ssml_text = f"<speak>{part}</speak>"
            audio_tensor = self.model.apply_tts(
                ssml_text=ssml_text, 
                speaker=voice, 
                sample_rate=self.config.sample_rate,
                put_accent=self.config.put_accent,
                put_yo=self.config.put_yo,
                put_stress_homo=self.config.put_stress_homo,
                put_yo_homo=self.config.put_yo_homo
            )
            buffer = io.BytesIO()
            sf.write(buffer, audio_tensor.numpy(), self.config.sample_rate, format='WAV')
            buffer.seek(0)
            segment = AudioSegment.from_wav(buffer)
            audio_segments.append(segment)

        if len(audio_segments) == 1:
            combined = audio_segments[0]
        else:
            combined = sum(audio_segments)

        combined.export(output_path, format="mp3", bitrate="192k")

class ComfyEngine:
    def __init__(self, config):
        self.config = config
        self.prompt_url = f"{config.COMFY_URL}/prompt"
        self.history_url = f"{config.COMFY_URL}/history"
        self.view_url = f"{config.COMFY_URL}/view"

    def _inject_data(self, data, text, voice):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    if "%prompt%" in value:
                        data[key] = value.replace("%prompt%", text)
                    if "me_qwen.wav" in value:
                        data[key] = value.replace("me_qwen.wav", voice)
                else:
                    self._inject_data(value, text, voice)
        elif isinstance(data, list):
            for item in data:
                self._inject_data(item, text, voice)

    def update_noise_seed(self, data, new_seed):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "noise_seed" or key == "seed":
                    data[key] = new_seed
                else:
                    self.update_noise_seed(value, new_seed)
        elif isinstance(data, list):
            for item in data:
                self.update_noise_seed(item, new_seed)
                
    def get_history_uuids(self):
        try:
            response = requests.get(self.history_url, timeout=5)
            return set(response.json().keys())
        except:
            return set()

    def generate(self, text, voice, output_path):
        with open(self.config.WORKFLOW_PATH, 'r', encoding='utf-8') as f:
            workflow = json.load(f)

        new_seed = random.randint(0, 10**5)
        self.update_noise_seed(workflow, new_seed)
        self._inject_data(workflow, text, voice)        
        
        pre_uuids = self.get_history_uuids()
        payload = {"prompt": workflow}
        resp = requests.post(self.prompt_url, json=payload, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"ComfyUI Error: {resp.text}")

        print(f"   Waiting for ComfyUI ({voice})...", end="", flush=True)
        timeout = time.time() + 120
        while time.time() < timeout:
            time.sleep(1)
            current_uuids = self.get_history_uuids()
            new_uuids = current_uuids - pre_uuids
            
            if new_uuids:
                uuid = list(new_uuids)[0]
                hist_resp = requests.get(f"{self.history_url}/{uuid}").json()
                outputs = hist_resp.get(uuid, {}).get('outputs', {})
                
                for node_id in outputs:
                    audio_list = outputs[node_id].get('audio', [])
                    if audio_list:
                        filename = audio_list[0].get('filename')
                        view_params = f"?filename={filename}&subfolder=audio&type=output"
                        audio_data = requests.get(self.view_url + view_params).content
                        
                        with open(output_path, 'wb') as f:
                            f.write(audio_data)
                        print(" Done.")
                        return True
        
        raise Exception("ComfyUI generation timed out.")

class Qwen3Engine:
    """Wrapper for Qwen3-TTS API."""
    def __init__(self, config):
        self.config = config

    def generate(self, text, voice, ref_text, output_path):
        speaker_path = os.path.join(self.config.SPEAKERS_DIR, voice)
        
        if not os.path.exists(speaker_path):
            raise FileNotFoundError(f"Speaker file not found: {speaker_path}")

        files = {
            'ref_audio': open(speaker_path, 'rb'),
        }
        data = {
            'text': text,
            'language': 'Russian',
            'xvec_only': False,
            'mode': 'voice_clone',
            'ref_text': ref_text,
        }

        print(f"   Calling Qwen3-TTS ({voice})...", end="", flush=True)
        response = requests.post(self.config.QWEN3_URL, files=files, data=data, timeout=60)
        files['ref_audio'].close()

        if response.status_code != 200:
            raise Exception(f"Qwen3 API Error: {response.text}")

        result = response.json()
        audio_bytes = base64.b64decode(result['audio_b64'])

        # Process audio: Load 24kHz WAV from bytes, resample to 48kHz, export to MP3
        audio_io = io.BytesIO(audio_bytes)
        segment = AudioSegment.from_wav(audio_io)

        # Resample to desired sample rate
        segment = segment.set_frame_rate(self.config.sample_rate)

        # --- Boost volume by +4 dB ---
        segment = segment.apply_gain(4)

        # Export with high bitrate
        segment.export(output_path, format="mp3", bitrate="192k")
        print(" Done.")

# --- CORE LOGIC ---

class ProgressManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self.load()

    def load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "last_chapter": 0,
            "fully_completed_chapters": [],
            "chapters_and_chunks": {},
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def save(self):
        self.data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def is_chunk_done(self, chapter_id, chunk_id):
        chap_str = str(chapter_id)
        if chap_str in self.data["chapters_and_chunks"]:
            return chunk_id in self.data["chapters_and_chunks"][chap_str]["completed_chunks"]
        return False

    def mark_chunk_done(self, chapter_id, chunk_id):
        chap_str = str(chapter_id)
        if chap_str not in self.data["chapters_and_chunks"]:
            self.data["chapters_and_chunks"][chap_str] = {"completed_chunks": []}
        if chunk_id not in self.data["chapters_and_chunks"][chap_str]["completed_chunks"]:
            self.data["chapters_and_chunks"][chap_str]["completed_chunks"].append(chunk_id)
        self.save()

class Processor:
    def __init__(self):
        self.cfg = Config()
        self.silero = SileroEngine(self.cfg)
        self.comfy = ComfyEngine(self.cfg)
        self.qwen3 = Qwen3Engine(self.cfg)
        self.progress = ProgressManager(self.cfg.progress_file)

    def get_engine_and_voice(self, line):
        match = re.match(r"^([^:]+):", line)
        if match:
            char_name = match.group(1).strip()
            if char_name in self.cfg.characters_tts_map:
                line = line.replace(char_name+":", "").strip()
                return self.cfg.characters_tts_map[char_name], line 
            else:
                return self.cfg.characters_tts_map["author"], line
        return self.cfg.characters_tts_map["author"], line

    def run(self):
        txt_files = sorted([f for f in os.listdir(self.cfg.input_folder) if f.endswith('.txt')], 
                           key=lambda x: int(re.findall(r'\d+', x)[0]) if re.findall(r'\d+', x) else x)

        last_chapter = self.progress.data.get("last_chapter", 0)
        start_index = 0
        if last_chapter != 0:
            last_chapter_str = str(last_chapter)
            for i, fname in enumerate(txt_files):
                if fname.replace('.txt', '') == last_chapter_str:
                    start_index = i + 1
                    break

        for filename in txt_files[start_index:]:
            chapter_id = filename.replace(".txt", "")
            input_path = os.path.join(self.cfg.input_folder, filename)
            output_chap_dir = os.path.join(self.cfg.output_folder, chapter_id)
            os.makedirs(output_chap_dir, exist_ok=True)

            if chapter_id in self.progress.data["fully_completed_chapters"]:
                continue

            print(f"\n--- Processing Chapter: {chapter_id} ---")
            
            with open(input_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]

            for chunk_id, line in enumerate(lines):
                if self.progress.is_chunk_done(chapter_id, chunk_id):
                    continue

                for old, new in self.cfg.name_replacements.items():
                    line = line.replace(old, new)

                tts_info, text_to_speak = self.get_engine_and_voice(line)
                print(f"Chunk {chunk_id}: [{tts_info['engine']}] {tts_info['voice']}")
                chunk_path = os.path.join(output_chap_dir, f"{chunk_id}.mp3")

                try:
                    if tts_info["engine"] == "silero":
                        self.silero.generate(text_to_speak, tts_info["voice"], chunk_path)
                    elif tts_info["engine"] == "comfyui":
                        self.comfy.generate(text_to_speak, tts_info["voice"], chunk_path)
                    elif tts_info["engine"] == "qwen3_tts":
                        self.qwen3.generate(text_to_speak, tts_info["voice"], tts_info["ref_text"], chunk_path)
                    
                    self.progress.mark_chunk_done(chapter_id, chunk_id)
                except Exception as e:
                    print(f"Error on Chapter {chapter_id}, Chunk {chunk_id}: {e}")
                    time.sleep(5) 
                    continue

            completed_chunks = self.progress.data["chapters_and_chunks"].get(chapter_id, {}).get("completed_chunks", [])
            if len(completed_chunks) == len(lines):
                self.progress.data["fully_completed_chapters"].append(chapter_id)
                self.progress.data["last_chapter"] = chapter_id
                self.progress.save()
                print(f"Chapter {chapter_id} fully completed.")

if __name__ == "__main__":
    app = Processor()
    app.run()