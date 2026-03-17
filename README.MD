# Personal Content Creator: Fanfiction, Audiobooks, and Visual Novels

Creating personalized content: fanfics, audiobooks, and visual novels.

**Demo video (in Russian): ** https://disk.yandex.ru/i/BKndy2R19qDEMw or https://t.me/tensorbanana/1287

> **Disclaimer:** The example in the video is not the final result. The final product is defined by the personalization you require (replacement of characters, locations, habits, fetishes, voices, and images). Reading or watching someone else's fanfiction is usually uninteresting as they often feel flat. Personal content, however, is a different story—it is the future.

I have already created about 10 adaptations based on sitcoms, anime, and books. 20–40 chapters is the "sweet spot" before it gets repetitive. So far, only two titles have reached the video stage because of the high density of action. I don't recommend using movies or books with serious, complex plots yet; you'll encounter too many plot inconsistencies, which can be frustrating. Sitcoms and anime are perfect. Manga is also an option, but maintaining consistency is difficult. The key "hook" is adding your own personalized details and preferences.

---

## Technical Stack

### TEXT
* **Input:** Subtitles, plot summaries.
* **Personalization:** Character replacement (names, descriptions, habits, gender).
* **Customization:** Adding specific tropes/fetishes to the plot.
* **Output:** A full-fledged light novel chapter or fanfic.
* **LLMs:** `qwen3.5-27b`, `qwen3.5-35b`, `GLM-4.7-Flash-abliterated`, `gemma3-27b`.

### AUDIOBOOK
* **Voices:** Original voices + user-cloned voices.
* **TTS:** `silero-tts-v5`, `qwen3-tts`, `vibevoice` (not recommended).
* **Qwen3 TTS API Server:** [faster-qwen3-tts](https://github.com/andimarafioti/faster-qwen3-tts)

### VISUAL NOVEL
* **Input:** Backgrounds, main character assets.
* **Model:** `klein-9b` in image-to-image/editing mode.
* **KV-FP8:** [FLUX.2-klein-9b-kv-fp8](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-kv-fp8)

---

## Known Issues & Workarounds

### LLM Limitations
1.  **Chapter Length:** LLMs struggle with long chapters. They are trained for short responses (1k–2k tokens). Beyond that, they loop or hallucinate. 
    * *Solution:* Split chapters into parts, then merge and prompt the AI to fix inconsistencies.
2.  **Language Quality:** Russian output is often more formulaic than English. 
    * *Solution:* Generate in English (even if the source material is Russian) and then translate using `gemma3-27b` or `translategemma-27b`.
3.  **Multitasking:** Accuracy drops when generating complex JSONs from long text. 
    * *Solution:* Break text into chunks and divide the task into sub-tasks.
4.  **Censorship:** Uncensored (abliterated) models are often worse at structured tasks like JSON or image prompting. Original models may refuse 18+ content. 
    * *Solution:* Use a "pipeline" approach—juggle different models for specific tasks.
5.  **Reasoning Mode:** Reasoning models perform poorly with long texts (50–100 lines), often leading to loops or extreme summarization. 
    * *Solution:* Disable reasoning for the majority of these tasks.
6.  **Manga Conversion:** I haven't mastered manga-to-prose conversion yet; plot consistency between pages remains an issue.

### TTS Issues
1.  **Silero-v5 (Xenia):** Great speed, but struggles with stress marks (accents). There is no perfect homograph solution yet. Only top-tier models like `gemini-3-pro` handle stress marks perfectly.
2.  **Qwen3-TTS:** Voice cloning is inconsistent. Sometimes it's spot on, sometimes it's unrecognizable. However, `faster-qwen3` runs at 3x real-time speed, which is a major plus.
3.  **VibeVoice:** Too much hallucination and background noise. I've stopped using it.

### Klein (Image Generation) Issues
1.  **Likeness:** If you input backgrounds and characters separately, likeness drops significantly. 
    * *Solution:* Use a "pre-frame" (digitally paste characters onto the background first) as the input. It improves likeness but slightly hurts background integration.
2.  **Extra Limbs:** More characters = more extra hands. 
    * *Solution:* Limit characters to 2–3 per frame and use the `res_2s` sampler (slower but more accurate).

---

## Workflow Pipelines

### Text Generation Stages
00. Download and rename English `.srt` files.
01. Fetch the episode summary from a Fandom wiki (in English).
02. Split `.srt` files into 100-line segments.
03. Convert `.srt` segments + summary into dialogues (`qwen3.5-27b`).
04. Merge dialogues back into a full episode.
05. Create a 17–20 sentence episode summary (`qwen3.5-35b`).
06. (Optional) Replace character names.
07. Transform dialogues + summary into a full story (`qwen_27b` or `qwen_35b`).
08. Rewrite to eliminate plot/dialogue inconsistencies (`qwen_27b`).
09. Split the story into two halves.
10. (Optional) Take a reference 18+ novel and split it into 40-line chunks for style guidance.
11. Prompt the LLM to add clothing descriptions (`qwen27`, `glm-flash-abli`).
12. Split the text in half again.
13. Add specific details/fetishes from a randomized list.
14. Translate the final text into Russian (`gemma3-27b`, `translate-gemma`).
---
Enjoy your personalized AI-slop fan fiction.


### Optional: Illustration per each Chapter
15. Convert chapter text into an image2image prompt (`qwen_27b` or `qwen_35b`).
16. Generate illustration using prompt + character references (`Klein-9b`).
17. Compile text and images into an `.fb2` file.
---
Enjoy your personalized AI-slop book with illustrations.


### Audiobook Generation Stages
30. Convert chapter text into "Direct Speech + Author Narration" format.
31. Translate the formatted speech into Russian.
32. Number the lines in the English text (Optional).
35. Perform word replacement for Silero compatibility.
36. Line-by-line TTS conversion to `.mp3` (`silero` + `qwen3-tts`).
---
Enjoy your personalized AI-slop audio book.


### Visual Novel / "Anime" Conversion (Using numbered lines from step 32)
37. Describe character actions for every line (`qwen_27b`).
38. Create a list of locations for the chapter (`qwen_27b`).
39. Assign locations and characters to every line (`qwen_27b`).
40. Describe clothing changes throughout the chapter (`qwen_27b`).
41. Identify line numbers containing direct speech.
42. Merge all data (locations, characters, actions, clothes, speech) into a single JSON.
43. Clean/format the JSON.
44. Input base character image + clothing prompt => Character on transparent background (`klein-9b`).
45. Create "Pre-frames" (paste 1-3 characters onto the location background).
46. Input Pre-frames + prompts => Final rendered frames (`klein-9b`).
50. Encode frames + line-by-line audio into a single `.mp4`.
---
Enjoy your personalized AI-slop animation.
