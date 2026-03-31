#!/usr/bin/env python3
"""Test the agent locally"""
import sys
sys.path.insert(0, r'E:\Wrapper Application')

from cyberai_agent import IntelligentAgent

agent = IntelligentAgent()
r = agent.run('Create a fibonacci calculator and run it')

print(f'Steps: {len(r)}')
for i, s in enumerate(r):
    result_str = str(s.get('result', {}))[:60]
    print(f'  {i+1}. {s["action"]}: {result_str}...')
