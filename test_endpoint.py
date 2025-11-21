#!/usr/bin/env python3
"""
Test script for LLM Analysis Quiz endpoint
Usage: python test_endpoint.py
"""

import requests
import json
import sys
import os
from datetime import datetime

# Configuration
ENDPOINT_URL = os.environ.get("ENDPOINT_URL", "http://localhost:5000/quiz")
EMAIL = os.environ.get("STUDENT_EMAIL", "your-email@example.com")
SECRET = os.environ.get("STUDENT_SECRET", "your-secret")

def test_health_check(base_url):
    """Test if service is running"""
    try:
        health_url = base_url.replace('/quiz', '/health')
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_invalid_json(endpoint_url):
    """Test with invalid JSON"""
    try:
        response = requests.post(
            endpoint_url,
            data="not json",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code == 400:
            print("✅ Invalid JSON test passed (got 400)")
            return True
        else:
            print(f"❌ Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Invalid JSON test error: {e}")
        return False

def test_invalid_secret(endpoint_url, email):
    """Test with wrong secret"""
    try:
        response = requests.post(
            endpoint_url,
            json={
                "email": email,
                "secret": "wrong-secret",
                "url": "https://example.com"
            },
            timeout=10
        )
        if response.status_code == 403:
            print("✅ Invalid secret test passed (got 403)")
            return True
        else:
            print(f"❌ Expected 403, got {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Invalid secret test error: {e}")
        return False

def test_demo_quiz(endpoint_url, email, secret):
    """Test with demo quiz"""
    try:
        print("\n🎯 Testing demo quiz (this may take 30-60 seconds)...")
        
        response = requests.post(
            endpoint_url,
            json={
                "email": email,
                "secret": secret,
                "url": "https://tds-llm-analysis.s-anand.net/demo"
            },
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Demo quiz test passed")
            print(f"   Response: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Demo quiz failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except requests.Timeout:
        print("❌ Demo quiz timed out (>180s)")
        return False
    except Exception as e:
        print(f"❌ Demo quiz error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("LLM Analysis Quiz - Endpoint Testing")
    print("=" * 60)
    print(f"Endpoint: {ENDPOINT_URL}")
    print(f"Email: {EMAIL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Health check
    print("Test 1: Health Check")
    results.append(test_health_check(ENDPOINT_URL))
    print()
    
    # Test 2: Invalid JSON
    print("Test 2: Invalid JSON")
    results.append(test_invalid_json(ENDPOINT_URL))
    print()
    
    # Test 3: Invalid secret
    print("Test 3: Invalid Secret")
    results.append(test_invalid_secret(ENDPOINT_URL, EMAIL))
    print()
    
    # Test 4: Demo quiz (the real test)
    print("Test 4: Demo Quiz")
    results.append(test_demo_quiz(ENDPOINT_URL, EMAIL, SECRET))
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Your endpoint is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    # Check if environment variables are set
    if ENDPOINT_URL == "http://localhost:5000/quiz":
        print("⚠️  Using default localhost endpoint")
        print("   Set ENDPOINT_URL environment variable for deployed endpoint")
        print()
    
    if EMAIL == "your-email@example.com":
        print("❌ Please set STUDENT_EMAIL environment variable")
        sys.exit(1)
    
    if SECRET == "your-secret":
        print("❌ Please set STUDENT_SECRET environment variable")
        sys.exit(1)
    
    sys.exit(run_all_tests())
