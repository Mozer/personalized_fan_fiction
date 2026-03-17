import requests
import time
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

def create_descriptions_directory():
    """Create the directory for saving descriptions if it doesn't exist"""
    if not os.path.exists('short_descriptions'):
        os.makedirs('short_descriptions')
        print("Created /short_descriptions directory")

def extract_page_title_from_url(url):
    """Extract the page title from a Fandom wiki URL"""
    parsed = urlparse(url)
    path = parsed.path
    # Get the last part of the path after the last slash
    page_title = path.split('/')[-1]
    # URL decode the title (replace %20 with spaces, etc.)
    page_title = unquote(page_title)
    return page_title

def get_wiki_page_content(wiki_base, page_title):
    """Get page content using Fandom's API"""
    api_url = f"https://{wiki_base}.fandom.com/api.php"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; EpisodeScraper/1.0; +https://example.com)'
    }
    
    params = {
        'action': 'parse',
        'page': page_title,
        'format': 'json',
        'prop': 'text|displaytitle',
        'redirects': 1
    }
    
    response = requests.get(api_url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    if 'error' in data:
        raise Exception(f"API error: {data['error']['info']}")
    
    return data['parse']

def extract_section_content(soup, heading):
    """
    Extract all content after a heading until the next heading
    """
    content_parts = []
    current_element = heading.find_next_sibling()
    
    while current_element and current_element.name not in ['h2', 'h3']:
        if current_element.name == 'p':
            text = current_element.get_text().strip()
            if text:
                content_parts.append(text)
        elif current_element.name == 'ul':  # For trivia lists
            list_items = []
            for li in current_element.find_all('li', recursive=False):
                item_text = li.get_text().strip()
                if item_text:
                    list_items.append(f"• {item_text}")
            if list_items:
                content_parts.append('\n'.join(list_items))
        current_element = current_element.find_next_sibling()
    
    return '\n\n'.join(content_parts)

def extract_episode_description(html_content, page_title):
    """
    Extract Synopsis, Plot, and Trivia sections from the episode page
    and combine them (Synopsis first, then Plot, then Trivia)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get the main content
    content_div = soup.find('div', class_='mw-parser-output')
    if not content_div:
        return "", page_title
    
    # Store the actual title from the page if available
    title_elem = soup.find('h1', class_='page-header__title')
    if title_elem:
        page_title = title_elem.get_text().strip()
    
    # Find all headings and map them to their content
    sections = {}
    
    for heading in content_div.find_all(['h2', 'h3']):
        heading_text = heading.get_text().strip().lower()
        
        # Check for Synopsis (various possible titles)
        if any(term in heading_text for term in ['brief overview', 'overview', 'synopsis',  'summary']):
            content = extract_section_content(soup, heading)
            if content:
                sections['synopsis'] = content
        
        # Check for Plot (various possible titles)
        elif any(term in heading_text for term in ['plot', 'plot synopsis']):
            # Avoid duplicate if it already matched synopsis
            if heading_text not in ['brief overview', 'overview', 'synopsis']:
                content = extract_section_content(soup, heading)
                if content:
                    sections['plot'] = content
        
        # Check for Trivia
        elif any(term in heading_text for term in ['trivia', 'notes', 'behind the scenes']):
            content = extract_section_content(soup, heading)
            if content:
                sections['trivia'] = content
    
    # Combine sections: Synopsis first, then Plot, then Trivia
    combined_description = []
    
    if 'synopsis' in sections:
        combined_description.append("SYNOPSIS:\n" + sections['synopsis'])
    
    if 'plot' in sections:
        if combined_description:  # Add spacing if we already have synopsis
            combined_description.append("\n" + "="*40 + "\n")
        combined_description.append("PLOT:\n" + sections['plot'])
    
    if 'trivia' in sections:
        if combined_description:  # Add spacing if we already have previous sections
            combined_description.append("\n" + "="*40 + "\n")
        combined_description.append("TRIVIA:\n" + sections['trivia'])
    
    # If we found any sections, return them combined
    if combined_description:
        return '\n'.join(combined_description), page_title
    
    # Fallback: if no specific sections found, try to get any paragraphs
    paragraphs = []
    for p in content_div.find_all('p')[:5]:  # First 5 paragraphs as fallback
        text = p.get_text().strip()
        if text and len(text) > 50:  # Only substantial paragraphs
            paragraphs.append(text)
    
    if paragraphs:
        return "FALLBACK CONTENT:\n" + '\n\n'.join(paragraphs), page_title
    
    return "", page_title

def save_episode(episode_num, url, title, description):
    """Save episode description to file"""
    filename = f"short_descriptions/{episode_num}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# Episode {episode_num}\n")
        f.write(f"## {title}\n\n")
        f.write(description)
    
    # Print a preview
    preview = description[:200].replace('\n', ' ') + "..." if len(description) > 200 else description
    print(f"  Preview: {preview}")

def main():
    """Main function to scrape all episodes"""
    create_descriptions_directory()
    
    # List of episode URLs
    episode_urls = [
        "https://theitcrowd.fandom.com/wiki/Yesterday%27s_Jam",
        "https://theitcrowd.fandom.com/wiki/Calamity_Jen",
        "https://theitcrowd.fandom.com/wiki/Fifty-Fifty",
        "https://theitcrowd.fandom.com/wiki/The_Red_Door",
        "https://theitcrowd.fandom.com/wiki/The_Haunting_of_Bill_Crouse",
        "https://theitcrowd.fandom.com/wiki/Aunt_Irma_Visits",
        "https://theitcrowd.fandom.com/wiki/The_Work_Outing",
        "https://theitcrowd.fandom.com/wiki/Return_of_the_Golden_Child",
        "https://theitcrowd.fandom.com/wiki/Moss_and_the_German",
        "https://theitcrowd.fandom.com/wiki/The_Dinner_Party",
        "https://theitcrowd.fandom.com/wiki/Smoke_and_Mirrors",
        "https://theitcrowd.fandom.com/wiki/Men_Without_Women",
        "https://theitcrowd.fandom.com/wiki/From_Hell",
        "https://theitcrowd.fandom.com/wiki/Are_We_Not_Men%3F",
        "https://theitcrowd.fandom.com/wiki/Tramps_Like_Us",
        "https://theitcrowd.fandom.com/wiki/The_Speech",
        "https://theitcrowd.fandom.com/wiki/Friendface",
        "https://theitcrowd.fandom.com/wiki/Calendar_Geeks",
        "https://theitcrowd.fandom.com/wiki/Jen_the_Fredo",
        "https://theitcrowd.fandom.com/wiki/The_Final_Countdown",
        "https://theitcrowd.fandom.com/wiki/Something_Happened",
        "https://theitcrowd.fandom.com/wiki/Italian_for_Beginners",
        "https://theitcrowd.fandom.com/wiki/Bad_Boys",
        "https://theitcrowd.fandom.com/wiki/Reynholm_v_Reynholm",
        "https://theitcrowd.fandom.com/wiki/The_Internet_Is_Coming"
    ]
    
    wiki_base = "theitcrowd"  # The wiki subdomain
    
    print("Starting episode scraper for The IT Crowd...")
    print("=" * 60)
    
    successful = 0
    failed = 0
    
    for episode_num, url in enumerate(episode_urls, 1):
        page_title = extract_page_title_from_url(url)
        
        print(f"\n📺 Processing Episode {episode_num}: {page_title}...")
        
        try:
            # Get content via API
            page_data = get_wiki_page_content(wiki_base, page_title)
            
            # Extract description from HTML (now returns both description and title)
            description, actual_title = extract_episode_description(page_data['text']['*'], page_title)
            
            if description and len(description.strip()) > 0:
                save_episode(episode_num, url, actual_title, description)
                print(f"  ✅ Episode {episode_num} saved successfully")
                successful += 1
            else:
                print(f"  ⚠️ No description found for Episode {episode_num}")
                # Save file with just the title and URL
                with open(f"short_descriptions/{episode_num}.txt", 'w', encoding='utf-8') as f:
                    f.write(f"# Episode {episode_num}\n")
                    f.write(f"## {actual_title}\n\n")
                    f.write(f"URL: {url}\n\n")
                    f.write("No content found on the wiki page.")
                failed += 1
            
            print(f"  💤 Sleeping 2 seconds...")
            time.sleep(2)  # Reduced sleep time to 2 seconds
                
        except Exception as e:
            print(f"  ❌ Error on Episode {episode_num}: {e}")
            # Save error info with title
            with open(f"short_descriptions/{episode_num}.txt", 'w', encoding='utf-8') as f:
                f.write(f"# Episode {episode_num}\n")
                f.write(f"## {page_title}\n\n")
                f.write(f"URL: {url}\n\n")
                f.write(f"ERROR: Failed to download - {str(e)}")
            failed += 1
            time.sleep(5)
    
    print("\n" + "=" * 60)
    print(f"✅ Scraping complete!")
    print(f"📊 Summary: {successful} successful, {failed} failed")
    print(f"📁 Files saved in /short_descriptions directory")

if __name__ == "__main__":
    main()