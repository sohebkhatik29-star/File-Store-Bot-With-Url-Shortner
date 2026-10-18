# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/parser.py
# Purpose: Smart movie title normalization, quality detection, language parsing,
#          and strict title similarity matcher.
# ==============================================================================

import re
import difflib
from typing import Dict, Any

# Quality mapping with regex patterns
QUALITY_PATTERNS = [
    (r"(?i)\b(2160p|4k|uhd)\b", "2160p"),
    (r"(?i)\b(1080p|fhd|1080)\b", "1080p"),
    (r"(?i)\b(720p|hd|720)\b", "720p"),
    (r"(?i)\b(480p|sd|480)\b", "480p"),
    (r"(?i)\b(540p|360p)\b", "480p"),
]

# Common audio & language patterns
LANGUAGE_PATTERNS = [
    (r"(?i)\b(hindi|hin)\b", "Hindi"),
    (r"(?i)\b(english|eng)\b", "English"),
    (r"(?i)\b(tamil|tam)\b", "Tamil"),
    (r"(?i)\b(telugu|tel)\b", "Telugu"),
    (r"(?i)\b(malayalam|mal)\b", "Malayalam"),
    (r"(?i)\b(kannada|kan)\b", "Kannada"),
    (r"(?i)\b(bengali|ben)\b", "Bengali"),
    (r"(?i)\b(punjabi|pun)\b", "Punjabi"),
    (r"(?i)\b(italian|ita)\b", "Italian"),
    (r"(?i)\b(spanish|spa|esp)\b", "Spanish"),
    (r"(?i)\b(french|fre|fra)\b", "French"),
    (r"(?i)\b(dual[\s_-]?audio)\b", "Dual Audio"),
    (r"(?i)\b(multi[\s_-]?audio)\b", "Multi Audio"),
]

# Junk tags to strip from titles
JUNK_TAGS = [
    r"\[.*?\]",                   # Anything inside square brackets e.g. [YTS.MX], [TG]
    r"\(.*?\b(yify|rarbg|psa|bolly|vj|codex|ash|tele|channel|unrated|extended|remastered)\b.*?\)",
    r"@[\w_]+",                   # Telegram usernames e.g. @Tech_VJ
    r"(?i)\b(unrated|bluray|blu-ray|web-dl|webdl|webrip|hdrip|dvdrip|hdtv|camrip|predvd|hdcam)\b",
    r"(?i)\b(x264|x265|hevc|h264|h265|avc|10bit|8bit|aac|ac3|dts|ddp5\.1|eac3|5\.1)\b",
    r"(?i)\b(esub|esubs|sub|subtitles|clean|org|original|uncut|extended|remastered)\b",
    r"(?i)\b(mkv|mp4|avi|webm)\b",
    r"[-_.]+",                    # Replace separators
]

def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string (e.g. 450 MB, 1.25 GB)."""
    if not size_bytes or size_bytes <= 0:
        return "Unknown Size"
    power = 1024
    n = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    while size_bytes >= power and n < len(units) - 1:
        size_bytes /= power
        n += 1
    return f"{size_bytes:.2f} {units[n]}"

def normalize_title(title: str) -> str:
    """Normalize a movie title for strict session matching."""
    if not title:
        return ""
    normalized = title.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

def extract_movie_metadata(filename: str, caption: str = "") -> Dict[str, Any]:
    """
    Extracts movie title, release year, quality, and languages from filename & caption.
    """
    raw_name = filename or caption or "Untitled_Movie"
    base_name = raw_name

    # 1. Extract Quality
    quality_found = None
    for pattern, label in QUALITY_PATTERNS:
        if re.search(pattern, base_name):
            quality_found = label
            break
    if not quality_found and caption:
        for pattern, label in QUALITY_PATTERNS:
            if re.search(pattern, caption):
                quality_found = label
                break

    # 2. Extract Languages
    languages_found = []
    for pattern, lang in LANGUAGE_PATTERNS:
        if re.search(pattern, base_name) or (caption and re.search(pattern, caption)):
            if lang not in languages_found:
                languages_found.append(lang)

    # 3. Extract Year (between 1950 and 2099)
    year_found = None
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", base_name)
    if year_match:
        year_found = int(year_match.group(1))

    # 4. Clean Title
    cleaned = base_name
    cleaned = re.sub(r"\[.*?\]", " ", cleaned)

    if year_match:
        cleaned_up_to_year = base_name[:year_match.start()]
        # Strip trailing brackets like '(' or '[' or '-'
        cleaned_up_to_year = re.sub(r"[\(\[\{\-_.\s]+$", "", cleaned_up_to_year)
        if len(cleaned_up_to_year.strip()) >= 2:
            cleaned = cleaned_up_to_year

    for pattern in JUNK_TAGS:
        cleaned = re.sub(pattern, " ", cleaned)

    for pattern, _ in QUALITY_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned)

    cleaned = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", cleaned)
    cleaned = re.sub(r"[\(\)\[\]\{\}]+", " ", cleaned)
    cleaned = re.sub(r"[._\-+]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = cleaned.split()
    formatted_words = []
    for w in words:
        if len(w) <= 3 and w.isalpha() and not w.lower() in ("the", "and", "for", "in", "of"):
            formatted_words.append(w.upper())
        else:
            formatted_words.append(w.capitalize())
    final_title = " ".join(formatted_words) if formatted_words else "Untitled Movie"

    is_confident = bool(cleaned and len(cleaned) >= 2 and quality_found)

    return {
        "raw_filename": raw_name,
        "title": final_title,
        "normalized_title": normalize_title(final_title),
        "year": year_found,
        "quality": quality_found or "720p",
        "quality_detected": bool(quality_found),
        "languages": languages_found or ["Hindi"],
        "is_confident": is_confident,
    }

def is_title_match(active_title: str, incoming_title: str, threshold: float = 0.65) -> bool:
    """Strictly prevents saving KGF inside Jaat session!"""
    norm_active = normalize_title(active_title)
    norm_incoming = normalize_title(incoming_title)

    if not norm_active or not norm_incoming:
        return False
    if norm_active == norm_incoming:
        return True

    active_tokens = set(norm_active.split())
    incoming_tokens = set(norm_incoming.split())

    if active_tokens and incoming_tokens:
        intersection = active_tokens.intersection(incoming_tokens)
        overlap_active = len(intersection) / len(active_tokens)
        overlap_incoming = len(intersection) / len(incoming_tokens)
        if overlap_active >= 0.8 or overlap_incoming >= 0.8:
            return True

    ratio = difflib.SequenceMatcher(None, norm_active, norm_incoming).ratio()
    return ratio >= threshold
