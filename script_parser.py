import fitz  # PyMuPDF
import re
import json
from datetime import datetime
import os


def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    # Remove non-breaking space
    return text.replace('\u00a0', ' ')


def extract_episode_metadata(text, pdf_path):
    """Extract detailed episode information and metadata"""
    lines = text.splitlines()
    metadata = {
        "episode_title": None,
        "season": None,
        "episode_number": None,
        "series_episode_number": None,
        "air_date": None,
        "writers": [],
        "directors": [],
        "story_by": [],
        "teleplay_by": [],
        "production_code": None,
        "total_pages": None,
        "file_info": {
            "filename": os.path.basename(pdf_path),
            "file_path": pdf_path,
            "file_size": None,
            "extraction_date": datetime.now().isoformat()
        }
    }
    
    # Get file size
    try:
        metadata["file_info"]["file_size"] = os.path.getsize(pdf_path)
    except:
        pass
    
    # Extract episode title - look for the full title which might span multiple lines
    for i, line in enumerate(lines[:50]):
        clean_line = line.strip()
        if clean_line.lower().startswith("the one"):
            # Check if this is a complete title or if we need to combine with next lines
            title = clean_line
            
            # If the line ends with "(" or seems incomplete, check next lines
            if (title.endswith("(") or title.count("(") > title.count(")")) and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Combine lines if the next line seems to be continuation
                if next_line and not next_line.startswith("[") and not next_line.startswith("Written"):
                    title = title + " " + next_line
                    
                    # Check one more line if still unbalanced parentheses
                    if title.count("(") > title.count(")") and i + 2 < len(lines):
                        third_line = lines[i + 2].strip()
                        if third_line and not third_line.startswith("[") and not third_line.startswith("Written"):
                            title = title + " " + third_line
            
            metadata["episode_title"] = title
            break
    
    # Extract season and episode info from filename or content
    filename = os.path.basename(pdf_path)
    
    # Try to extract from filename patterns like "S1_Scripts/Friends_Ep1.pdf"
    season_match = re.search(r'[Ss](\d+)', filename)
    episode_match = re.search(r'[Ee]p?(\d+)', filename)
    
    if season_match:
        metadata["season"] = int(season_match.group(1))
    if episode_match:
        metadata["episode_number"] = int(episode_match.group(1))
    
    # Calculate series episode number (Friends has specific episode counts per season)
    if metadata["season"] and metadata["episode_number"]:
        # Friends episode counts: S1=24, S2=24, S3=25, S4=24, S5=24, S6=25, S7=24, S8=24, S9=24, S10=18
        season_episodes = [0, 24, 24, 25, 24, 24, 25, 24, 24, 24, 18]
        if metadata["season"] <= len(season_episodes) - 1:
            series_num = sum(season_episodes[1:metadata["season"]]) + metadata["episode_number"]
            metadata["series_episode_number"] = series_num
    
    # Search for writing/directing credits in the text (only first 10 lines to avoid dialogue)
    first_lines = lines[:10]  # Only search the very beginning
    
    # Look for writer credits - Friends scripts have unique formatting
    writer_patterns = [
        r'Written by:?\s*(.+?)(?:\n|Transcribed|$)',
        r'Writer:?\s*(.+?)(?:\n|Transcribed|$)',
        r'Teleplay by:?\s*(.+?)(?:\n|Transcribed|$)',
        r'Story by:?\s*(.+?)(?:\n|Transcribed|$)'
    ]
    
    # Standard patterns first
    for pattern in writer_patterns:
        for line in first_lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                writer_text = match.group(1).strip()
                writers = [w.strip() for w in writer_text.split('&') if w.strip()]
                
                if 'teleplay' in pattern.lower():
                    metadata["teleplay_by"].extend(writers)
                elif 'story' in pattern.lower():
                    metadata["story_by"].extend(writers)
                else:
                    metadata["writers"].extend(writers)
    
    # Friends-specific pattern: Look for "Name Name Transcribed by:" at the very start
    if not metadata["writers"]:  # Only if we haven't found writers yet
        for i, line in enumerate(first_lines):
            line = line.strip()
            # Must be at the very beginning (first few lines) and followed by "Transcribed by:"
            if i < 3 and re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s*&\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)*)\s+Transcribed by:', line):
                match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s*&\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)*)\s+Transcribed by:', line)
                if match:
                    writer_text = match.group(1).strip()
                    writers = [w.strip() for w in writer_text.split('&') if w.strip()]
                    metadata["writers"].extend(writers)
                    break
    
    # Look for director credits (also only in first 10 lines)
    director_patterns = [
        r'Directed by:?\s*(.+?)(?:\n|$)',
        r'Director:?\s*(.+?)(?:\n|$)'
    ]
    
    for pattern in director_patterns:
        for line in first_lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                director_text = match.group(1).strip()
                directors = [d.strip() for d in director_text.split('&') if d.strip()]
                metadata["directors"].extend(directors)
    
    # Look for production code (search in first 10 lines)
    for line in first_lines:
        prod_code_match = re.search(r'Production Code:?\s*([A-Z0-9\-]+)', line, re.IGNORECASE)
        if prod_code_match:
            metadata["production_code"] = prod_code_match.group(1)
            break
    
    # Count total pages
    page_numbers = set()
    for line in lines:
        page_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', line)
        if page_match:
            page_numbers.add(page_match.group(1))
    
    if page_numbers:
        # Get the highest page number
        max_page = max([int(p.split('/')[0]) for p in page_numbers])
        metadata["total_pages"] = max_page
    
    return metadata


def extract_episode_title(text):
    lines = text.splitlines()
    for line in lines[:50]:
        clean_line = line.strip()
        if clean_line.lower().startswith("the one"):
            return clean_line
    return None


def calculate_script_statistics(script_data):
    """Calculate detailed statistics about the script"""
    stats = {
        "total_scenes": len(script_data),
        "total_dialogue_lines": 0,
        "character_stats": {},
        "scene_lengths": [],
        "average_scene_length": 0,
        "longest_scene": None,
        "shortest_scene": None,
        "page_range": None,
        "unique_characters": set(),
        "speaking_characters": set()
    }
    
    all_pages = set()
    
    for scene in script_data:
        scene_length = len(scene["dialogue"])
        stats["scene_lengths"].append(scene_length)
        stats["total_dialogue_lines"] += scene_length
        
        # Track pages
        if scene.get("page_numbers"):
            all_pages.update(scene["page_numbers"])
        
        # Track characters
        for char in scene["characters"]:
            stats["unique_characters"].add(char)
            if char not in stats["character_stats"]:
                stats["character_stats"][char] = {
                    "total_lines": 0,
                    "scenes_appeared": 0,
                    "average_lines_per_scene": 0
                }
            stats["character_stats"][char]["scenes_appeared"] += 1
        
        # Count lines per character in this scene
        for dialogue in scene["dialogue"]:
            speaker = dialogue["speaker"]
            stats["speaking_characters"].add(speaker)
            if speaker in stats["character_stats"]:
                stats["character_stats"][speaker]["total_lines"] += 1
    
    # Calculate averages and extremes
    if stats["scene_lengths"]:
        stats["average_scene_length"] = sum(stats["scene_lengths"]) / len(stats["scene_lengths"])
        
        max_length = max(stats["scene_lengths"])
        min_length = min(stats["scene_lengths"])
        
        stats["longest_scene"] = {
            "length": max_length,
            "scene_index": stats["scene_lengths"].index(max_length)
        }
        stats["shortest_scene"] = {
            "length": min_length,
            "scene_index": stats["scene_lengths"].index(min_length)
        }
    
    # Calculate character averages
    for char, char_stats in stats["character_stats"].items():
        if char_stats["scenes_appeared"] > 0:
            char_stats["average_lines_per_scene"] = char_stats["total_lines"] / char_stats["scenes_appeared"]
    
    # Page range
    if all_pages:
        page_nums = [int(p.split('/')[0]) for p in all_pages]
        stats["page_range"] = {"start": min(page_nums), "end": max(page_nums)}
    
    # Convert sets to lists for JSON serialization
    stats["unique_characters"] = list(stats["unique_characters"])
    stats["speaking_characters"] = list(stats["speaking_characters"])
    
    return stats


def clean_line_and_extract_page(text, episode_title=None):
    original = text.strip()

    # Match and extract trailing page number
    match = re.search(r'(.*?)\b(\d{1,2}/\d{1,2})\b\s*$', original)
    if match:
        raw_before = match.group(1).strip()
        page_number = match.group(2).strip()
    else:
        raw_before = original
        page_number = None

    # Remove episode title if it's at the end of the line
    if episode_title:
        raw_before = re.sub(
            rf'\s*{re.escape(episode_title)}\s*$', '', raw_before, flags=re.IGNORECASE
        )

    # Remove trailing URLs
    raw_before = re.sub(r'https?://\S+', '', raw_before).strip()

    return raw_before, page_number


def clean_episode_title_from_dialogue(script_data, episode_title):
    """
    Remove episode title from dialogue lines where it appears accidentally
    """
    if not episode_title:
        return script_data, 0
    
    # Create a regex pattern that matches the episode title (case insensitive)
    # Also handle slight variations in spacing and punctuation
    title_pattern = re.escape(episode_title)
    # Make spaces flexible and handle common variations
    title_pattern = title_pattern.replace(r'\ ', r'\s+')
    title_pattern = rf'\s*{title_pattern}\s*'
    
    cleaned_count = 0
    
    for scene in script_data:
        for dialogue_entry in scene["dialogue"]:
            original_line = dialogue_entry["line"]
            
            # Remove the episode title if found
            cleaned_line = re.sub(title_pattern, '', original_line, flags=re.IGNORECASE)
            
            # Clean up any extra whitespace
            cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()
            
            # Only update if something was actually removed
            if cleaned_line != original_line:
                dialogue_entry["line"] = cleaned_line
                cleaned_count += 1
                
                # Mark that this line was cleaned (for debugging/tracking)
                dialogue_entry["cleaned"] = True
    
    return script_data, cleaned_count


def parse_friends_script(raw_text, metadata):
    script_data = []
    current_scene = {
        "scene": None,
        "scene_number": 0,
        "characters": set(),
        "dialogue": [],
        "page_numbers": set(),
        "episode_title": metadata.get("episode_title"),
        "stage_directions": []  # NEW: Track stage directions
    }
    current_speaker = None
    buffer = ""
    scene_counter = 0

    lines = raw_text.splitlines()

    for line_num, line in enumerate(lines):
        line = line.strip()

        if not line:
            continue

        # Skip title+URL+page-number noise lines
        if (
            ("The One Where" in line or "The One with" in line)
            and "http" in line
            and re.search(r"\d+/\d+", line)
        ):
            continue

        # Skip lines starting with a date like "7/5/25, 8:20 AM"
        if re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}', line):
            continue

        # Scene heading
        if line.startswith("[Scene:"):
            if current_scene["dialogue"] or current_scene["stage_directions"]:
                current_scene["characters"] = list(current_scene["characters"])
                current_scene["page_numbers"] = list(current_scene["page_numbers"])
                script_data.append(current_scene)

            scene_counter += 1
            scene_match = re.search(r"\[Scene:\s*(.*?)\]", line)
            current_scene = {
                "scene": scene_match.group(1) if scene_match else None,
                "scene_number": scene_counter,
                "characters": set(),
                "dialogue": [],
                "page_numbers": set(),
                "episode_title": metadata.get("episode_title"),
                "stage_directions": [],
                "line_number_start": line_num + 1
            }
            current_speaker = None
            buffer = ""
            continue

        # Capture stage directions
        if line.startswith("[") or line.startswith("("):
            current_scene["stage_directions"].append({
                "direction": line,
                "line_number": line_num + 1
            })
            continue

        # Speaker line
        match = re.match(r"^([A-Z][a-z]+):\s*(.*)", line)
        if match:
            # Save previous buffered line
            if current_speaker and buffer:
                cleaned, page_number = clean_line_and_extract_page(buffer.strip(), episode_title=metadata.get("episode_title"))
                entry = {
                    "speaker": current_speaker, 
                    "line": cleaned,
                    "line_number": line_num + 1
                }
                if page_number:
                    entry["page_number"] = page_number
                    current_scene["page_numbers"].add(page_number)
                current_scene["dialogue"].append(entry)

            current_speaker = match.group(1)
            buffer = match.group(2)
            current_scene["characters"].add(current_speaker)
        else:
            if current_speaker:
                buffer += " " + line

    # Final dialogue flush
    if current_speaker and buffer:
        cleaned, page_number = clean_line_and_extract_page(buffer.strip(), episode_title=metadata.get("episode_title"))
        entry = {
            "speaker": current_speaker, 
            "line": cleaned,
            "line_number": len(lines)
        }
        if page_number:
            entry["page_number"] = page_number
            current_scene["page_numbers"].add(page_number)
        current_scene["dialogue"].append(entry)
        current_scene["characters"] = list(current_scene["characters"])
        current_scene["page_numbers"] = list(current_scene["page_numbers"])
        script_data.append(current_scene)

    return script_data


def parse_friends_script_with_metadata(pdf_path, output_path=None):
    """
    Parse a Friends script PDF and return comprehensive data with metadata
    """
    # Extract text
    text = extract_text_from_pdf(pdf_path)
    
    # Extract metadata
    metadata = extract_episode_metadata(text, pdf_path)
    
    # Parse script
    script_data = parse_friends_script(text, metadata)
    
    # Clean episode title from dialogue lines
    script_data, cleaned_count = clean_episode_title_from_dialogue(script_data, metadata.get("episode_title"))
    
    # Calculate statistics
    statistics = calculate_script_statistics(script_data)
    
    # Add cleaning info to parsing metadata
    parsing_info = {
        "parser_version": "2.0",
        "total_lines_processed": len(text.splitlines()),
        "parsing_date": datetime.now().isoformat(),
        "dialogue_lines_cleaned": cleaned_count
    }
    
    # Combine everything
    full_data = {
        "metadata": metadata,
        "statistics": statistics,
        "script": script_data,
        "parsing_info": parsing_info
    }
    
    # Save to file if output path provided
    if output_path:
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Enhanced script data saved to: {output_path}")
    
    # Return the full_data instead of None
    return full_data


if __name__ == "__main__":
    pdf_path = "Raw_Data/S1_Scripts/S1_Ep6.pdf"
    output_path = "Parsed_Scripts/parsed_s1_e6.json"
    
    # Parse with full metadata
    result = parse_friends_script_with_metadata(pdf_path, output_path)
    
    # Print summary
    print(f"📺 Episode: {result['metadata']['episode_title']}")
    print(f"🎬 Season {result['metadata']['season']}, Episode {result['metadata']['episode_number']}")
    print(f"📄 Total Pages: {result['metadata']['total_pages']}")
    print(f"🎭 Total Characters: {len(result['statistics']['unique_characters'])}")
    print(f"💬 Total Dialogue Lines: {result['statistics']['total_dialogue_lines']}")
    print(f"🎬 Total Scenes: {result['statistics']['total_scenes']}")
    
    if result['metadata']['writers']:
        print(f"✍️ Writers: {', '.join(result['metadata']['writers'])}")
    if result['metadata']['directors']:
        print(f"🎬 Directors: {', '.join(result['metadata']['directors'])}")