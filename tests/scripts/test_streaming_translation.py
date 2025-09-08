#!/usr/bin/env python3
"""
Test script for streaming translation functionality.
Tests both pseudo-streaming (Russian) and real streaming (Ukrainian/English).
"""

import asyncio
import aiohttp
import json
import time
from typing import AsyncGenerator
from urllib.parse import quote

# Test messages in different languages
TEST_MESSAGES = {
    "ru": "Привет! Расскажите о вашей школе soft skills для детей.",
    "uk": "Привіт! Розкажіть про вашу школу soft skills для дітей.",
    "en": "Hello! Tell me about your soft skills school for children."
}

async def stream_sse(url: str, params: dict) -> AsyncGenerator[str, None]:
    """Stream SSE responses from the server."""
    
    # Build query string
    query_params = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
    full_url = f"{url}?{query_params}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(full_url) as response:
            async for line in response.content:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith('data: '):
                    data = line_str[6:]  # Remove 'data: ' prefix
                    if data and data != '[DONE]':
                        yield data

async def test_language_streaming(lang_code: str, message: str):
    """Test streaming for a specific language."""
    print(f"\n{'='*60}")
    print(f"Testing {lang_code.upper()} language streaming")
    print(f"Message: {message}")
    print(f"{'='*60}")
    
    url = "http://localhost:8000/chat/stream"
    params = {
        "user_id": f"test_{lang_code}",
        "message": message
    }
    
    start_time = time.time()
    first_chunk_time = None
    chunks_received = 0
    full_response = []
    
    print("\n📡 Streaming response:")
    print("-" * 40)
    
    try:
        async for chunk in stream_sse(url, params):
            if first_chunk_time is None:
                first_chunk_time = time.time()
                time_to_first_chunk = first_chunk_time - start_time
                print(f"\n⏱️ Time to first chunk: {time_to_first_chunk:.2f}s")
                print("-" * 40)
                
            chunks_received += 1
            
            # Try to parse as JSON (for metadata)
            try:
                data = json.loads(chunk)
                if isinstance(data, dict):
                    # It's metadata
                    print(f"\n📊 Metadata received:")
                    print(f"  - Intent: {data.get('intent', 'N/A')}")
                    print(f"  - User Signal: {data.get('user_signal', 'N/A')}")
                    print(f"  - Detected Language: {data.get('detected_language', 'N/A')}")
                    print(f"  - Documents: {data.get('relevant_documents', [])}")
                else:
                    # It's text content
                    print(data, end='', flush=True)
                    full_response.append(data)
            except json.JSONDecodeError:
                # Raw text chunk
                print(chunk, end='', flush=True)
                full_response.append(chunk)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return
    
    total_time = time.time() - start_time
    
    print(f"\n\n{'='*60}")
    print(f"📈 Streaming Statistics for {lang_code.upper()}:")
    print(f"  - Total chunks received: {chunks_received}")
    print(f"  - Time to first chunk: {time_to_first_chunk:.2f}s" if first_chunk_time else "  - No chunks received")
    print(f"  - Total streaming time: {total_time:.2f}s")
    print(f"  - Full response length: {len(''.join(full_response))} characters")
    
    # Analysis based on language
    if lang_code == "ru":
        print(f"\n💡 Analysis: Russian (pseudo-streaming)")
        print(f"  - Expected: Fast first chunk (<3s), then word-by-word streaming")
        print(f"  - Actual: First chunk at {time_to_first_chunk:.2f}s")
        if time_to_first_chunk < 3:
            print(f"  ✅ Pseudo-streaming working correctly!")
        else:
            print(f"  ⚠️ Slower than expected for pseudo-streaming")
    else:
        print(f"\n💡 Analysis: {lang_code.upper()} (real translation streaming)")
        print(f"  - Expected: Gradual streaming as translation happens")
        print(f"  - Actual: First chunk at {time_to_first_chunk:.2f}s")
        if chunks_received > 10:
            print(f"  ✅ Real streaming working correctly! ({chunks_received} chunks)")
        else:
            print(f"  ⚠️ Low chunk count might indicate buffering issues")

async def test_protected_terms():
    """Test that protected terms (like 'Ukido', 'soft skills') are preserved during streaming."""
    print(f"\n{'='*60}")
    print(f"Testing PROTECTED terms handling in streaming")
    print(f"{'='*60}")
    
    message = "Tell me about Ukido's soft skills courses and Zoom classes"
    
    url = "http://localhost:8000/chat/stream"
    params = {
        "user_id": "test_protected_terms",
        "message": message
    }
    
    print(f"\n📝 Original message: {message}")
    print(f"🔒 Protected terms to check: Ukido, soft skills, Zoom")
    print("\n📡 Streaming response in English:")
    print("-" * 40)
    
    full_response = []
    
    try:
        async for chunk in stream_sse(url, params):
            try:
                data = json.loads(chunk)
                if not isinstance(data, dict):
                    print(data, end='', flush=True)
                    full_response.append(data)
            except json.JSONDecodeError:
                print(chunk, end='', flush=True)
                full_response.append(chunk)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return
    
    full_text = ''.join(full_response)
    
    print(f"\n\n{'='*60}")
    print(f"🔍 Checking protected terms in response:")
    
    terms_to_check = ['Ukido', 'soft skills', 'Zoom']
    all_preserved = True
    
    for term in terms_to_check:
        if term.lower() in full_text.lower():
            print(f"  ✅ '{term}' - preserved correctly")
        else:
            print(f"  ❌ '{term}' - NOT FOUND (might be incorrectly translated)")
            all_preserved = False
    
    if all_preserved:
        print(f"\n✅ All protected terms preserved during streaming!")
    else:
        print(f"\n⚠️ Some protected terms were not preserved")

async def main():
    """Run all streaming tests."""
    print("🚀 Starting Streaming Translation Tests")
    print("=" * 60)
    
    # Test 1: Russian (should use pseudo-streaming)
    await test_language_streaming("ru", TEST_MESSAGES["ru"])
    await asyncio.sleep(2)  # Pause between tests
    
    # Test 2: Ukrainian (should use real streaming)
    await test_language_streaming("uk", TEST_MESSAGES["uk"])
    await asyncio.sleep(2)
    
    # Test 3: English (should use real streaming)
    await test_language_streaming("en", TEST_MESSAGES["en"])
    await asyncio.sleep(2)
    
    # Test 4: Protected terms
    await test_protected_terms()
    
    print("\n" + "=" * 60)
    print("✅ All streaming tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())