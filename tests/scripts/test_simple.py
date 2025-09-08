#!/usr/bin/env python3
"""Simple test for multilingual functionality"""

import httpx
import json
import asyncio

async def test_single():
    """Test single Ukrainian request"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test Ukrainian
        print("🔍 Testing Ukrainian language detection...")
        response = await client.post(
            "http://localhost:8000/chat",
            json={
                "user_id": "test_uk",
                "message": "Привіт! Розкажіть про школу"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📝 Detected language: {result.get('detected_language', 'unknown')}")
            print(f"📝 Intent: {result.get('intent', 'unknown')}")
            print(f"📝 User signal: {result.get('user_signal', 'unknown')}")
            print(f"📝 Response (first 200 chars): {result.get('response', '')[:200]}...")
            
            # Check metadata
            if 'metadata' in result:
                print(f"📝 Metadata: {json.dumps(result['metadata'], indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
if __name__ == "__main__":
    asyncio.run(test_single())