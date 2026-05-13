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
import time

print('=== Running agentcli with Detailed Logging ===\n', flush=True)

try:
    print('[1/3] Building runtime...', flush=True)
    runtime = build_runtime(Path.cwd())
    print('✓ Runtime built', flush=True)
    
    print('[2/3] Creating adapter...', flush=True)
    adapter = DeepSeekOpenAIAdapter(
        api_key=runtime.llm.api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )
    print('✓ Adapter created', flush=True)
    
    print('[3/3] Creating agent loop...', flush=True)
    loop = AgentLoop(runtime=runtime, adapter=adapter)
    print('✓ Agent loop created', flush=True)
    
    question = "Tell me about this project in 2-3 sentences"
    print(f'\n[4/4] Running query: "{question}"', flush=True)
    print(f'Max steps: {runtime.max_steps}', flush=True)
    print('-' * 60, flush=True)
    
    start = time.time()
    answer = loop.run(question)
    elapsed = time.time() - start
    
    print('-' * 60, flush=True)
    print(f'\nAnswer:\n{answer}', flush=True)
    print(f'\n✓ Completed in {elapsed:.1f}s', flush=True)
    
except KeyboardInterrupt:
    print('\n✗ Interrupted', flush=True)
except Exception as e:
    print(f'\n✗ Error: {type(e).__name__}: {e}', flush=True)
    import traceback
    traceback.print_exc()
