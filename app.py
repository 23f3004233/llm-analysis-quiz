from flask import Flask, request, jsonify
import os
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import base64
import traceback
import re
from urllib.parse import urljoin, urlparse
import mimetypes
from io import BytesIO

from openai import OpenAI
# import speech_recognition as sr
# from pydub import AudioSegment
import pandas as pd
import PyPDF2
from bs4 import BeautifulSoup

# AI Pipe Configuration
client = OpenAI(
    api_key=os.environ.get("AIPIPE_TOKEN"),
    base_url="https://aipipe.org/openai/v1"
)

app = Flask(__name__)

YOUR_EMAIL = os.environ.get("STUDENT_EMAIL", "your-email@example.com")
YOUR_SECRET = os.environ.get("STUDENT_SECRET", "your-secret-string")

def get_browser():
    """Initialize Chrome"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    chrome_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser", 
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable"
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_options.binary_location = path
            break
    
    return webdriver.Chrome(options=chrome_options)

def extract_all_links_from_html(html, base_url):
    """Extract ALL downloadable links from HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    # Find all <a> tags with href
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        full_url = urljoin(base_url, href)
        links.append({
            'url': full_url,
            'text': a_tag.get_text(strip=True),
            'type': 'link'
        })
    
    # Find all <source> tags (audio/video)
    for source_tag in soup.find_all('source', src=True):
        src = source_tag['src']
        full_url = urljoin(base_url, src)
        links.append({
            'url': full_url,
            'text': 'media',
            'type': 'media'
        })
    
    # Find all <audio> tags
    for audio_tag in soup.find_all('audio', src=True):
        src = audio_tag['src']
        full_url = urljoin(base_url, src)
        links.append({
            'url': full_url,
            'text': 'audio',
            'type': 'audio'
        })
    
    # Find all <video> tags
    for video_tag in soup.find_all('video', src=True):
        src = video_tag['src']
        full_url = urljoin(base_url, src)
        links.append({
            'url': full_url,
            'text': 'video',
            'type': 'video'
        })
    
    return links

def fetch_quiz_page(url):
    """Fetch quiz page and extract all content"""
    print(f"\n{'='*60}")
    print(f"Fetching: {url}")
    
    driver = None
    try:
        driver = get_browser()
        driver.get(url)
        time.sleep(5)
        
        page_html = driver.page_source
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Extract all links
        all_links = extract_all_links_from_html(page_html, url)
        
        print(f"✓ Loaded: {len(page_text)} chars text")
        print(f"✓ Found {len(all_links)} downloadable items")
        
        print(f"\nText preview:")
        print("-" * 60)
        print(page_text[:800])
        print("-" * 60)
        
        print(f"\nDownloadable items:")
        for link in all_links[:10]:
            print(f"  [{link['type']}] {link['url']}")
        
        return {
            "html": page_html,
            "text": page_text,
            "url": url,
            "all_links": all_links
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def detect_file_type(url, content_bytes=None):
    """Detect file type from URL or content"""
    # Try URL extension
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    
    type_map = {
        '.pdf': 'pdf',
        '.csv': 'csv',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.txt': 'text',
        '.mp3': 'audio',
        '.wav': 'audio',
        '.ogg': 'audio',
        '.mp4': 'video',
        '.avi': 'video',
        '.mov': 'video',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.png': 'image',
        '.gif': 'image'
    }
    
    if ext in type_map:
        return type_map[ext]
    
    # Try MIME type from content
    if content_bytes:
        mime = mimetypes.guess_type(url)[0]
        if mime:
            if 'audio' in mime:
                return 'audio'
            elif 'video' in mime:
                return 'video'
            elif 'image' in mime:
                return 'image'
            elif 'pdf' in mime:
                return 'pdf'
    
    return 'unknown'

def transcribe_audio(audio_bytes):
    """Transcribe audio to text using speech recognition"""
    print("  🎤 Audio transcription disabled")
    return None
    # print("  🎤 Transcribing audio...")
    
    # try:
    #     # Convert audio to WAV format
    #     audio = AudioSegment.from_file(BytesIO(audio_bytes))
    #     audio = audio.set_channels(1).set_frame_rate(16000)
        
    #     wav_io = BytesIO()
    #     audio.export(wav_io, format='wav')
    #     wav_io.seek(0)
        
    #     # Use speech recognition
    #     recognizer = sr.Recognizer()
    #     with sr.AudioFile(wav_io) as source:
    #         audio_data = recognizer.record(source)
    #         text = recognizer.recognize_google(audio_data)
        
    #     print(f"  ✓ Transcribed: {len(text)} chars")
    #     print(f"  Preview: {text[:200]}")
    #     return text
    
    # except Exception as e:
    #     print(f"  ✗ Transcription failed: {e}")
    #     # Fallback: try with OpenAI Whisper if available
    #     try:
    #         print("  Trying OpenAI Whisper...")
    #         # Save audio temporarily
    #         temp_audio = BytesIO(audio_bytes)
    #         temp_audio.name = "audio.mp3"
            
    #         response = client.audio.transcriptions.create(
    #             model="whisper-1",
    #             file=temp_audio
    #         )
    #         text = response.text
    #         print(f"  ✓ Whisper transcribed: {len(text)} chars")
    #         return text
    #     except Exception as e2:
    #         print(f"  ✗ Whisper also failed: {e2}")
    #         return None

def process_pdf(pdf_bytes):
    """Extract text from PDF"""
    print("  📄 Processing PDF...")
    try:
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        all_text = []
        for i, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            all_text.append(f"[Page {i+1}]\n{text}")
        
        full_text = "\n\n".join(all_text)
        print(f"  ✓ Extracted {len(full_text)} chars from {len(pdf_reader.pages)} pages")
        return full_text
    except Exception as e:
        print(f"  ✗ PDF processing failed: {e}")
        return None

def process_csv(csv_bytes):
    """Process CSV file"""
    print("  📊 Processing CSV...")
    try:
        df = pd.read_csv(BytesIO(csv_bytes))
        
        # Get summary
        summary = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "head": df.head(10).to_dict('records'),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "describe": df.describe().to_dict() if not df.empty else {}
        }
        
        print(f"  ✓ CSV: {df.shape[0]} rows x {df.shape[1]} columns")
        return {
            "dataframe": df,
            "summary": summary,
            "full_data": df.to_dict('records')
        }
    except Exception as e:
        print(f"  ✗ CSV processing failed: {e}")
        return None

def download_and_process_file(url):
    """Download and process any file type"""
    print(f"\n📥 Downloading: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.content
        
        file_type = detect_file_type(url, content)
        print(f"  Type: {file_type}")
        
        result = {
            "url": url,
            "type": file_type,
            "size": len(content),
            "content": None,
            "raw_base64": base64.b64encode(content).decode('utf-8')
        }
        
        # Process based on type
        if file_type == 'audio':
            transcription = transcribe_audio(content)
            result['content'] = transcription
            result['transcription'] = transcription
        
        elif file_type == 'pdf':
            text = process_pdf(content)
            result['content'] = text
            result['text'] = text
        
        elif file_type == 'csv':
            csv_data = process_csv(content)
            if csv_data:
                result['content'] = csv_data['summary']
                result['csv_data'] = csv_data
        
        elif file_type == 'text':
            result['content'] = content.decode('utf-8', errors='ignore')
        
        print(f"  ✓ Processed successfully")
        return result
    
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        traceback.print_exc()
        return None

def call_ai(prompt, max_retries=3):
    """Call AI with robust error handling"""
    for attempt in range(max_retries):
        try:
            print(f"\n🤖 AI call {attempt + 1}/{max_retries}...")
            
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0
            )
            
            response_text = resp.choices[0].message.content
            print(f"✓ Response: {len(response_text)} chars")
            return response_text
            
        except Exception as e:
            print(f"✗ Error: {e}")
            if attempt == max_retries - 1:
                traceback.print_exc()
                return None
            time.sleep(2)
    
    return None

def solve_quiz_with_ai(quiz_data):
    """Solve quiz using AI as a data analyst"""
    print(f"\n{'='*60}")
    print("SOLVING QUIZ WITH AI")
    print(f"{'='*60}")
    
    # Build comprehensive context
    context_parts = [
        "=== QUIZ PAGE CONTENT ===",
        quiz_data['text'],
        "\n=== AVAILABLE FILES ===",
    ]
    
    for link in quiz_data.get('all_links', []):
        context_parts.append(f"[{link['type']}] {link['url']} - {link['text']}")
    
    context = "\n".join(context_parts)
    
    prompt = f"""You are an expert data analyst solving a quiz. Your task is to analyze the question and determine what needs to be done.

{context}

YOUR ROLE:
- You are a professional data analyst
- You must actually solve the problem, not just copy text
- You must think step by step
- You must identify ALL files that need to be downloaded

CRITICAL INSTRUCTIONS:
1. READ the question carefully and understand what is being asked
2. IDENTIFY all files that need to be downloaded (CSV, PDF, audio, video, images, etc.)
3. EXTRACT the submission URL from the page
4. If you can answer without files, provide the answer
5. If files are needed, list ALL file URLs

IMPORTANT RULES:
- DO NOT just copy text from the question
- DO NOT use placeholder URLs like "example.com"
- DO NOT answer "your secret" or "anything you want" - these are just placeholders!
- If the question shows "your secret", look for the ACTUAL secret value on the page
- If you see audio/video files, you MUST include them in files_needed
- Extract the REAL submission URL from the page content

RESPONSE FORMAT (JSON only, no markdown):
{{
    "submit_url": "actual_url_from_page",
    "reasoning": "brief explanation of what you understand",
    "answer": your_answer_or_null,
    "files_needed": ["url1", "url2"]
}}

If you cannot determine the answer without files, set answer to null.
"""

    response_text = call_ai(prompt)
    if not response_text:
        return None

    try:
        # Parse response
        response_text = response_text.strip()
        for marker in ['```json', '```', '`']:
            response_text = response_text.replace(marker, '')
        response_text = response_text.strip()
        
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start == -1 or end == 0:
            print(f"✗ No JSON in response")
            return None
        
        json_str = response_text[start:end]
        result = json.loads(json_str)
        
        print("\n✓ Parsed JSON:")
        print(json.dumps(result, indent=2))
        
        # Fix URLs
        if result.get('submit_url'):
            parsed_base = urlparse(quiz_data['url'])
            base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
            result['submit_url'] = urljoin(base_domain, result['submit_url'])
        
        if result.get('files_needed'):
            fixed_files = []
            parsed_base = urlparse(quiz_data['url'])
            base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
            
            for file_url in result['files_needed']:
                fixed_url = urljoin(base_domain, file_url)
                fixed_files.append(fixed_url)
                print(f"  File: {fixed_url}")
            
            result['files_needed'] = fixed_files
        
        return result
        
    except Exception as e:
        print(f"✗ Parse error: {e}")
        traceback.print_exc()
        return None

def solve_with_processed_files(quiz_data, processed_files):
    """Solve quiz after processing all files"""
    print(f"\n{'='*60}")
    print("SOLVING WITH PROCESSED FILES")
    print(f"{'='*60}")
    
    # Build comprehensive prompt with all processed data
    file_context = []
    
    for pf in processed_files:
        file_context.append(f"\n=== FILE: {pf['url']} ===")
        file_context.append(f"Type: {pf['type']}")
        
        if pf['type'] == 'audio' and pf.get('transcription'):
            file_context.append("Audio Transcription:")
            file_context.append(pf['transcription'])
        
        elif pf['type'] == 'pdf' and pf.get('text'):
            file_context.append("PDF Content:")
            file_context.append(pf['text'][:2000])
        
        elif pf['type'] == 'csv' and pf.get('csv_data'):
            csv_data = pf['csv_data']
            file_context.append(f"CSV Shape: {csv_data['summary']['shape']}")
            file_context.append(f"Columns: {csv_data['summary']['columns']}")
            file_context.append(f"First 10 rows: {json.dumps(csv_data['summary']['head'], indent=2)}")
            file_context.append(f"Statistics: {json.dumps(csv_data['summary']['describe'], indent=2)}")
    
    files_text = "\n".join(file_context)
    
    prompt = f"""You are an expert data analyst. You have been given a quiz question and all necessary files have been processed.

=== ORIGINAL QUESTION ===
{quiz_data['text']}

=== PROCESSED FILES ===
{files_text}

YOUR TASK:
You are a professional data analyst. You must:
1. Understand what the question is asking
2. Use the audio transcription (if any) to understand the exact task
3. Analyze the data files (CSV, PDF, etc.)
4. Perform the required calculations/analysis
5. Provide the final answer

CRITICAL:
- If there's an audio file, it likely contains instructions on what to do
- Follow those instructions EXACTLY
- Actually perform calculations, don't just guess
- The answer must be precise and correct

RESPONSE FORMAT (JSON only):
{{
    "submit_url": "https://tds-llm-analysis.s-anand.net/submit",
    "reasoning": "step by step explanation of your solution",
    "calculations": "show your work",
    "answer": your_final_answer
}}

The answer can be a number, string, boolean, or JSON object depending on what's asked.
"""

    response_text = call_ai(prompt)
    if not response_text:
        return None

    try:
        response_text = response_text.strip()
        for marker in ['```json', '```', '`']:
            response_text = response_text.replace(marker, '')
        response_text = response_text.strip()
        
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start == -1 or end == 0:
            return None
        
        result = json.loads(response_text[start:end])
        
        print("\n✓ Final answer:")
        print(json.dumps(result, indent=2))
        
        # Fix submit URL
        if result.get('submit_url'):
            parsed_base = urlparse(quiz_data['url'])
            base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
            result['submit_url'] = urljoin(base_domain, result['submit_url'])
        
        return result
    
    except Exception as e:
        print(f"✗ Parse error: {e}")
        return None

def submit_answer(submit_url, email, secret, quiz_url, answer):
    """Submit answer"""
    print(f"\n{'='*60}")
    print("SUBMITTING ANSWER")
    print(f"{'='*60}")
    
    payload = {
        "email": email,
        "secret": secret,
        "url": quiz_url,
        "answer": answer
    }
    
    print(f"To: {submit_url}")
    print(f"Answer: {answer}")

    try:
        response = requests.post(submit_url, json=payload, timeout=30)
        result = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")
        
        return result
    except Exception as e:
        print(f"✗ Error: {e}")
        return {"correct": False, "reason": str(e)}

def solve_quiz_chain(initial_url, email, secret, max_time=180):
    """Solve complete quiz chain"""
    print(f"\n{'#'*60}")
    print(f"# QUIZ CHAIN START")
    print(f"{'#'*60}\n")
    
    start_time = time.time()
    current_url = initial_url
    results = []

    while current_url and (time.time() - start_time) < max_time:
        print(f"\n{'*'*60}")
        print(f"Quiz #{len(results) + 1}")
        print(f"Time: {time.time() - start_time:.1f}s / {max_time}s")
        print(f"{'*'*60}")

        # Fetch page
        quiz_data = fetch_quiz_page(current_url)
        
        # Solve with AI
        solution = solve_quiz_with_ai(quiz_data)
        if not solution:
            results.append({"url": current_url, "error": "Failed to parse"})
            break

        # Download and process files if needed
        if solution.get("files_needed"):
            print(f"\n📎 Processing {len(solution['files_needed'])} files...")
            
            processed_files = []
            for file_url in solution['files_needed']:
                pf = download_and_process_file(file_url)
                if pf:
                    processed_files.append(pf)
            
            if processed_files:
                # Re-solve with processed files
                solution = solve_with_processed_files(quiz_data, processed_files)
                if not solution:
                    results.append({"url": current_url, "error": "Failed with files"})
                    break

        # Submit
        submit_result = submit_answer(
            solution["submit_url"],
            email,
            secret,
            current_url,
            solution["answer"]
        )

        results.append({
            "url": current_url,
            "answer": solution["answer"],
            "correct": submit_result.get("correct"),
            "reason": submit_result.get("reason")
        })

        if submit_result.get("correct"):
            print("\n✅ CORRECT")
        else:
            print(f"\n❌ WRONG: {submit_result.get('reason')}")

        current_url = submit_result.get("url")
        if not current_url:
            print("\n✓ Chain complete")
            break

    print(f"\n{'#'*60}")
    print(f"# FINISHED: {len(results)} quizzes")
    print(f"{'#'*60}\n")

    return results

@app.route('/quiz', methods=['POST'])
def handle_quiz():
    """Main endpoint"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        if data.get("secret") != YOUR_SECRET:
            return jsonify({"error": "Invalid secret"}), 403

        if data.get("email") != YOUR_EMAIL:
            return jsonify({"error": "Invalid email"}), 403

        quiz_url = data.get("url")
        if not quiz_url:
            return jsonify({"error": "No URL provided"}), 400

        results = solve_quiz_chain(quiz_url, YOUR_EMAIL, YOUR_SECRET)

        return jsonify({"status": "completed", "results": results}), 200

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "LLM Quiz Solver",
        "status": "running"
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*60}")
    print(f"Production Quiz Solver - Port {port}")
    print(f"Handles: Audio, Video, PDF, CSV, Images, Text")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
