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

from openai import OpenAI

# AI Pipe Configuration
client = OpenAI(
    api_key=os.environ.get("AIPIPE_TOKEN"),
    base_url="https://aipipe.org/openai/v1"
)

app = Flask(__name__)

YOUR_EMAIL = os.environ.get("STUDENT_EMAIL", "your-email@example.com")
YOUR_SECRET = os.environ.get("STUDENT_SECRET", "your-secret-string")

def ensure_absolute_url(url, base_url):
    """Convert relative URL to absolute URL"""
    if not url:
        return ""
    
    # Strip whitespace
    url = url.strip()
    
    # Already absolute
    if url.startswith('http://') or url.startswith('https://'):
        return url
    
    # Parse base URL to get domain
    parsed_base = urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    # Convert relative to absolute
    absolute_url = urljoin(base_domain, url)
    
    print(f"  Converted '{url}' → '{absolute_url}'")
    return absolute_url

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
            print(f"✓ Chrome: {path}")
            break
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def extract_urls_from_text(text, base_url):
    """Extract URLs from text"""
    urls = []
    
    # Find http/https URLs
    http_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls.extend(re.findall(http_pattern, text))
    
    # Find relative URLs that might be submit endpoints
    relative_pattern = r'(?:POST|post|submit|POST to|post to)\s+(?:to\s+)?([/\w\-\.]+)'
    relative_matches = re.findall(relative_pattern, text)
    for match in relative_matches:
        if match.startswith('/'):
            urls.append(urljoin(base_url, match))
    
    return list(set(urls))

def fetch_quiz_page(url):
    """Fetch quiz page"""
    print(f"\n{'='*60}")
    print(f"Fetching: {url}")
    
    driver = None
    try:
        driver = get_browser()
        driver.get(url)
        time.sleep(5)
        
        page_html = driver.page_source
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        print(f"✓ Loaded: {len(page_text)} chars")
        print(f"\nText preview:")
        print("-" * 60)
        print(page_text[:800])
        print("-" * 60)
        
        # Extract all URLs from page
        found_urls = extract_urls_from_text(page_html + " " + page_text, url)
        print(f"\n📎 URLs found in page: {len(found_urls)}")
        for found_url in found_urls[:5]:  # Show first 5
            print(f"  - {found_url}")
        
        return {
            "html": page_html,
            "text": page_text,
            "url": url,
            "found_urls": found_urls
        }
    except Exception as e:
        print(f"✗ Error: {e}")
        traceback.print_exc()
        return {
            "html": "",
            "text": f"Error: {str(e)}",
            "url": url,
            "found_urls": []
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def download_file(url):
    """Download file"""
    print(f"\n📥 Downloading: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = base64.b64encode(response.content).decode('utf-8')
        print(f"✓ Downloaded: {len(content)} chars")
        return content
    except Exception as e:
        print(f"✗ Failed: {e}")
        return None

def call_ai(prompt, max_retries=3):
    """Call AI Pipe"""
    for attempt in range(max_retries):
        try:
            print(f"\n🤖 AI Pipe call {attempt + 1}/{max_retries}...")
            
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.1
            )
            
            response_text = resp.choices[0].message.content
            print(f"✓ Response: {len(response_text)} chars")
            print(f"\nResponse preview:")
            print("-" * 60)
            print(response_text[:600])
            print("-" * 60)
            
            return response_text
            
        except Exception as e:
            print(f"✗ Error attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                traceback.print_exc()
                return None
            time.sleep(2)
    
    return None

def solve_quiz_with_ai(quiz_data):
    """Solve quiz"""
    print(f"\n{'='*60}")
    print("SOLVING QUIZ")
    print(f"{'='*60}")
    
    # Build context with found URLs
    url_context = ""
    if quiz_data.get('found_urls'):
        url_context = f"\nURLs found in the page:\n"
        for url in quiz_data['found_urls'][:10]:
            url_context += f"  - {url}\n"
    
    prompt = f"""You are solving a data analysis quiz. Analyze this page carefully.

QUIZ PAGE TEXT:
{quiz_data['text']}

{url_context}

INSTRUCTIONS:
1. Read the question and understand what it's asking
2. Identify the submission URL - look for phrases like "Post your answer to", "submit to", etc.
3. Find any file download links (look for <a href> tags)
4. Determine the answer to the question

CRITICAL: The submit_url MUST be a complete valid URL starting with http:// or https://

Respond with ONLY this JSON (no markdown, no ```):
{{
    "submit_url": "https://complete-url-here.com/submit",
    "answer": your_answer,
    "files_needed": ["https://file1.pdf", "https://file2.csv"]
}}

If no files needed, use empty array: "files_needed": []

HTML SNIPPET (for finding URLs):
{quiz_data['html'][:4000]}
"""

    response_text = call_ai(prompt)
    if not response_text:
        return None

    try:
        # Clean and parse
        response_text = response_text.strip()
        for marker in ['```json', '```', '`']:
            response_text = response_text.replace(marker, '')
        response_text = response_text.strip()
        
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start == -1 or end == 0:
            print(f"✗ No JSON found")
            print(f"Response: {response_text}")
            return None
        
        json_str = response_text[start:end]
        result = json.loads(json_str)
        
        print("\n✓ Parsed JSON:")
        print(json.dumps(result, indent=2))
        
        # Validate and fix submit_url
        submit_url = result.get('submit_url', '').strip()
        
        if not submit_url:
            print("⚠️  Empty submit_url, trying to find from page URLs")
            # Look for submit/answer URLs in found_urls
            for url in quiz_data.get('found_urls', []):
                if any(keyword in url.lower() for keyword in ['submit', 'answer', 'quiz']):
                    submit_url = url
                    print(f"✓ Found submit URL: {submit_url}")
                    break
        
        if not submit_url or not submit_url.startswith('http'):
            print(f"✗ Invalid submit_url: '{submit_url}'")
            # Try to construct from base URL
            if quiz_data.get('found_urls'):
                submit_url = quiz_data['found_urls'][0]
                print(f"⚠️  Using first URL as fallback: {submit_url}")
        
        # Convert relative URLs to absolute
        submit_url = ensure_absolute_url(submit_url, quiz_data['url'])
        result['submit_url'] = submit_url
        
        print(f"✓ Final submit_url: {submit_url}")
        
        # Validate answer exists
        if 'answer' not in result and not result.get('files_needed'):
            print("✗ Missing answer and files_needed")
            return None
        
        return result
        
    except Exception as e:
        print(f"✗ Parse error: {e}")
        traceback.print_exc()
        return None

def process_files_and_solve(quiz_data, files_needed):
    """Process files"""
    print(f"\n{'='*60}")
    print(f"PROCESSING {len(files_needed)} FILES")
    print(f"{'='*60}")
    
    file_contents = {}
    for file_url in files_needed:
        content = download_file(file_url)
        if content:
            file_contents[file_url] = content[:10000]  # Truncate to avoid token limits

    if not file_contents:
        print("✗ No files downloaded")
        return None

    prompt = f"""Analyze these files to solve the quiz.

QUESTION:
{quiz_data['text']}

FILES (base64 encoded):
{json.dumps(list(file_contents.keys()))}

First file preview (first 1000 chars of base64):
{list(file_contents.values())[0][:1000] if file_contents else 'none'}

INSTRUCTIONS:
1. Decode the files
2. Extract data as needed
3. Calculate the answer
4. Return JSON ONLY:

{{
    "submit_url": "{quiz_data.get('found_urls', [''])[0]}",
    "answer": your_calculated_answer
}}

Important: answer should be a number if calculating sums, counts, etc.
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
        
        # Ensure submit_url is absolute
        if 'submit_url' in result:
            result['submit_url'] = ensure_absolute_url(
                result['submit_url'], 
                quiz_data['url']
            )
        elif quiz_data.get('found_urls'):
            result['submit_url'] = quiz_data['found_urls'][0]
        
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
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(submit_url, json=payload, timeout=30)
        result = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")
        
        return result
    except Exception as e:
        print(f"✗ Error: {e}")
        traceback.print_exc()
        return {"correct": False, "reason": str(e)}

def solve_quiz_chain(initial_url, email, secret, max_time=180):
    """Solve quiz chain"""
    print(f"\n{'#'*60}")
    print(f"# QUIZ CHAIN START")
    print(f"# URL: {initial_url}")
    print(f"{'#'*60}\n")
    
    start_time = time.time()
    current_url = initial_url
    results = []

    while current_url and (time.time() - start_time) < max_time:
        print(f"\n{'*'*60}")
        print(f"Quiz #{len(results) + 1}: {current_url}")
        print(f"Time: {time.time() - start_time:.1f}s / {max_time}s")
        print(f"{'*'*60}")

        quiz_data = fetch_quiz_page(current_url)
        
        solution = solve_quiz_with_ai(quiz_data)
        if not solution:
            print("✗ No solution")
            results.append({"url": current_url, "error": "Failed to parse quiz"})
            break

        if solution.get("files_needed"):
            print(f"\n📎 Files: {solution['files_needed']}")
            solution = process_files_and_solve(quiz_data, solution["files_needed"])
            if not solution:
                results.append({"url": current_url, "error": "Failed with files"})
                break

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
            print("\n✅✅✅ CORRECT ✅✅✅")
        else:
            print(f"\n❌ WRONG: {submit_result.get('reason')}")

        current_url = submit_result.get("url")
        if not current_url:
            print("\n✓ Chain complete")
            break

    print(f"\n{'#'*60}")
    print(f"# FINISHED: {len(results)} quizzes in {time.time() - start_time:.1f}s")
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
    print(f"LLM Quiz Solver - Port {port}")
    print(f"Email: {YOUR_EMAIL}")
    print(f"AI: gpt-4o-mini via aipipe.org")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
