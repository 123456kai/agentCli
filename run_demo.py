#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, 'src')

os.environ['DEEPSEEK_API_KEY'] = 'sk-1bc630972983493d8caa78ad8ea11d3c'
os.environ['DEEPSEEK_MODEL'] = 'deepseek-v4-pro'

from pathlib import Path
from agentcli.runtime import build_runtime
from agentcli.llm.adapter import DeepSeekOpenAIAdapter
from agentcli.agent_loop import AgentLoop

print('=== Running agentcli with DeepSeek v4-pro ===\n')

try:
    runtime = build_runtime(Path.cwd())
    adapter = DeepSeekOpenAIAdapter(
        api_key=runtime.llm.api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )
    
    loop = AgentLoop(runtime=runtime, adapter=adapter)
    
    question = "What is the main purpose and architecture of this agentcli project?"
    print(f"Question: {question}\n")
    print("="*60)
    print("Result:")
    print("="*60 + "\n")
    
    answer = loop.run(question)
    print(answer)
    
    print("\n" + "="*60)
    print("✓ Query completed successfully")
    
except Exception as e:
    print(f'✗ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
