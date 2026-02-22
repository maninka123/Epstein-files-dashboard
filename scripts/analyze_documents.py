#!/usr/bin/env python3
"""
Epstein Files — AI Document Analysis Script (Gemini 2.0 / 1.5 Flash)
============================================================
Analyzes scanned documents in data/images/documents/ to extract:
- Names of famous people / associates
- Detection of people/faces (including redacted/blurry ones)
- Document type classification
- Evidence importance score (1-10)
- Summary of findings

Features:
- SDK: Google Gen AI (the modern SDK)
- Checkpointing: Resume from last processed file
- Structured Export: Saves to CSV and Excel
- Rate Limit Handling: Gracefully handles 429 errors
"""

import os
import json
import time
import logging
from pathlib import Path
import pandas as pd
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv
from tqdm import tqdm
import sys

# Load environment variables from .env file
load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "images" / "documents"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
STATE_FILE = PROCESSED_DIR / "analysis_state.json"
RESULTS_CSV = PROCESSED_DIR / "evidence_analysis.csv"
RESULTS_XLSX = PROCESSED_DIR / "evidence_analysis.xlsx"
MODEL_CACHE = PROCESSED_DIR / "last_working_model.txt"

# The Prompt
ANALYSIS_PROMPT = """
Analyze this document scan from the Epstein case files. 
Extract structured intelligence about the contents.

Provide your response in JSON format with the following keys:
1. 'document_type': (string) e.g., 'Flight Manifest', 'Court Filing', 'Personal Letter', 'Photo Evidence'.
2. 'entities_found': (list of strings) Names of famous people, politicians, or known associates mentioned or pictured.
3. 'person_detection': (string) Describe any people or faces visible. Note if they appear to be minors or if they are redacted/blacked out.
4. 'key_findings': (string) A concise summary of the most important information in this document.
5. 'importance_score': (integer, 1-10) How valuable is this as evidence? (1 = boilerplate/spam, 10 = smoking gun).
6. 'reasoning': (string) Why did you give it that importance score?

Return ONLY the raw JSON.
"""

# ── Logging ───────────────────────────────────────────────────────────────────

# Suppress noisy HTTP/AFC logs from google-genai SDK
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)]
)
# Our logger stays at INFO
log = logging.getLogger("ai_analysis")
log.setLevel(logging.INFO)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_state():
    """Load the progress state."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            return {"processed_files": [], "last_file": None}
    return {"processed_files": [], "last_file": None}

def save_state(processed_files, last_file):
    """Save the progress state."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "processed_files": list(processed_files),
        "last_file": str(last_file),
        "total_processed": len(processed_files),
        "updated_at": time.ctime()
    }, indent=2))

def save_results(results_list):
    """Append results to CSV and update Excel."""
    if not results_list:
        return
        
    df = pd.DataFrame(results_list)
    
    # Save CSV (Append if exists)
    if RESULTS_CSV.exists():
        try:
            existing_df = pd.read_csv(RESULTS_CSV)
            df = pd.concat([existing_df, df], ignore_index=True).drop_duplicates(subset=["file_name"])
        except:
            pass
    
    df.to_csv(RESULTS_CSV, index=False)
    
    # Save Excel
    try:
        df.to_excel(RESULTS_XLSX, index=False, engine='openpyxl')
        log.info(f"📁 Updated {RESULTS_XLSX.name}")
    except Exception as e:
        log.warning(f"⚠️ Could not save Excel: {e}")

# ── Main Analysis ──────────────────────────────────────────────────────────────

def main():
    log.info("="*60)
    log.info("  EPSTEIN FILES — AI DOCUMENT ANALYSIS")
    log.info("="*60)

    if not DOCS_DIR.exists():
        log.error(f"❌ Documents directory not found: {DOCS_DIR}")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("❌ GEMINI_API_KEY not found in .env file.")
        return

    # Initialize Client
    client = genai.Client(api_key=api_key)
    
    log.info("🔍 Detecting available models with active quota...")
    
    # Models that DO NOT support image input — skip these
    SKIP_KEYWORDS = ['gemma', 'embedding', 'imagen', 'veo', 'aqa', 'tts', 'audio',
                     'nano-banana', 'robotics', 'computer-use', 'deep-research']
    
    try:
        available_models = [m.name for m in client.models.list() if 'generateContent' in m.supported_actions]
        vision_models = [m for m in available_models 
                         if not any(skip in m.lower() for skip in SKIP_KEYWORDS)]
        flash_models = [m for m in vision_models if 'flash' in m.lower()]
        other_models = [m for m in vision_models if 'flash' not in m.lower()]
        candidate_models = flash_models + other_models
        log.info(f"   Found {len(candidate_models)} vision-capable models.")
    except Exception as e:
        log.error(f"❌ Failed to list models: {e}")
        return
    
    # --- Try cached model first (saves ~18 test requests) ---
    model_id = None
    if MODEL_CACHE.exists():
        cached = MODEL_CACHE.read_text().strip()
        try:
            client.models.generate_content(model=cached, contents="ok")
            model_id = cached
            log.info(f"✅ Using cached model: {model_id}")
        except:
            log.info(f"   Cached model '{cached}' no longer available. Searching...")
    
    # --- If no cache hit, search all models with retries ---
    if not model_id:
        MAX_RETRIES = 3
        for attempt in range(1, MAX_RETRIES + 1):
            log.info(f"   Attempt {attempt}/{MAX_RETRIES}: Testing model quotas...")
            for m in candidate_models:
                try:
                    client.models.generate_content(model=m, contents="ok")
                    model_id = m
                    log.info(f"✅ Found working model: {model_id}")
                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    if "exhausted" in err_msg or "limit: 0" in err_msg or "429" in err_msg:
                        continue
                    log.warning(f"⚠️ Could not use {m}: {e}")
            
            if model_id:
                break
            
            if attempt < MAX_RETRIES:
                log.warning("⏳ All models rate-limited. Waiting 60s for per-minute quota to reset...")
                for sec in tqdm(range(60, 0, -1), desc="⏳ Waiting", unit="s", 
                               bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s", ncols=60):
                    time.sleep(1)
            else:
                log.error("❌ DAILY LIMIT REACHED — All vision models exhausted after 3 retries.")
                log.error("   Your free daily quota is used up. Try again tomorrow!")
                return
    
    # Cache the working model for next run
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_CACHE.write_text(model_id)

    state = load_state()
    processed_files = set(state.get("processed_files", []))
    
    # Get all images
    all_images = sorted([f for f in DOCS_DIR.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png')])
    to_process = [f for f in all_images if f.name not in processed_files]

    if not to_process:
        log.info("✅ All files in this folder have already been processed.")
        return

    log.info(f"📊 Found {len(all_images)} total images. {len(to_process)} remaining to process.")
    log.info("🚀 Starting analysis... (Ctrl+C to stop safely)")

    current_batch = []
    batch_size = 5 # Save every 5 images
    
    pbar = tqdm(
        to_process,
        desc="🔍 Analyzing",
        unit="img",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        ncols=90
    )
    
    try:
        for i, img_path in enumerate(pbar):
            pbar.set_postfix_str(img_path.name[-30:], refresh=True)
            
            try:
                # Load image as bytes
                with open(img_path, 'rb') as f:
                    img_bytes = f.read()
                
                # Send to Gemini
                response = client.models.generate_content(
                    model=model_id,
                    contents=[
                        ANALYSIS_PROMPT,
                        types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                    )
                )
                
                # Parse JSON response
                result = response.parsed if hasattr(response, 'parsed') else None
                
                # If parsed is None, try manual text parsing
                if result is None:
                    text_content = response.text
                    clean_text = text_content.replace('```json', '').replace('```', '').strip()
                    try:
                        result = json.loads(clean_text)
                    except Exception as e:
                        log.error(f"❌ Failed to parse JSON for {img_path.name}: {e}")
                        continue
                
                if not isinstance(result, dict):
                    log.error(f"❌ Result for {img_path.name} is not a dictionary: {type(result)}")
                    continue
                
                # Add metadata
                result['file_name'] = img_path.name
                result['file_path'] = str(img_path.relative_to(BASE_DIR))
                result['analyzed_at'] = time.ctime()
                
                current_batch.append(result)
                processed_files.add(img_path.name)
                
                # Checkpointing
                if len(current_batch) >= batch_size:
                    save_results(current_batch)
                    save_state(processed_files, img_path.name)
                    current_batch = []
                    pbar.set_postfix_str(f"💾 Saved ({len(processed_files)} total)", refresh=True)

                # Cooldown with visible countdown
                for sec in range(10, 0, -1):
                    pbar.set_postfix_str(f"⏳ {sec}s cooldown", refresh=True)
                    time.sleep(1)

            except Exception as e:
                if "429" in str(e):
                    log.warning("⏳ Rate limit hit. Waiting 60s...")
                    for sec in tqdm(range(60, 0, -1), desc="⏳ Cooldown", unit="s",
                                   bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s", ncols=60,
                                   file=sys.stderr):
                        time.sleep(1)
                    # Retry the same image
                    pbar.update(-1)
                    continue
                log.error(f"❌ Error analyzing '{img_path.name}': {e}")
                continue

    except KeyboardInterrupt:
        log.info("\n🛑 User interrupted. Saving progress...")
    
    finally:
        if current_batch:
            save_results(current_batch)
            if 'i' in locals() and i < len(to_process):
                save_state(processed_files, to_process[i].name)
            elif to_process:
                save_state(processed_files, to_process[-1].name)
        log.info("🏁 Analysis paused. Run script again to resume.")

if __name__ == "__main__":
    main()
