"""
Gemini API Tester
Test your Gemini API key to verify it works
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

def test_gemini_api(api_key: str):
    """Test Gemini API with a simple request"""
    print("=" * 60)
    print("🧪 GEMINI API TESTER")
    print("=" * 60)
    
    try:
        import google.generativeai as genai
        
        print(f"\n🔑 API Key: {api_key[:20]}...{api_key[-10:]}")
        print("📡 Configuring Gemini...")
        
        genai.configure(api_key=api_key)
        
        print("🤖 Creating model instance...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        print("💬 Sending test prompt...")
        prompt = "Say 'Hello from Gemini!' if you can read this."
        
        response = model.generate_content(prompt)
        
        print("\n✅ SUCCESS! Gemini API is working!")
        print(f"📝 Response: {response.text}")
        print("\n" + "=" * 60)
        print("✅ Your Gemini API key is VALID and ACTIVE!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n" + "=" * 60)
        print("❌ Your Gemini API key is INVALID or SUSPENDED!")
        print("=" * 60)
        print("\n📋 To get a new API key:")
        print("   1. Go to: https://aistudio.google.com/app/apikey")
        print("   2. Click 'Create API Key'")
        print("   3. Copy the key")
        print("   4. Paste it in config/settings.yaml (line 10)")
        print("   5. Restart the backend")
        return False


if __name__ == "__main__":
    import yaml
    
    # Try to load from config
    config_path = Path("config/settings.yaml")
    
    if config_path.exists():
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        api_key = config['models']['deepfake'].get('gemini_api_key', '')
        
        if api_key and api_key != "YOUR_GEMINI_API_KEY_HERE":
            test_gemini_api(api_key)
        else:
            print("❌ No API key found in config/settings.yaml")
            print("   Please add your Gemini API key to line 10")
    else:
        print("❌ Config file not found: config/settings.yaml")
        
        # Allow manual testing
        if len(sys.argv) > 1:
            api_key = sys.argv[1]
            test_gemini_api(api_key)
        else:
            print("\nUsage: python test_gemini.py [API_KEY]")
