#!/usr/bin/env python3
"""
Test script to verify PROTECTED tags fix for streaming translation.
Tests that terms like Ukido, soft skills, Zoom are preserved without nested tags.
"""

import httpx
import asyncio
import json

async def test_streaming_translation(message, expected_lang, description):
    """Test streaming translation with focus on PROTECTED terms."""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"📝 Message: {message}")
    print(f"🌐 Expected language: {expected_lang}")
    print(f"{'='*60}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Call SSE endpoint
        response_chunks = []
        try:
            async with client.stream(
                'GET',
                'http://localhost:8000/chat/stream',
                params={'user_id': f'test_{expected_lang}', 'message': message}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        if data and data != '[DONE]':
                            response_chunks.append(data)
                            
        except Exception as e:
            print(f"❌ Error: {e}")
            return
            
        # Combine all chunks
        full_response = ''.join(response_chunks)
        print(f"\n📤 Full response ({len(response_chunks)} chunks):")
        print(full_response)
        
        # Check for nested PROTECTED tags
        if '[PROTECTED]' in full_response or '[/PROTECTED]' in full_response:
            print(f"\n❌ FOUND PROTECTED TAGS! This should not happen!")
            # Count occurrences
            open_tags = full_response.count('[PROTECTED]')
            close_tags = full_response.count('[/PROTECTED]')
            print(f"   Open tags: {open_tags}")
            print(f"   Close tags: {close_tags}")
        else:
            print(f"\n✅ No PROTECTED tags found - fix is working!")
            
        # Check if key terms are preserved
        terms_to_check = ['Ukido', 'soft skills', 'Zoom', 'online']
        preserved = []
        for term in terms_to_check:
            if term.lower() in full_response.lower():
                preserved.append(term)
                
        if preserved:
            print(f"✅ Preserved terms: {', '.join(preserved)}")
        else:
            print(f"⚠️  No protected terms found in response")

async def main():
    """Test all languages with focus on PROTECTED terms."""
    print("🔬 Testing PROTECTED Tags Fix in Streaming Translation")
    print("Goal: Verify that terms are preserved WITHOUT nested tags")
    
    # Test cases with messages containing protected terms
    tests = [
        (
            "Расскажите про Ukido и soft skills, как проходят занятия в Zoom?",
            "uk",
            "Ukrainian with multiple protected terms"
        ),
        (
            "What is Ukido? Do you teach soft skills online via Zoom?",
            "en",
            "English (should pass through without translation)"
        ),
        (
            "Привіт! Що таке Ukido? Ви навчаєте soft skills через Zoom?",
            "uk",
            "Ukrainian detection and translation"
        ),
        (
            "Сколько стоит обучение soft skills в школе Ukido? Занятия online?",
            "ru",
            "Russian (no translation needed)"
        ),
    ]
    
    for message, expected_lang, description in tests:
        await test_streaming_translation(message, expected_lang, description)
        await asyncio.sleep(2)  # Delay between tests
    
    print("\n" + "="*60)
    print("✅ Testing completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())