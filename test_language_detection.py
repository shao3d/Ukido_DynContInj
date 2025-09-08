#!/usr/bin/env python3
"""
Quick test to verify language detection and streaming type.
"""

import httpx
import asyncio
import json

async def test_language(message, expected_lang):
    """Test if router correctly detects language."""
    print(f"\n{'='*50}")
    print(f"Testing: {message}")
    print(f"Expected language: {expected_lang}")
    print(f"{'='*50}")
    
    async with httpx.AsyncClient() as client:
        # Call the regular chat endpoint to see what router returns
        response = await client.post(
            "http://localhost:8000/chat",
            json={"user_id": f"test_{expected_lang}", "message": message}
        )
        
        if response.status_code == 200:
            data = response.json()
            detected = data.get("detected_language", "NOT FOUND")
            print(f"✅ Response received")
            print(f"📊 Detected language: {detected}")
            
            if detected == expected_lang:
                print(f"✅ Language detection CORRECT!")
            else:
                print(f"❌ Language detection WRONG! Expected: {expected_lang}, Got: {detected}")
                
            # Check if streaming would use the right branch
            if detected == "ru":
                print(f"→ Will use: PSEUDO-STREAMING (word by word)")
            else:
                print(f"→ Will use: REAL STREAMING (translation chunks)")
        else:
            print(f"❌ Error: {response.status_code}")

async def main():
    """Test all three languages."""
    print("🔍 Testing Language Detection After Router Fix")
    
    # Test cases
    tests = [
        ("Привет! Расскажите о школе", "ru"),  # Russian - no Ukrainian letters
        ("Привіт! Розкажіть про школу", "uk"),  # Ukrainian - has 'і'
        ("Hello! Tell me about school", "en"),  # English - all Latin
        ("Що це за школа?", "uk"),              # Ukrainian - has 'Щ'
        ("What is Ukido?", "en"),               # English
        ("Добрый день", "ru"),                  # Russian
    ]
    
    for message, expected_lang in tests:
        await test_language(message, expected_lang)
        await asyncio.sleep(1)  # Small delay between tests
    
    print("\n" + "="*50)
    print("✅ Language detection tests completed!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())