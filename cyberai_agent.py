"""
CyberAI Pro v3.0 - Intelligent Agent System
Actually reasons, plans, writes code, and executes like a real AI assistant
"""

import json
import os
import re
import sys
import time
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Rich for output
try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    RICH = True
except:
    RICH = False
    console = None

def log(msg: str, style: str = ""):
    if RICH and console:
        console.print(msg, style=style)
    else:
        print(msg)

# ============================================================================
# INTELLIGENT AGENT CORE
# ============================================================================

class IntelligentAgent:
    """
    AI Agent that actually reasons and acts intelligently.
    Can write code, create files, execute commands, and solve problems.
    """
    
    SYSTEM_PROMPT = """You are CyberAI Pro, an intelligent AI assistant with system access.

Your job is to help the user by thinking through problems and taking actions.

CAPABILITIES:
1. Write and execute Python code (PRIMARY - use this for coding tasks)
2. Create files with specific content
3. Run shell commands
4. Read files
5. Install packages

HOW TO RESPOND:
Always respond in this format:

THOUGHT: [Your reasoning about what needs to be done]

ACTION: [One of: write_code, write_file, run_command, read_file, install_package, finish]

INPUT: [The specific input for the action]

---
ACTION DETAILS:

write_code - PRIMARY for coding tasks. Write Python code and execute it.
Format: filename.py|code
Example: calculator.py|def add(a, b): return a + b
print(add(2, 3))

write_file - For creating text files (not code execution).
Format: filepath|content
Example: notes.txt|This is my note

run_command - Run shell commands.
Format: command
Example: ls -la

read_file - Read file content.
Format: filepath
Example: file.txt

install_package - Install Python packages.
Format: package_name
Example: requests

finish - When task is complete.
Format: Your final response to user

---
IMPORTANT:
- Use write_code for ALL coding tasks (it writes AND runs the code)
- Always think step by step
- If something fails, try a different approach
- Write complete, working code without placeholder comments
- Use proper format with | delimiter"""
    
    def __init__(self):
        self.memory: List[Dict] = []
        self.max_memory = 20
        self.setup_llm()
        log("[Agent] Intelligent Agent initialized", "green")
    
    def setup_llm(self):
        """Setup LLM providers."""
        self.providers = []
        
        # Groq
        groq_key = os.getenv('GROQ_API_KEY')
        if groq_key:
            try:
                from groq import Groq
                self.providers.append({
                    'name': 'Groq',
                    'client': Groq(api_key=groq_key),
                    'model': 'llama-3.3-70b-versatile'
                })
            except:
                pass
        
        # OpenRouter
        or_key = os.getenv('OPENROUTER_API_KEY')
        if or_key:
            try:
                from openai import OpenAI
                self.providers.append({
                    'name': 'OpenRouter',
                    'client': OpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=or_key
                    ),
                    'model': 'anthropic/claude-3.5-sonnet'
                })
            except:
                pass
    
    def ask_llm(self, prompt: str, max_tokens: int = 1000) -> str:
        """Query LLM with failover."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            *self.get_history(),
            {"role": "user", "content": prompt}
        ]
        
        for provider in self.providers:
            try:
                resp = provider['client'].chat.completions.create(
                    model=provider['model'],
                    messages=messages,
                    temperature=0.2,
                    max_tokens=1000,
                    timeout=15
                )
                return resp.choices[0].message.content
            except Exception as e:
                log(f"[LLM] {provider['name']} failed: {e}", "red")
                continue
        
        return "THOUGHT: All LLM providers failed\n\nACTION: finish\n\nINPUT: Error: AI service unavailable"
    
    def get_history(self) -> List[Dict]:
        """Get conversation history."""
        history = []
        for entry in self.memory[-10:]:
            history.append({"role": entry['role'], "content": entry['content']})
        return history
    
    def add_to_memory(self, role: str, content: str):
        """Add to memory."""
        self.memory.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        if len(self.memory) > self.max_memory:
            self.memory = self.memory[-self.max_memory:]
    
    def parse_response(self, response: str) -> Dict:
        """Parse LLM response into structured format."""
        thought = ""
        action = "finish"
        input_data = ""
        
        # Extract THOUGHT
        thought_match = re.search(r'THOUGHT:\s*(.+?)(?=\n\nACTION:|$)', response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
        
        # Extract ACTION
        action_match = re.search(r'ACTION:\s*(\w+)', response)
        if action_match:
            action = action_match.group(1).lower()
        
        # Extract INPUT
        input_match = re.search(r'INPUT:\s*(.+?)(?=\n\n|$)', response, re.DOTALL)
        if input_match:
            input_data = input_match.group(1).strip()
        
        return {
            'thought': thought,
            'action': action,
            'input': input_data,
            'raw': response
        }
    
    def execute_action(self, action: str, input_data: str) -> Dict:
        """Execute the chosen action."""
        try:
            if action == 'write_code':
                return self._write_code(input_data)
            elif action == 'run_command':
                return self._run_command(input_data)
            elif action == 'write_file':
                return self._write_file(input_data)
            elif action == 'read_file':
                return self._read_file(input_data)
            elif action == 'install_package':
                return self._install_package(input_data)
            elif action == 'finish':
                return {'success': True, 'result': input_data, 'type': 'finish'}
            else:
                return {'success': False, 'error': f'Unknown action: {action}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _write_code(self, code_input: str) -> Dict:
        """Write Python code to a file and execute it."""
        try:
            # Parse filename and code
            if '|' in code_input:
                filepath, code = code_input.split('|', 1)
            else:
                # Auto-generate filename
                filepath = f"generated_{int(time.time())}.py"
                code = code_input
            
            filepath = filepath.strip()
            code = code.strip()
            
            # Write file
            Path(filepath).write_text(code)
            
            # Execute the code
            result = subprocess.run(
                ['python', filepath],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            return {
                'success': result.returncode == 0,
                'result': f"Created: {filepath}\n\nOutput:\n{output[:500]}",
                'filepath': filepath,
                'output': output
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _run_command(self, cmd: str) -> Dict:
        """Run shell command."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            return {
                'success': result.returncode == 0,
                'result': output[:1000] if output else "Command executed (no output)"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _write_file(self, file_input: str) -> Dict:
        """Write content to file."""
        try:
            if '|' not in file_input:
                return {'success': False, 'error': 'Format: filepath|content'}
            
            filepath, content = file_input.split('|', 1)
            Path(filepath.strip()).write_text(content)
            return {'success': True, 'result': f"Written: {filepath}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _read_file(self, filepath: str) -> Dict:
        """Read file content."""
        try:
            content = Path(filepath).read_text()
            return {'success': True, 'result': content[:2000]}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _install_package(self, package: str) -> Dict:
        """Install Python package."""
        try:
            result = subprocess.run(
                ['pip', 'install', package],
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                'success': result.returncode == 0,
                'result': f"Installed {package}"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def run(self, goal: str, max_steps: int = 10) -> List[Dict]:
        """Run the agent loop on a goal."""
        log(f"\n[Agent] Goal: {goal}", "cyan bold")
        
        self.add_to_memory('user', goal)
        results = []
        created_files = set()  # Track created files
        
        for step in range(max_steps):
            log(f"\n[Step {step + 1}] Thinking...", "dim")
            
            # Ask LLM what to do
            prompt = f"""Current task: {goal}

Previous actions and results:
{self._format_history()}

Already created files: {', '.join(created_files) if created_files else 'None'}

What should I do next? 
- If you already created a file, use run_command to execute it
- If the task is complete, use finish

Respond in the required format."""
            
            llm_response = self.ask_llm(prompt, max_tokens=800)
            parsed = self.parse_response(llm_response)
            
            thought = parsed['thought']
            action = parsed['action']
            input_data = parsed['input']
            
            # Prevent infinite loops - if same action/input repeated
            if results and action == results[-1]['action'] and input_data == results[-1]['input']:
                log(f"[Warning] Repeated action detected, forcing finish", "yellow")
                action = 'finish'
                input_data = 'Task completed with the steps taken.'
            
            # Track created files
            if action == 'write_code' or action == 'write_file':
                if '|' in input_data:
                    filepath = input_data.split('|', 1)[0].strip()
                    created_files.add(filepath)
            
            log(f"[Thought] {thought[:80]}...", "blue")
            log(f"[Action] {action}: {input_data[:60]}...", "yellow")
            
            # Execute
            result = self.execute_action(action, input_data)
            
            # Store
            self.add_to_memory('assistant', f"THOUGHT: {thought}\nACTION: {action}\nINPUT: {input_data}")
            self.add_to_memory('system', f"Result: {result.get('result', result.get('error', 'Unknown'))}")
            
            results.append({
                'step': step,
                'thought': thought,
                'action': action,
                'input': input_data,
                'result': result
            })
            
            if action == 'finish':
                log(f"\n[Complete] {input_data}", "green bold")
                break
        
        return results
    
    def _format_history(self) -> str:
        """Format recent history for LLM."""
        recent = self.memory[-6:]
        formatted = []
        for entry in recent:
            role = entry['role']
            content = entry['content'][:200]
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

# Backwards compatibility
CyberAgent = IntelligentAgent

if __name__ == "__main__":
    # Test
    agent = IntelligentAgent()
    results = agent.run("Create a Python script that calculates fibonacci numbers and run it")
    print(f"\nCompleted {len(results)} steps")
