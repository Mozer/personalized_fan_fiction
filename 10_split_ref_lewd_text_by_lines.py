# split ref lewd text by lines (40). don't use large amount of lines, they can be copied into main story

import os
import codecs

def split_into_episodes(input_file, output_dir, lines_per_episode):
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Read input file with Windows-1251 encoding
    #with codecs.open(input_file, 'r', encoding='windows-1251') as f:
    with codecs.open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    total_lines = len(lines)
    episode_number = 1
    
    # Split into episodes of 50 lines each
    for i in range(0, total_lines, lines_per_episode):
        episode_lines = lines[i:i + lines_per_episode]
        
        # Define output filename
        output_file = os.path.join(output_dir, f"{episode_number}.txt")
        
        # Write episode to file with UTF-8 encoding
        with codecs.open(output_file, 'w', encoding='utf-8') as out_f:
            out_f.writelines(episode_lines)
        
        print(f"Created episode {episode_number} with {len(episode_lines)} lines")
        episode_number += 1
    
    print(f"\nSuccessfully created {episode_number - 1} episodes in '{output_dir}/'")

if __name__ == "__main__":
    # Configuration
    input_filename = "Emmanuelle_II_-_Emmanuelle_Arsan.txt"
    output_directory = "episodes_Emmanuelle_eng_by_lines"
    
    # Run the splitting
    split_into_episodes(input_filename, output_directory, lines_per_episode=40)