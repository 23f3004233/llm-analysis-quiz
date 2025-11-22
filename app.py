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

from openai import OpenAI

# AI Pipe Configuration
client = OpenAI(
    api_key=os.environ.get("AIPIPE_TOKEN"),  # Changed from OPENAI_API_KEY
    base_url="https://aipipe.org/openai/v1"   # Added base_url
)

app = Flask(__name__)

YOUR_EMAIL = os.environ.get("STUDENT_EMAIL", "your-email@example.com")
YOUR_SECRET = os.environ.get("STUDENT_SECRET", "your-secret-string")

def get_browser():
    """Initialize Chrome with better error handling"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Find Chrome binary
    chrome_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser", 
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable"
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_options.binary_location = path
            print(f"✓ Using Chrome at: {path}")
            break
    else:
        print("⚠️  Chrome binary not found in standard locations")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("✓ Chrome initialized successfully")
        return driver
    except Exception as e:
        print(f"✗ Chrome initialization failed: {e}")
        traceback.print_exc()
        raise

def fetch_quiz_page(url):
    """Fetch quiz page with detailed logging"""
    print(f"\n{'='*60}")
    print(f"Fetching quiz page: {url}")
    print(f"{'='*60}")
    
    driver = None
    try:
        driver = get_browser()
        print("Loading page...")
        driver.get(url)
        
        # Wait for page to load
        print("Waiting for page to render...")
        time.sleep(5)
        
        page_html = driver.page_source
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        print(f"✓ Page loaded successfully")
        print(f"  HTML length: {len(page_html)} chars")
        print(f"  Text length: {len(page_text)} chars")
        print(f"\nPage text preview (first 500 chars):")
        print("-" * 60)
        print(page_text[:500])
        print("-" * 60)
        
        return {
            "html": page_html,
            "text": page_text,
            "url": url
        }
    except Exception as e:
        print(f"✗ Error fetching page: {e}")
        traceback.print_exc()
        return {
            "html": "",
            "text": f"Error: {str(e)}",
            "url": url
        }
    finally:
        if driver:
            try:
                driver.quit()
                print("✓ Browser closed")
            except:
                pass

def download_file(url):
    """Download file with logging"""
    print(f"\nDownloading file: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = base64.b64encode(response.content).decode('utf-8')
        print(f"✓ File downloaded: {len(content)} chars (base64)")
        return content
    except Exception as e:
        print(f"✗ Download failed: {e}")
        return None

def call_ai(prompt, max_retries=2):
    """Call AI Pipe with retry and logging"""
    for attempt in range(max_retries):
        try:
            print(f"\nCalling AI Pipe (attempt {attempt + 1}/{max_retries})...")
            print(f"Prompt length: {len(prompt)} chars")
            
            resp = client.chat.completions.create(
                model="gpt-4o-mini",  # Free model via AI Pipe
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0
            )
            
            response_text = resp.choices[0].message.content
            print(f"✓ AI response received: {len(response_text)} chars")
            print(f"\nAI response preview:")
            print("-" * 60)
            print(response_text[:500])
            print("-" * 60)
            
            return response_text
            
        except Exception as e:
            print(f"✗ AI Pipe error (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                traceback.print_exc()
                return None
            time.sleep(2)
    
    return None

def solve_quiz_with_ai(quiz_data):
    """Solve quiz with detailed logging"""
    print(f"\n{'='*60}")
    print("SOLVING QUIZ WITH AI")
    print(f"{'='*60}")
    
    prompt = f"""You are solving a data analysis quiz. Here is the quiz page content:

PAGE TEXT:
{quiz_data['text']}

Your task:
1. Read and understand the question carefully
2. Identify if any files need to be downloaded (look for links or URLs)
3. Extract the submission URL (where to POST the answer)
4. Determine the answer

You MUST respond with ONLY a valid JSON object (no markdown, no explanation, no code blocks):

{{
    "submit_url": "the exact URL where the answer should be posted",
    "answer": your_answer_here,
    "files_needed": ["list", "of", "file", "URLs", "if", "any"]
}}

Rules:
- If no files are needed, make files_needed an empty array: []
- The answer can be a number, string, boolean, or object
- Make sure submit_url is the exact URL from the page
- DO NOT wrap your response in ```json ``` or any markdown

PAGE HTML (truncated):
{quiz_data['html'][:3000]}
"""

    response_text = call_ai(prompt)
    if not response_text:
        print("✗ No response from AI")
        return None

    try:
        # Clean response
        print("\nParsing AI response...")
        response_text = response_text.strip()
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        # Find JSON
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start == -1 or end == 0:
            print(f"✗ No JSON found in response")
            print(f"Full response: {response_text}")
            return None
        
        json_str = response_text[start:end]
        result = json.loads(json_str)
        
        print("✓ Successfully parsed JSON:")
        print(json.dumps(result, indent=2))
        
        # Validate required fields
        if 'submit_url' not in result:
            print("✗ Missing submit_url in response")
            return None
        
        if 'answer' not in result and not result.get('files_needed'):
            print("✗ Missing both answer and files_needed")
            return None
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON parse error: {e}")
        print(f"Attempted to parse: {json_str if 'json_str' in locals() else response_text}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        traceback.print_exc()
        return None

def process_files_and_solve(quiz_data, files_needed):
    """Process files and solve"""
    print(f"\n{'='*60}")
    print(f"PROCESSING FILES: {len(files_needed)} file(s)")
    print(f"{'='*60}")
    
    file_contents = {}
    for file_url in files_needed:
        content = download_file(file_url)
        if content:
            file_contents[file_url] = content

    if not file_contents:
        print("✗ No files downloaded successfully")
        return None

    prompt = f"""You are analyzing downloaded files to solve a data quiz.

ORIGINAL QUESTION:
{quiz_data['text']}

DOWNLOADED FILES:
{json.dumps(list(file_contents.keys()))}

Instructions:
1. The files are base64 encoded
2. Decode and analyze them
3. Answer the question precisely
4. Output ONLY valid JSON (no markdown):

{{
    "submit_url": "the submission URL from the original page",
    "answer": your_final_answer
}}

The answer should match what the question asks for (number, string, etc.)
"""

    response_text = call_ai(prompt)
    if not response_text:
        return None

    try:
        response_text = response_text.strip().replace('```json', '').replace('```', '').strip()
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start == -1 or end == 0:
            return None
        return json.loads(response_text[start:end])
    except Exception as e:
        print(f"✗ Error parsing file-solve response: {e}")
        return None

def submit_answer(submit_url, email, secret, quiz_url, answer):
    """Submit answer with logging"""
    print(f"\n{'='*60}")
    print("SUBMITTING ANSWER")
    print(f"{'='*60}")
    
    payload = {
        "email": email,
        "secret": secret,
        "url": quiz_url,
        "answer": answer
    }
    
    print(f"Submit URL: {submit_url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(submit_url, json=payload, timeout=30)
        result = response.json()
        
        print(f"Response Status: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2)}")
        
        return result
    except Exception as e:
        print(f"✗ Submission error: {e}")
        traceback.print_exc()
        return {"correct": False, "reason": str(e)}

def solve_quiz_chain(initial_url, email, secret, max_time=180):
    """Solve quiz chain"""
    print(f"\n{'#'*60}")
    print(f"# STARTING QUIZ CHAIN")
    print(f"# Initial URL: {initial_url}")
    print(f"# Max time: {max_time}s")
    print(f"{'#'*60}\n")
    
    start_time = time.time()
    current_url = initial_url
    results = []

    while current_url and (time.time() - start_time) < max_time:
        print(f"\n\n{'*'*60}")
        print(f"Quiz {len(results) + 1}: {current_url}")
        print(f"Elapsed time: {time.time() - start_time:.1f}s / {max_time}s")
        print(f"{'*'*60}")

        # Fetch quiz
        quiz_data = fetch_quiz_page(current_url)
        
        # Solve
        solution = solve_quiz_with_ai(quiz_data)
        if not solution:
            print("✗ Failed to get solution from AI")
            results.append({"url": current_url, "error": "Failed to parse quiz"})
            break

        # Process files if needed
        if solution.get("files_needed"):
            print(f"\n📎 Files needed: {solution['files_needed']}")
            solution = process_files_and_solve(quiz_data, solution["files_needed"])
            if not solution:
                results.append({"url": current_url, "error": "Failed to solve with files"})
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

        # Check result
        if submit_result.get("correct"):
            print("\n✓✓✓ CORRECT ANSWER ✓✓✓")
        else:
            print(f"\n✗✗✗ WRONG ANSWER ✗✗✗")
            print(f"Reason: {submit_result.get('reason')}")

        # Next URL
        current_url = submit_result.get("url")
        if not current_url:
            print("\n✓ Quiz chain complete!")
            break

    print(f"\n{'#'*60}")
    print(f"# QUIZ CHAIN FINISHED")
    print(f"# Total quizzes: {len(results)}")
    print(f"# Total time: {time.time() - start_time:.1f}s")
    print(f"{'#'*60}\n")

    return results

@app.route('/quiz', methods=['POST'])
def handle_quiz():
    """Main quiz endpoint"""
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

        print(f"\n{'='*60}")
        print(f"NEW REQUEST RECEIVED")
        print(f"Email: {data.get('email')}")
        print(f"URL: {quiz_url}")
        print(f"{'='*60}")

        results = solve_quiz_chain(quiz_url, YOUR_EMAIL, YOUR_SECRET)

        return jsonify({"status": "completed", "results": results}), 200

    except Exception as e:
        print(f"\n✗✗✗ ERROR IN /quiz ✗✗✗")
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({"status": "healthy"}), 200

@app.route('/', methods=['GET'])
def index():
    """Index"""
    return jsonify({
        "service": "LLM Quiz Solver",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "quiz": "/quiz (POST)"
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*60}")
    print(f"Starting LLM Quiz Solver on port {port}")
    print(f"Email: {YOUR_EMAIL}")
    print(f"Secret: {'*' * len(YOUR_SECRET)}")
    print(f"AI Pipe: Using gpt-4o-mini via aipipe.org")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
