import os
import json
from pathlib import Path
from datetime import datetime
import subprocess
from PIL import Image
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

class Config:
    FRAMES_DIR = Path("images/frames")
    TTS_DIR = Path("mp3")
    OUTPUT_DIR = Path("mp4")
    PROGRESS_FILE = Path("progress_mp4.json")
    
    TARGET_WIDTH = 1488
    TARGET_HEIGHT = 832
    TARGET_SAMPLE_RATE = 48000  
    EXPORT_AUDIO_BITRATE = "96k" 
    FPS = 24 # Standard fps for the final mp4 wrapper

class ProgressManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self.load()

    def load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "completed_episodes": [],
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def save(self):
        self.data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def is_episode_done(self, episode_id):
        return str(episode_id) in self.data["completed_episodes"]

    def mark_episode_done(self, episode_id):
        ep_str = str(episode_id)
        if ep_str not in self.data["completed_episodes"]:
            self.data["completed_episodes"].append(ep_str)
        self.save()

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_sorted_numeric_dirs(root_dir):
    """Returns a list of directory names sorted as integers."""
    if not os.path.exists(root_dir):
        return []
    
    dirs = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
    
    def sort_key(d):
        try:
            return int(d)
        except ValueError:
            return float('inf')
            
    return sorted(dirs, key=sort_key)

def get_sorted_numeric_frames(episode_dir):
    """Returns a list of .jpg files sorted by integer name."""
    files = [f for f in os.listdir(episode_dir) if f.lower().endswith('.jpg')]
    
    def sort_key(f):
        try:
            return int(Path(f).stem)
        except ValueError:
            return float('inf')
            
    return sorted(files, key=sort_key)

def validate_image(image_path, cfg):
    """Check if the image matches the target resolution."""
    with Image.open(image_path) as img:
        if img.size != (cfg.TARGET_WIDTH, cfg.TARGET_HEIGHT):
            raise ValueError(f"Resolution mismatch in {image_path}: {img.size} != {(cfg.TARGET_WIDTH, cfg.TARGET_HEIGHT)}")

def create_video_from_images(episode_frames_dir, episode_audio_dir, output_video_path, fps, target_sr):
    frames = get_sorted_numeric_frames(episode_frames_dir)
    if not frames:
        return None

    list_path = episode_frames_dir / "image_list.txt"
    with open(list_path, "w") as f:
        for frame_name in frames:
            frame_id = Path(frame_name).stem
            jpg_path = episode_frames_dir / frame_name
            mp3_path = episode_audio_dir / f"{frame_id}.mp3"

            # Determine duration
            if mp3_path.exists():
                dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)]                
                duration = subprocess.check_output(dur_cmd, text=True).strip()
            else:
                duration = "2.0"
                print(f"  Warning: No audio for {frame_id}, using 2s.")

            # Write only the filename (jpg_path.name) – the list file is in the same folder
            f.write(f"file '{jpg_path.name}'\n")
            f.write(f"duration {duration}\n")
        
        # Duplicate the last frame with 0.5s duration (otherwise ffmpeg trims last frame to 5s)
        if frames:  # Make sure there's at least one frame
            last_frame_name = frames[-1]
            last_frame_id = Path(last_frame_name).stem
            last_jpg_path = episode_frames_dir / last_frame_name
            
            f.write(f"file '{last_jpg_path.name}'\n")
            f.write(f"duration 0.5\n")

    # Use hardware encoding if available
    cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_path),
        '-r', '24',
        "-pix_fmt", "yuv420p",
        "-c:v", "h264_nvenc",
        "-preset", "p4",                  
        "-b:v", "5M",
        "-y", str(output_video_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    #list_path.unlink()
    return output_video_path

def mux_video_audio(video_path, audio_path, final_output_path):
    cmd = [
        "ffmpeg", "-i", str(video_path), "-i", str(audio_path),
        "-c:v", "copy",          # video already encoded
        "-c:a", "copy",           # copy audio as‑is (AAC from combine_audio)
        "-shortest",
        "-y", str(final_output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
def combine_audio(episode_audio_dir, output_audio_path, target_sr=48000, bitrate="96k"):
    """Combine all MP3 files into one AAC audio file at given bitrate."""
    audio_files = sorted(episode_audio_dir.glob("*.mp3"), key=lambda p: int(p.stem))
    if not audio_files:
        return None

    list_path = episode_audio_dir / "concat_list.txt"
    with open(list_path, "w") as f:
        for af in audio_files:
            f.write(f"file '{af.name}'\n")

    cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-af", f"aresample={target_sr}",
        "-c:a", "aac", "-b:a", bitrate,      # encode once at desired bitrate
        "-y", str(output_audio_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    #list_path.unlink()
    return output_audio_path
    
def process_episode(episode_id, cfg, progress):
    if progress.is_episode_done(episode_id):
        print(f"Episode {episode_id} already completed. Skipping.")
        return

    print(f"Processing Episode {episode_id}...")
    
    episode_frames_dir = cfg.FRAMES_DIR / str(episode_id)
    episode_audio_dir = cfg.TTS_DIR / str(episode_id)
    
    # Optional: validate images as before
    frames = get_sorted_numeric_frames(episode_frames_dir)
    if not frames:
        print(f"  No frames found in {episode_frames_dir}. Skipping.")
        return
    for frame_name in frames:
        validate_image(episode_frames_dir / frame_name, cfg)

    # Temporary files
    combined_audio = cfg.OUTPUT_DIR / f"{episode_id}_audio.m4a"
    temp_video = cfg.OUTPUT_DIR / f"{episode_id}_temp.mp4"
    final_output = cfg.OUTPUT_DIR / f"{episode_id}.mp4"

    print("  Combining audio...")
    combine_audio(episode_audio_dir, combined_audio, cfg.TARGET_SAMPLE_RATE)

    print("  Creating video from images...")
    create_video_from_images(episode_frames_dir, episode_audio_dir, temp_video, cfg.FPS, cfg.TARGET_SAMPLE_RATE)

    print("  Muxing video and audio...")
    mux_video_audio(temp_video, combined_audio, final_output)

    # Cleanup
    combined_audio.unlink(missing_ok=True)
    temp_video.unlink(missing_ok=True)

    progress.mark_episode_done(episode_id)
    print(f"Episode {episode_id} completed successfully!\n")
    

def main():
    cfg = Config()
    ensure_dir(cfg.OUTPUT_DIR)
    
    progress = ProgressManager(cfg.PROGRESS_FILE)
    
    episode_dirs = get_sorted_numeric_dirs(cfg.FRAMES_DIR)
    if not episode_dirs:
        print(f"No episode directories found in {cfg.FRAMES_DIR}. Exiting.")
        return
        
    for episode_id in episode_dirs:
        try:
            process_episode(episode_id, cfg, progress)
        except Exception as e:
            print(f"Failed to process Episode {episode_id}: {str(e)}")
            # Optionally break or continue based on whether you want to stop the whole script on one failure
            break

    print("All episodes processed!")

if __name__ == "__main__":
    main()