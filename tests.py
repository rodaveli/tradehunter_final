# tests.py

import requests
import config

def test_openrouter_connection(config):
    print("Testing OpenRouter API connection...")
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-website-url.com",
        "X-Title": "Your Application Name"
    }
    data = {
        "model": config.FAST_LLM,
        "messages": [{"role": "user", "content": "Hello, World!"}]
    }
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to OpenRouter API: {e}")
        return False

def test_config_loading():
    print("Testing config loading...")
    required_keys = ['OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'EXA_API_KEY', 'FAST_LLM', 'LONG_CONTEXT_LLM', 'SMART_LLM', 'RSS_FEEDS']
    for key in required_keys:
        if key not in globals():
            print(f"Error: {key} not found in config")
            return False
    print("All required config keys found")
    return True

def run_all_tests():

    tests = [
        ("Config Loading", test_config_loading),
        ("OpenRouter API Connection", lambda: test_openrouter_connection(config))
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\nRunning test: {test_name}")
        result = test_func()
        results.append((test_name, result))
        print(f"Test result: {'Passed' if result else 'Failed'}")

    print("\nTest Summary:")
    for test_name, result in results:
        print(f"{test_name}: {'Passed' if result else 'Failed'}")

if __name__ == "__main__":
    run_all_tests()