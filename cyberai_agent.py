"""
CyberAI Pro - Core Agent System
Proper agent architecture with loop, tools, and memory
"""

import json
import os
import re
import sys
import time
import threading
import queue
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Rich for beautiful terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.status import Status
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None

def log(msg: str, style: str = ""):
    """Log with Rich if available."""
    if RICH_AVAILABLE and console:
        console.print(msg, style=style)
    else:
        print(msg)

# ============================================================================
# MEMORY SYSTEM
# ============================================================================

@dataclass
class MemoryEntry:
    """Single memory entry."""
    timestamp: str
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    metadata: Dict = field(default_factory=dict)

class MemoryManager:
    """Persistent memory for the agent."""
    
    def __init__(self, memory_file: str = "cyberai_memory.json"):
        self.memory_file = Path(memory_file)
        self.short_term: List[MemoryEntry] = []  # Last N interactions
        self.long_term: List[MemoryEntry] = []   # Important facts
        self.max_short_term = 20
        self.max_long_term = 100
        self._load()
    
    def _load(self):
        """Load memory from disk."""
        if self.memory_file.exists():
            try:
                data = json.loads(self.memory_file.read_text())
                self.short_term = [MemoryEntry(**e) for e in data.get('short_term', [])]
                self.long_term = [MemoryEntry(**e) for e in data.get('long_term', [])]
                log(f"[Memory] Loaded {len(self.short_term)} short-term, {len(self.long_term)} long-term")
            except Exception as e:
                log(f"[Memory] Load failed: {e}", "red")
    
    def _save(self):
        """Save memory to disk."""
        try:
            data = {
                'short_term': [vars(e) for e in self.short_term],
                'long_term': [vars(e) for e in self.long_term]
            }
            self.memory_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log(f"[Memory] Save failed: {e}", "red")
    
    def add(self, role: str, content: str, metadata: Dict = None):
        """Add entry to short-term memory."""
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.short_term.append(entry)
        
        # Trim if needed
        if len(self.short_term) > self.max_short_term:
            self.short_term = self.short_term[-self.max_short_term:]
        
        self._save()
    
    def get_context(self, n_recent: int = 10) -> str:
        """Get recent context for LLM."""
        recent = self.short_term[-n_recent:]
        return "\n".join([
            f"[{e.role}] {e.content[:200]}" 
            for e in recent
        ])
    
    def get_formatted_history(self, n: int = 10) -> List[Dict]:
        """Get history in OpenAI format."""
        return [
            {"role": e.role if e.role in ['user', 'assistant', 'system'] else 'user', 
             "content": e.content}
            for e in self.short_term[-n:]
        ]

# ============================================================================
# LLM INTERFACE with Retry Logic
# ============================================================================

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai
import httpx

class LLMEngine:
    """Robust LLM interface with failover and retries."""
    
    SYSTEM_PROMPT = """You are CyberAI Pro, an autonomous AI agent with system control.

CRITICAL: You MUST respond with valid JSON only. No markdown, no extra text.

Response format:
{
  "thought": "Your reasoning here",
  "action": "tool_name or 'finish'",
  "input": "tool parameters",
  "response": "What to tell the user"
}

Available tools:
- run_command: Execute shell command
- read_file: Read file contents
- write_file: Write to file
- list_directory: List files in directory
- open_browser: Open URL in browser
- web_search: Search the web
- finish: Task is complete

Rules:
1. ALWAYS use JSON format
2. If task needs multiple steps, plan them in thought
3. Execute tools one at a time
4. Use 'finish' when done
5. Be concise and direct"""

    def __init__(self):
        self.providers = []
        self._init_providers()
        self.current_provider = 0
    
    def _init_providers(self):
        """Initialize all available providers."""
        # Groq
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            self.providers.append({
                "name": "groq",
                "client": openai.OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1"),
                "model": "llama-3.3-70b-versatile",
                "timeout": 15
            })
        
        # OpenRouter
        or_key = os.getenv("OPENROUTER_API_KEY", "")
        if or_key:
            self.providers.append({
                "name": "openrouter",
                "client": openai.OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1"),
                "model": "anthropic/claude-3.5-sonnet",
                "timeout": 20
            })
        
        log(f"[LLM] Initialized {len(self.providers)} providers", "green")
    
    def ask(self, messages: List[Dict], max_tokens: int = 2000) -> str:
        """Ask LLM with automatic failover."""
        for i, provider in enumerate(self.providers):
            try:
                log(f"[LLM] Trying {provider['name']}...", "dim")
                
                response = provider["client"].chat.completions.create(
                    model=provider["model"],
                    messages=[{"role": "system", "content": self.SYSTEM_PROMPT}] + messages,
                    max_tokens=max_tokens,
                    temperature=0.3,
                    timeout=provider["timeout"]
                )
                
                content = response.choices[0].message.content
                log(f"[LLM] {provider['name']} success", "green")
                return content
                
            except Exception as e:
                log(f"[LLM] {provider['name']} failed: {e}", "red")
                continue
        
        return json.dumps({
            "thought": "All providers failed",
            "action": "finish",
            "input": "",
            "response": "Error: All AI providers failed. Check API keys."
        })
    
    def parse_response(self, response: str) -> Dict:
        """Parse LLM response to JSON."""
        try:
            # Try to find JSON in response
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Return as plain text response
            return {
                "thought": "Could not parse JSON",
                "action": "finish",
                "input": "",
                "response": response
            }

# ============================================================================
# TOOL SYSTEM
# ============================================================================

class ToolRegistry:
    """Registry of available tools."""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.register_defaults()
    
    def register(self, name: str, func: Callable):
        """Register a tool."""
        self.tools[name] = func
    
    def execute(self, name: str, input_data: str) -> Dict:
        """Execute a tool by name."""
        if name not in self.tools:
            return {"success": False, "error": f"Unknown tool: {name}"}
        
        try:
            result = self.tools[name](input_data)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def register_defaults(self):
        """Register default tools."""
        self.register("run_command", self._run_command)
        self.register("read_file", self._read_file)
        self.register("write_file", self._write_file)
        self.register("list_directory", self._list_directory)
        self.register("open_browser", self._open_browser)
        self.register("finish", lambda x: {"status": "complete", "message": x})
    
    def _run_command(self, cmd: str) -> str:
        """Execute shell command."""
        import subprocess
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        return output[:1000] if output else "Command executed (no output)"
    
    def _read_file(self, path: str) -> str:
        """Read file contents."""
        try:
            return Path(path).read_text()[:5000]
        except Exception as e:
            return f"Error: {e}"
    
    def _write_file(self, params: str) -> str:
        """Write to file. Format: path|content"""
        try:
            parts = params.split("|", 1)
            if len(parts) == 2:
                path, content = parts
            else:
                # Try to parse as JSON
                data = json.loads(params)
                path = data.get("path", "")
                content = data.get("content", "")
            
            Path(path).write_text(content)
            return f"File written: {path}"
        except Exception as e:
            return f"Error: {e}"
    
    def _list_directory(self, path: str) -> str:
        """List directory contents."""
        try:
            p = Path(path or ".")
            files = [f.name for f in p.iterdir()]
            return "\n".join(files[:50])
        except Exception as e:
            return f"Error: {e}"
    
    def _open_browser(self, url: str) -> str:
        """Open URL in browser."""
        import webbrowser
        webbrowser.open(url)
        return f"Opened: {url}"

# ============================================================================
# AGENT CORE
# ============================================================================

class CyberAgent:
    """Autonomous AI Agent with proper loop architecture."""
    
    def __init__(self):
        self.memory = MemoryManager()
        self.llm = LLMEngine()
        self.tools = ToolRegistry()
        self.running = False
        self.max_iterations = 10  # Prevent infinite loops
        
        log("[Agent] Initialized", "green")
    
    def run(self, goal: str) -> List[Dict]:
        """Execute agent loop for a goal."""
        self.running = True
        results = []
        
        # Add user goal to memory
        self.memory.add("user", goal, {"type": "goal"})
        
        log(f"\n[Agent] Goal: {goal}", "cyan bold")
        
        for iteration in range(self.max_iterations):
            if not self.running:
                break
            
            log(f"\n[Agent] Step {iteration + 1}/{self.max_iterations}", "dim")
            
            # Get history context
            history = self.memory.get_formatted_history(15)
            
            # Ask LLM for next action
            messages = history + [{"role": "user", "content": f"Current goal: {goal}\nWhat should I do next?"}]
            
            try:
                llm_response = self.llm.ask(messages, max_tokens=1500)
                parsed = self.llm.parse_response(llm_response)
            except Exception as e:
                log(f"[Agent] LLM error: {e}", "red")
                break
            
            # Log the thought
            thought = parsed.get("thought", "No thought provided")
            log(f"[Thought] {thought[:100]}...", "dim")
            
            action = parsed.get("action", "finish")
            action_input = parsed.get("input", "")
            response_text = parsed.get("response", "")
            
            # Store in memory
            self.memory.add("assistant", json.dumps(parsed), {"type": "action"})
            
            # Execute if not finish
            if action == "finish":
                log(f"[Agent] Complete: {response_text}", "green bold")
                results.append({
                    "step": iteration,
                    "action": "finish",
                    "result": response_text
                })
                break
            
            # Execute tool
            log(f"[Tool] {action}: {action_input[:50]}...", "yellow")
            tool_result = self.tools.execute(action, action_input)
            
            result_summary = tool_result.get("result", tool_result.get("error", ""))[:200]
            log(f"[Result] {result_summary}...", "blue" if tool_result["success"] else "red")
            
            # Store result
            self.memory.add("system", json.dumps(tool_result), {"type": "result"})
            
            results.append({
                "step": iteration,
                "action": action,
                "input": action_input,
                "result": tool_result
            })
        
        return results
    
    def stop(self):
        """Stop the agent loop."""
        self.running = False

# ============================================================================
# MAIN ENTRY
# ============================================================================

if __name__ == "__main__":
    # Test the agent
    agent = CyberAgent()
    
    # Example goals
    goals = [
        "Create a file called test.txt with 'Hello World'",
        "List files in current directory",
        "What is 2+2?"
    ]
    
    for goal in goals:
        results = agent.run(goal)
        print(f"\n{'='*50}")
