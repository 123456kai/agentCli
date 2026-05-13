#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, 'src')

os.environ['DEEPSEEK_API_KEY'] = 'sk-1bc630972983493d8caa78ad8ea11d3c'
os.environ['DEEPSEEK_MODEL'] = 'deepseek-v4-pro'

from pathlib import Path
from agentcli.runtime import build_runtime
from agentcli.llm.adapter import DeepSeekOpenAIAdapter
import json

print('=== Testing DeepSeek API with Agent Tools ===\n')

try:
    runtime = build_runtime(Path.cwd())
    adapter = DeepSeekOpenAIAdapter(
        api_key=runtime.llm.api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )
    
    # Get tool definitions
    tools = [
        {
            "type": "function",
            "function": spec
        }
        for spec in [
            {
                "name": "search_files",
                "description": "Search files by pattern",
                "parameters": {
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                }
            }
        ]
    ]
    
    print("Step 1: Testing simple message without tools...")
    messages = [
        {'role': 'user', 'content': 'Say hello'}
    ]
    response = adapter.respond(messages, [])
    print(f"✓ Response: {response['content'][:50]}...\n")
    
    print("Step 2: Testing message with tools...")
    messages = [
        {'role': 'user', 'content': 'What files are in this project?'}
    ]
    print(f"Tools available: {len(tools)}")
    response = adapter.respond(messages, tools)
    print(f"✓ Response type: {response['type']}")
    if response['type'] == 'tool_call':
        print(f"  Tool: {response['tool_name']}")
        print(f"  Args: {response['arguments']}")
    else:
        print(f"  Content: {response['content'][:50]}...")
    
    print("\n✓ API integration works!")
    
except Exception as e:
    print(f'\n✗ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
