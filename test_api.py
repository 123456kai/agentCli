#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, 'src')

os.environ['DEEPSEEK_API_KEY'] = 'sk-1bc630972983493d8caa78ad8ea11d3c'
os.environ['DEEPSEEK_MODEL'] = 'deepseek-v4-pro'

from pathlib import Path
from agentcli.runtime import build_runtime
from agentcli.llm.adapter import DeepSeekOpenAIAdapter

print('=== Testing agentcli with DeepSeek v4-pro ===')
try:
    print('\n1. Building runtime...')
    runtime = build_runtime(Path.cwd())
    print(f'   API Key: {runtime.llm.api_key[:20]}...')
    print(f'   Model: {runtime.llm.model}')
    print(f'   Base URL: {runtime.llm.base_url}')
    
    print('\n2. Creating adapter...')
    adapter = DeepSeekOpenAIAdapter(
        api_key=runtime.llm.api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )
    print('   ✓ Adapter created')
    
    print('\n3. Making test API call...')
    messages = [
        {'role': 'user', 'content': 'Say "Hello from DeepSeek v4-pro"'}
    ]
    response = adapter.respond(messages, [])
    print(f'   Response type: {response["type"]}')
    print(f'   Content: {response["content"][:100]}...')
    print('\n✓ All tests passed!')
    
except Exception as e:
    print(f'\n✗ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
