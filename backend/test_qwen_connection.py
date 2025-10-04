"""
Quick test script to verify Qwen API connection.
Run this after installing dependencies to validate the integration.

Usage:
    DASHSCOPE_API_KEY=sk-your-key python test_qwen_connection.py
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    import dashscope
    from dashscope import Generation

    print("✅ DashScope module imported successfully")
    print(f"   Version: {dashscope.__version__}")
except ImportError as e:
    print(f"❌ Failed to import dashscope: {e}")
    print("\nInstall with: pip install dashscope>=1.20.0")
    sys.exit(1)

# Get API key from environment
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    print("❌ DASHSCOPE_API_KEY environment variable not set")
    print("\nSet with: export DASHSCOPE_API_KEY=sk-your-key")
    sys.exit(1)

print(f"✅ API key found: {api_key[:10]}...")

# Set API key
dashscope.api_key = api_key

# Test simple chat
print("\n🧪 Testing Qwen API connection...")
try:
    response = Generation.call(
        model="qwen-vl-plus",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello' in one word."},
        ],
        result_format="message",
    )

    if response.status_code == 200:
        content = response.output.choices[0].message.content
        print("✅ API connection successful!")
        print("   Model: qwen-vl-plus")
        print(f"   Response: {content}")
        print(f"   Tokens used: {response.usage.total_tokens}")
    else:
        print(f"❌ API returned error: {response.code} - {response.message}")
        sys.exit(1)

except Exception as e:
    print(f"❌ API call failed: {e}")
    sys.exit(1)

print("\n✅ All checks passed! Qwen integration is ready.")
print("\nNext steps:")
print("1. Start backend: docker-compose up backend (or rebuild if needed)")
print("2. Test chat endpoint: curl -X POST http://localhost:8000/api/chat \\")
print("     -H 'Content-Type: application/json' \\")
print('     -d \'{"message": "Hello!"}\'')
