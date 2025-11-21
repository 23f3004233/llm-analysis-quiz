from flask import Flask, request, jsonify
import os
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import base64
from urllib.parse import urlparse
import traceback

from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = Flask(__name__)

YOUR_EMAIL = os.environ.get("STUDENT_EMAIL", "your-email@example.com")
YOUR_SECRET = os.environ.get("STUDENT_SECRET", "your-secret-string")

def get_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def fetch_quiz_page(url):
    driver = get_browser()
    try:
        driver.get(url)
        time.sleep(3)

        page_html = driver.page_source
        page_text = driver.find_element(By.TAG_NAME, "body").text

        return {
            "html": page_html,
            "text": page_text,
            "url": url
        }
    finally:
        driver.quit()

def download_file(url):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return base64.b64encode(response.content).decode('utf-8')
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None

def call_openai(prompt):
    """
    Wrapper for OpenAI gpt-4o-mini (free model)
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096,
            temperature=0
        )
        return resp.choices[0].message["content"]
    except Exception as e:
        print("OpenAI API error:", e)
        return None

def solve_quiz_with_openai(quiz_data):
    prompt = f"""
You are solving a data analysis quiz. Here is the quiz page:

{quiz_data['text']}

Your task:
1. Understand the question.
2. Detect if files must be downloaded.
3. Provide the quiz answer.
4. Output ONLY valid JSON like:

{{
    "submit_url": "the submission endpoint",
    "answer": your_answer,
    "files_needed": ["urls", "if", "any"]
}}

Quiz HTML (truncated):
{quiz_data['html'][:5000]}
"""

    response_text = call_openai(prompt)
    if not response_text:
        return None

    try:
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        json_str = response_text[start:end]
        return json.loads(json_str)
    except:
        return None

def process_files_and_solve(quiz_data, files_needed):
    file_contents = {}
    for file_url in files_needed:
        content = download_file(file_url)
        if content:
            file_contents[file_url] = content

    prompt = f"""
You are solving a data analysis quiz that requires file analysis.

Quiz content:
{quiz_data['text']}

Downloaded files (base64):
{json.dumps(list(file_contents.keys()))}

Instructions:
1. Decode files
2. Extract any needed data
3. Solve the quiz
4. Output JSON ONLY:

{{
    "submit_url": "the submission URL",
    "answer": final_answer
}}
"""

    response_text = call_openai(prompt)
    if not response_text:
        return None

    try:
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        return json.loads(response_text[start:end])
    except:
        return None

def submit_answer(submit_url, email, secret, quiz_url, answer):
    payload = {
        "email": email,
        "secret": secret,
        "url": quiz_url,
        "answer": answer
    }

    try:
        response = requests.post(submit_url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Error submitting answer: {e}")
        return {"correct": False, "reason": str(e)}

def solve_quiz_chain(initial_url, email, secret, max_time=180):
    start_time = time.time()
    current_url = initial_url
    results = []

    while current_url and (time.time() - start_time) < max_time:
        print(f"Solving quiz at: {current_url}")

        quiz_data = fetch_quiz_page(current_url)

        solution = solve_quiz_with_openai(quiz_data)
        if not solution:
            results.append({"url": current_url, "error": "Failed to parse quiz"})
            break

        if solution.get("files_needed"):
            solution = process_files_and_solve(quiz_data, solution["files_needed"])

        if not solution:
            results.append({"url": current_url, "error": "Failed file-solve"})
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

        current_url = submit_result.get("url")

        if not current_url:
            break

    return results

@app.route('/quiz', methods=['POST'])
def handle_quiz():
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
        print("Error in /quiz:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
