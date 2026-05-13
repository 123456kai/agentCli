#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from pathlib import Path
from agentcli.runtime import build_runtime
from agentcli.llm.adapter import DemoAdapter
from agentcli.agent_loop import AgentLoop

print('=== Testing agentcli Agent Loop Logic with Demo Adapter ===\n')

try:
    runtime = build_runtime(Path.cwd())
    adapter = DemoAdapter()  # Use demo instead of real API
    
    loop = AgentLoop(runtime=runtime, adapter=adapter)
    
    question = "What is the entry point?"
    print(f"Q: {question}\n")
    answer = loop.run(question)
    print(f"A:\n{answer}\n")
    print("✓ Agent loop works correctly!")
    
except Exception as e:
    print(f'✗ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
