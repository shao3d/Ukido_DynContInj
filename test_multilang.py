import requests
import json

test_messages = [
    {"lang": "English", "msg": "What courses do you have?"},
    {"lang": "Ukrainian", "msg": "Які курси у вас є?"},
    {"lang": "German", "msg": "Welche Kurse haben Sie?"}
]

for test in test_messages:
    print(f"\n=== Testing {test['lang']} ===")
    print(f"Q: {test['msg']}")
    
    response = requests.post(
        'http://localhost:8000/chat',
        json={'user_id': f'test_lang_{test["lang"]}', 'message': test['msg']}
    )
    
    if response.status_code == 200:
        resp_json = response.json()
        resp_text = resp_json.get('response', '')[:150] + "..."
        print(f"A: {resp_text}")
        print(f"Intent: {resp_json.get('intent')}")
    else:
        print(f"Error: {response.status_code}")
