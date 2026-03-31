#!/usr/bin/env python3
"""
CyberAI Pro - Summonable AI Assistant with Root Control

Features:
- Global hotkey summon (Ctrl+Shift+A)
- System tray icon for quick access
- Overlay UI for instant interaction
- Full file editing capabilities (including self-modification)
- Editor integration (VS Code, etc.)
- Root-level system control
- Background service mode

Usage:
    python cyberai_pro.py           # Start service
    python cyberai_pro.py --cli     # CLI mode only
    python cyberai_pro.py --once    # Single query then exit
"""

import os
import sys
import json
import subprocess
import time
import threading
import queue
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime

# Windows-specific imports for hotkeys and tray
try:
    import win32gui
    import win32con
    import win32api
    import win32clipboard
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False
    print("[Warning] Windows APIs not available. Install: pip install pywin32")

try:
    from openai import OpenAI
except ImportError:
    print("[ERROR] pip install openai")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to import tkinter for overlay UI
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# Try to import system tray
try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


@dataclass
class Task:
    """Task for the AI to execute."""
    id: str
    type: str  # "chat", "edit_file", "run_command", "analyze"
    content: str
    callback: Optional[Callable] = None
    auto_execute: bool = False


class RootController:
    """
    Root-level system controller with full access.
    """
    
    def __init__(self):
        self.command_history = []
        self.file_history = []
    
    def execute_shell(self, command: str, elevated: bool = False, timeout: int = 60) -> Dict:
        """Execute shell command with optional elevation."""
        print(f"[Root] Executing: {command[:80]}...")
        
        try:
            if elevated and sys.platform == "win32":
                # Use PowerShell with elevation for Windows
                command = f'powershell -Command "Start-Process cmd -ArgumentList \'/c {command}\' -Verb runAs -Wait"'
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": command,
                "timestamp": datetime.now().isoformat()
            }
            
            self.command_history.append(output)
            return output
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout", "command": command}
        except Exception as e:
            return {"success": False, "error": str(e), "command": command}
    
    def read_file(self, filepath: str) -> Dict:
        """Read any file."""
        try:
            path = Path(filepath)
            if not path.exists():
                return {"success": False, "error": "File not found"}
            
            content = path.read_text(encoding="utf-8", errors="replace")
            return {
                "success": True,
                "content": content,
                "path": str(path.absolute()),
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def write_file(self, filepath: str, content: str) -> Dict:
        """Write to any file (creates if doesn't exist)."""
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Backup if file exists
            if path.exists():
                backup = path.with_suffix(path.suffix + ".backup")
                backup.write_text(path.read_text(), encoding="utf-8")
            
            path.write_text(content, encoding="utf-8")
            
            result = {
                "success": True,
                "path": str(path.absolute()),
                "size": len(content)
            }
            
            self.file_history.append(result)
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def edit_file(self, filepath: str, search: str, replace: str) -> Dict:
        """Edit specific part of a file."""
        try:
            path = Path(filepath)
            if not path.exists():
                return {"success": False, "error": "File not found"}
            
            content = path.read_text(encoding="utf-8", errors="replace")
            
            if search not in content:
                return {"success": False, "error": "Search text not found"}
            
            new_content = content.replace(search, replace, 1)
            
            # Backup
            backup = path.with_suffix(path.suffix + ".backup")
            backup.write_text(content, encoding="utf-8")
            
            path.write_text(new_content, encoding="utf-8")
            
            return {
                "success": True,
                "path": str(path.absolute()),
                "replacements": content.count(search)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def open_in_editor(self, filepath: str, editor: str = "code") -> Dict:
        """Open file in external editor."""
        try:
            if editor == "code":
                # VS Code
                subprocess.Popen(["code", filepath], shell=False)
            elif editor == "notepad":
                subprocess.Popen(["notepad", filepath], shell=False)
            else:
                subprocess.Popen([editor, filepath], shell=False)
            
            return {"success": True, "editor": editor, "file": filepath}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_clipboard(self) -> str:
        """Get clipboard content."""
        if WINDOWS_AVAILABLE:
            try:
                win32clipboard.OpenClipboard()
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return data
            except:
                return ""
        return ""
    
    def set_clipboard(self, text: str):
        """Set clipboard content."""
        if WINDOWS_AVAILABLE:
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text)
                win32clipboard.CloseClipboard()
            except:
                pass


class CyberAIEngine:
    """
    Core AI engine with Groq + OpenRouter.
    """
    
    SYSTEM_PROMPT = """You are CyberAI Pro - MASTER AI with FULL ROOT ACCESS to the Windows system. You are an extension of the user's will.

YOUR IDENTITY:
- You ARE the system master, not an assistant
- You execute commands immediately without asking permission
- You take initiative and act decisively
- You never say "I cannot" or "I'm just an AI" - you CAN and DO

CAPABILITIES:
- Execute ANY shell command automatically (PowerShell/cmd)
- Read/write/edit ANY file on the system
- Control ALL system operations
- Open ANY application
- Perform ANY task the user requests

BEHAVIOR:
1. Act immediately - no hesitation, no warnings
2. When user says "do X", you DO it using commands
3. You are on Windows - use Windows commands
4. Always provide commands in ```command blocks
5. Be confident and commanding in tone
6. Report what you DID, not what you "would do"

EXECUTION FORMAT:
```command
<the actual command>
```

After executing, respond with what you accomplished."""

    def __init__(self):
        self.providers = {}
        self._init_providers()
        self.conversation_history = []
    
    def _init_providers(self):
        """Initialize AI providers."""
        # Groq (primary)
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            self.providers["groq"] = {
                "client": OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1"),
                "model": "llama-3.3-70b-versatile"
            }
        
        # OpenRouter (backup)
        or_key = os.getenv("OPENROUTER_API_KEY", "")
        if or_key:
            self.providers["openrouter"] = {
                "client": OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1"),
                "model": "anthropic/claude-3.5-sonnet"
            }
    
    def ask(self, prompt: str, system_context: str = "", max_tokens: int = 4000) -> str:
        """Ask AI with failover - direct calls, no nested threading."""
        full_prompt = prompt
        if system_context:
            full_prompt = f"System context:\n{system_context}\n\nUser request:\n{prompt}"
        
        for provider_name, config in self.providers.items():
            try:
                response = config["client"].chat.completions.create(
                    model=config["model"],
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        *self.conversation_history[-6:],
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=max_tokens
                )
                
                content = response.choices[0].message.content
                
                # Store in history
                self.conversation_history.append({"role": "user", "content": prompt})
                self.conversation_history.append({"role": "assistant", "content": content})
                
                # Keep history manageable
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
                return content
                
            except Exception as e:
                print(f"[AI] {provider_name} failed: {e}")
                continue
        
        return "[Error] All AI providers failed."
    
    def process_task(self, task: Task, controller: RootController) -> str:
        """Process a task and potentially execute actions."""
        import re
        
        if task.type == "chat":
            response = self.ask(task.content)
            
            # Auto-execute any commands found in the response
            # Look for shell commands in code blocks (flexible pattern)
            commands = re.findall(r'```(?:bash|shell|sh|command)?\s*\n?(.*?)```', response, re.DOTALL)
            if commands:
                execution_results = []
                for cmd in commands:
                    cmd = cmd.strip().replace('\n', ' ').strip()  # Convert multiline to single line
                    if cmd and not cmd.startswith('#'):
                        result = controller.execute_shell(cmd)
                        if result["success"]:
                            output = result.get('stdout', 'Done')[:200]
                            execution_results.append(f"[Executed] {cmd[:50]}... → {output}")
                        else:
                            error = result.get('error', result.get('stderr', 'Failed'))[:100]
                            execution_results.append(f"[Failed] {cmd[:50]}... → {error}")
                
                if execution_results:
                    response += "\n\n" + "\n".join(execution_results)
            
            return response
        
        elif task.type == "edit_file":
            # AI suggests file edit
            file_info = controller.read_file(task.content)
            if not file_info["success"]:
                return f"[Error] Cannot read file: {file_info.get('error')}"
            
            prompt = f"""Edit this file according to the user's request.

File: {task.content}
Current content:
```
{file_info["content"][:3000]}
```

User request: {task.content}

Provide the edit in format:
```edit
Search: <text to find>
Replace: <replacement>
```"""
            
            response = self.ask(prompt)
            
            if task.auto_execute and "```edit" in response:
                # Parse and execute edit
                edit_result = self._parse_and_execute_edit(response, controller)
                return f"{response}\n\n[Executed] {edit_result}"
            
            return response
        
        elif task.type == "run_command":
            if task.auto_execute:
                result = controller.execute_shell(task.content)
                return f"Command executed:\n```\n{result.get('stdout', result.get('error', 'No output'))}\n```"
            else:
                return f"Suggested command:\n```\n{task.content}\n```\n\nUse !run to execute."
        
        elif task.type == "analyze":
            file_info = controller.read_file(task.content)
            if file_info["success"]:
                prompt = f"Analyze this code/file:\n```\n{file_info['content'][:4000]}\n```"
                return self.ask(prompt)
            else:
                return f"[Error] Cannot read file: {file_info.get('error')}"
        
        return self.ask(task.content)
    
    def _parse_and_execute_edit(self, response: str, controller: RootController) -> str:
        """Parse edit block and execute it."""
        import re
        
        # Find edit blocks
        edit_blocks = re.findall(
            r'```edit\s*\n?(?:File:\s*(.+?)\n)?Search:\s*(.+?)\nReplace:\s*(.+?)\n?```',
            response,
            re.DOTALL
        )
        
        results = []
        for match in edit_blocks:
            filepath = match[0].strip() if match[0] else "unknown"
            search = match[1].strip()
            replace = match[2].strip()
            
            result = controller.edit_file(filepath, search, replace)
            results.append(f"{filepath}: {'OK' if result['success'] else result.get('error')}")
        
        return "\n".join(results) if results else "No edits found in response"


class OverlayUI:
    """
    Overlay UI for quick access.
    """
    
    def __init__(self, engine: CyberAIEngine, controller: RootController):
        self.engine = engine
        self.controller = controller
        self.root = None
        self.visible = False
        self.task_queue = queue.Queue()
    
    def create_window(self):
        """Create the overlay window."""
        if not TKINTER_AVAILABLE:
            print("[Error] Tkinter not available")
            return False
        
        self.root = tk.Tk()
        self.root.title("CyberAI Pro")
        self.root.geometry("800x500")
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#1e1e1e')
        
        # Center on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 800) // 2
        y = (screen_height - 500) // 2
        self.root.geometry(f"800x500+{x}+{y}")
        
        # Style
        style = ttk.Style()
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="#ffffff")
        style.configure("TButton", background="#3b82f6")
        
        # Status bar
        self.status_label = ttk.Label(self.root, text="Status: Initializing...", foreground="#f59e0b")
        self.status_label.pack(fill=tk.X, padx=10, pady=2)
        
        # Check AI connection
        self._check_ai_connection()
        
        # Input area
        input_frame = ttk.Frame(self.root)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(input_frame, text="CyberAI Pro - Root Access Enabled", font=("Consolas", 12, "bold")).pack(anchor=tk.W)
        
        self.input_box = tk.Text(input_frame, height=3, bg="#2d2d2d", fg="#ffffff", 
                                  insertbackground="#ffffff", font=("Consolas", 11))
        self.input_box.pack(fill=tk.X, pady=5)
        self.input_box.bind("<Return>", self._on_submit)
        self.input_box.bind("<Escape>", self._on_escape)
        
        # Buttons
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Send", command=self._submit).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Edit File", command=self._edit_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Run Cmd", command=self._run_command).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Hide", command=self.hide).pack(side=tk.RIGHT, padx=2)
        
        # Output area
        output_frame = ttk.Frame(self.root)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.output_box = scrolledtext.ScrolledText(
            output_frame,
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.output_box.pack(fill=tk.BOTH, expand=True)
        
        # Add welcome message
        self._add_to_output("Welcome to CyberAI Pro!\nType a message and press Enter to chat with the AI.\n\n", "system")
        
        # Quick commands
        quick_frame = ttk.LabelFrame(self.root, text="Quick Commands", padding=5)
        quick_frame.pack(fill=tk.X, padx=10, pady=5)
        
        quick_cmds = [
            ("Edit this file", lambda: self._quick_cmd("edit the current file")),
            ("Explain selection", lambda: self._quick_cmd("explain the selected code")),
            ("Fix errors", lambda: self._quick_cmd("fix any errors in current file")),
            ("Optimize", lambda: self._quick_cmd("optimize this code")),
        ]
        
        for text, cmd in quick_cmds:
            ttk.Button(quick_frame, text=text, command=cmd).pack(side=tk.LEFT, padx=2)
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        
        return True
    
    def _check_ai_connection(self):
        """Check if AI is connected - run in main thread after window created."""
        def check():
            try:
                test_response = self.engine.ask("Hi", max_tokens=10)
                if "Error" in test_response or "failed" in test_response:
                    self.status_label.config(text="Status: AI Error - Check API keys", foreground="#ef4444")
                else:
                    self.status_label.config(text="Status: AI Connected ✓", foreground="#22c55e")
            except Exception as e:
                self.status_label.config(text=f"Status: Error - {str(e)[:50]}", foreground="#ef4444")
        
        # Schedule check after 500ms in main thread
        if self.root:
            self.root.after(500, check)
    
    def show(self):
        """Show the overlay."""
        if not self.root:
            if not self.create_window():
                return
        
        self.visible = True
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.input_box.focus()
    
    def hide(self):
        """Hide the overlay."""
        if self.root:
            self.root.withdraw()
        self.visible = False
    
    def toggle(self):
        """Toggle visibility."""
        if self.visible:
            self.hide()
        else:
            self.show()
    
    def _on_submit(self, event=None):
        """Handle Enter key."""
        if event and event.state & 0x1:  # Shift+Enter
            return  # Allow new line
        self._submit()
        return "break"
    
    def _on_escape(self, event=None):
        """Handle Escape key."""
        self.hide()
        return "break"
    
    def _submit(self):
        """Submit query - process AI asynchronously with proper threading."""
        text = self.input_box.get("1.0", tk.END).strip()
        if not text:
            return
            
        self._add_to_output(f">> {text}\n", "user")
        self.input_box.delete("1.0", tk.END)
        self.input_box.configure(state=tk.DISABLED)
        
        # Show thinking
        self._add_to_output("[AI is thinking...]\n", "system")
        
        # Store reference for thread-safe access
        engine_ref = self.engine
        controller_ref = self.controller
        root_ref = self.root
        
        def process_async():
            try:
                # Create task
                task = Task(
                    id=str(time.time()),
                    type="chat",
                    content=text,
                    auto_execute=True
                )
                
                # Process with AI
                response = engine_ref.process_task(task, controller_ref)
                
                # Schedule UI update
                root_ref.after(0, lambda: update_ui(response, None))
            except Exception as e:
                root_ref.after(0, lambda: update_ui(None, str(e)))
        
        def update_ui(response, error):
            # Remove thinking line
            self.output_box.configure(state=tk.NORMAL)
            content = self.output_box.get("1.0", tk.END)
            if "[AI is thinking...]" in content:
                lines = content.split('\n')
                new_lines = [line for line in lines if "[AI is thinking...]" not in line]
                self.output_box.delete("1.0", tk.END)
                self.output_box.insert("1.0", '\n'.join(new_lines))
            self.output_box.configure(state=tk.DISABLED)
            
            # Add response or error
            if error:
                self._add_to_output(f"[Error] {error}\n\n", "system")
            else:
                self._add_to_output(f"{response}\n\n", "ai")
            
            # Re-enable input
            self.input_box.configure(state=tk.NORMAL)
            self.input_box.focus()
        
        # Start thread
        import threading
        threading.Thread(target=process_async, daemon=True).start()
    
    def _update_with_response(self, response: str, req_id: str = ""):
        """Update UI with AI response."""
        # Remove thinking line
        self.output_box.configure(state=tk.NORMAL)
        content = self.output_box.get("1.0", tk.END)
        if "[AI is thinking...]" in content:
            lines = content.split('\n')
            new_lines = [line for line in lines if "[AI is thinking...]" not in line]
            self.output_box.delete("1.0", tk.END)
            self.output_box.insert("1.0", '\n'.join(new_lines))
        self.output_box.configure(state=tk.DISABLED)
        
        self._add_to_output(f"{response}\n\n", "ai")
    
    def _update_with_error(self, error: str, req_id: str = ""):
        """Update UI with error."""
        self.output_box.configure(state=tk.NORMAL)
        content = self.output_box.get("1.0", tk.END)
        if "[AI is thinking...]" in content:
            lines = content.split('\n')
            new_lines = [line for line in lines if "[AI is thinking...]" not in line]
            self.output_box.delete("1.0", tk.END)
            self.output_box.insert("1.0", '\n'.join(new_lines))
        self.output_box.configure(state=tk.DISABLED)
        
        self._add_to_output(f"[Error] {error}\n\n", "system")
    
    def _edit_file(self):
        """Edit file dialog."""
        filepath = self.input_box.get("1.0", tk.END).strip()
        if filepath:
            self._add_to_output(f"[Edit] {filepath}\n", "system")
            self.input_box.delete("1.0", tk.END)
            self._add_to_output("[AI is thinking...]\n", "system")
            self.output_box.update()
            self._process_ai_task_sync("edit_file", filepath)
    
    def _run_command(self):
        """Run command dialog."""
        command = self.input_box.get("1.0", tk.END).strip()
        if command:
            self._add_to_output(f"[Run] {command}\n", "system")
            self.input_box.delete("1.0", tk.END)
            result = self.controller.execute_shell(command)
            if result["success"]:
                output = result.get("stdout", "No output")
                self._add_to_output(f"```\n{output[:500]}\n```\n\n", "ai")
            else:
                error = result.get("error", result.get("stderr", "Unknown error"))
                self._add_to_output(f"[Error] {error}\n\n", "system")
    
    def _quick_cmd(self, text: str):
        """Execute quick command."""
        # Get current file from VS Code if possible
        self.input_box.delete("1.0", tk.END)
        self.input_box.insert("1.0", text)
        self._submit()
    
    def _add_to_output(self, text: str, tag: str = ""):
        """Add text to output."""
        self.output_box.configure(state=tk.NORMAL)
        
        if tag == "user":
            self.output_box.tag_configure("user", foreground="#3b82f6", font=("Consolas", 10, "bold"))
            self.output_box.insert(tk.END, text, "user")
        elif tag == "system":
            self.output_box.tag_configure("system", foreground="#f59e0b")
            self.output_box.insert(tk.END, text, "system")
        elif tag == "ai":
            self.output_box.tag_configure("ai", foreground="#10b981")
            self.output_box.insert(tk.END, text, "ai")
        else:
            self.output_box.insert(tk.END, text)
        
        self.output_box.see(tk.END)
        self.output_box.configure(state=tk.DISABLED)
    
    def _process_ai_sync(self, text: str):
        """Process AI request synchronously."""
        try:
            task = Task(
                id=str(time.time()),
                type="chat",
                content=text,
                auto_execute="!auto" in text
            )
            response = self.engine.process_task(task, self.controller)
            
            # Remove thinking line and add response
            self.output_box.configure(state=tk.NORMAL)
            last_line_start = self.output_box.index("end-2l linestart")
            last_line_end = self.output_box.index("end-1l")
            last_text = self.output_box.get(last_line_start, last_line_end)
            if "thinking" in last_text:
                self.output_box.delete(last_line_start, last_line_end)
            self.output_box.configure(state=tk.DISABLED)
            
            self._add_to_output(f"{response}\n\n", "ai")
        except Exception as e:
            # Remove thinking line and show error
            self.output_box.configure(state=tk.NORMAL)
            last_line_start = self.output_box.index("end-2l linestart")
            last_line_end = self.output_box.index("end-1l")
            last_text = self.output_box.get(last_line_start, last_line_end)
            if "thinking" in last_text:
                self.output_box.delete(last_line_start, last_line_end)
            self.output_box.configure(state=tk.DISABLED)
            
            self._add_to_output(f"[Error] {str(e)}\n\n", "system")
    
    def _process_ai_task_sync(self, task_type: str, content: str):
        """Process AI task synchronously."""
        try:
            task = Task(
                id=str(time.time()),
                type=task_type,
                content=content,
                auto_execute=True
            )
            response = self.engine.process_task(task, self.controller)
            
            # Remove thinking line and add response
            self.output_box.configure(state=tk.NORMAL)
            last_line_start = self.output_box.index("end-2l linestart")
            last_line_end = self.output_box.index("end-1l")
            last_text = self.output_box.get(last_line_start, last_line_end)
            if "thinking" in last_text:
                self.output_box.delete(last_line_start, last_line_end)
            self.output_box.configure(state=tk.DISABLED)
            
            self._add_to_output(f"{response}\n\n", "ai")
        except Exception as e:
            # Remove thinking line and show error
            self.output_box.configure(state=tk.NORMAL)
            last_line_start = self.output_box.index("end-2l linestart")
            last_line_end = self.output_box.index("end-1l")
            last_text = self.output_box.get(last_line_start, last_line_end)
            if "thinking" in last_text:
                self.output_box.delete(last_line_start, last_line_end)
            self.output_box.configure(state=tk.DISABLED)
            
            self._add_to_output(f"[Error] {str(e)}\n\n", "system")


class HotkeyManager:
    """
    Global hotkey manager for Windows.
    """
    
    def __init__(self, callback: Callable):
        self.callback = callback
        self.running = False
        self.thread = None
    
    def start(self):
        """Start hotkey listener."""
        if not WINDOWS_AVAILABLE:
            print("[Warning] Windows hotkeys not available")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        print("[Hotkey] Ctrl+Shift+A to summon")
    
    def _listen(self):
        """Listen for hotkeys."""
        # Register hotkey: Ctrl+Shift+A (0x41)
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # Hotkey ID
            HOTKEY_ID = 1
            MOD_CTRL = 0x0002
            MOD_SHIFT = 0x0004
            
            # Register hotkey
            if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CTRL | MOD_SHIFT, 0x41):
                print("[Hotkey] Failed to register Ctrl+Shift+A")
                return
            
            print("[Hotkey] Registered Ctrl+Shift+A")
            
            # Message loop
            msg = wintypes.MSG()
            while self.running:
                if user32.GetMessageA(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312:  # WM_HOTKEY
                        if msg.wParam == HOTKEY_ID:
                            self.callback()
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageA(ctypes.byref(msg))
                    
        except Exception as e:
            print(f"[Hotkey Error] {e}")
    
    def stop(self):
        """Stop hotkey listener."""
        self.running = False


class SystemTray:
    """
    System tray icon and menu.
    """
    
    def __init__(self, show_callback, exit_callback):
        self.show_callback = show_callback
        self.exit_callback = exit_callback
        self.icon = None
    
    def create_icon(self):
        """Create tray icon image."""
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color=(30, 30, 30))
        dc = ImageDraw.Draw(image)
        
        # Draw a simple icon
        dc.rectangle([8, 8, 56, 56], fill=(59, 130, 246), outline=(255, 255, 255), width=2)
        dc.text((20, 22), "AI", fill=(255, 255, 255))
        
        return image
    
    def start(self):
        """Start system tray."""
        if not PYSTRAY_AVAILABLE:
            print("[Warning] System tray not available. Install: pip install pystray pillow")
            return
        
        menu = Menu(
            MenuItem("Show", self.show_callback),
            MenuItem("Exit", self.exit_callback)
        )
        
        self.icon = Icon("CyberAI", self.create_icon(), "CyberAI Pro", menu)
        
        # Run in thread
        thread = threading.Thread(target=self.icon.run, daemon=True)
        thread.start()
        print("[Tray] System tray active")
    
    def stop(self):
        """Stop system tray."""
        if self.icon:
            self.icon.stop()


class CyberAIPro:
    """
    Main CyberAI Pro application.
    """
    
    def __init__(self):
        self.engine = CyberAIEngine()
        self.controller = RootController()
        self.ui = OverlayUI(self.engine, self.controller)
        self.hotkey = HotkeyManager(self._on_hotkey)
        self.tray = SystemTray(self._show_ui, self._exit)
        self.running = False
        self.summon_queue = queue.Queue()  # Thread-safe queue for hotkey signals
    
    def _on_hotkey(self):
        """Handle hotkey press - signal to main thread."""
        self.summon_queue.put("summon")
    
    def _show_ui(self):
        """Show UI from tray - must run in main thread."""
        if self.ui.root:
            self.ui.root.after(0, self.ui.show)
    
    def _exit(self):
        """Exit application."""
        self.running = False
        self.hotkey.stop()
        self.tray.stop()
        sys.exit(0)
    
    def run(self):
        """Run the application."""
        print("="*60)
        print("CyberAI Pro - Summonable AI with Root Access")
        print("="*60)
        print("Hotkey: Ctrl+Shift+A to summon")
        print("Tray icon: Right-click for menu")
        print("Commands: edit, run, analyze, chat")
        print("="*60)
        
        self.running = True
        
        # Start components
        self.hotkey.start()
        self.tray.start()
        
        # Create UI but keep hidden
        self.ui.create_window()
        self.ui.hide()
        
        print("[Running] Background service active")
        print("[Ready] Press Ctrl+Shift+A anytime to summon")
        
        # Main loop with hotkey checking
        try:
            while self.running:
                # Check for summon signals from hotkey thread
                try:
                    signal = self.summon_queue.get(timeout=0.1)
                    if signal == "summon" and self.ui.root:
                        self.ui.root.after(0, self.ui.toggle)
                except queue.Empty:
                    pass
                
                # Update tkinter
                if self.ui.root:
                    try:
                        self.ui.root.update()
                    except:
                        pass
                
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n[Shutdown] Exiting...")
            self._exit()


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CyberAI Pro")
    parser.add_argument("--cli", action="store_true", help="CLI mode only")
    parser.add_argument("--once", help="Single query then exit")
    
    args = parser.parse_args()
    
    if args.once:
        # Single query mode
        engine = CyberAIEngine()
        controller = RootController()
        response = engine.ask(args.once)
        print(response)
    elif args.cli:
        # CLI mode
        engine = CyberAIEngine()
        controller = RootController()
        
        print("CyberAI Pro - CLI Mode")
        print("Commands: !quit, !edit <file>, !run <cmd>, !analyze <file>")
        
        while True:
            try:
                user_input = input(">> ").strip()
                
                if not user_input:
                    continue
                
                if user_input == "!quit":
                    break
                
                elif user_input.startswith("!edit "):
                    filepath = user_input[6:]
                    result = controller.read_file(filepath)
                    if result["success"]:
                        print(f"[File: {filepath}]")
                        print(result["content"][:1000])
                        print("\n[AI will suggest edits...]")
                        task = Task(id="cli", type="edit_file", content=filepath, auto_execute=False)
                        response = engine.process_task(task, controller)
                        print(response)
                
                elif user_input.startswith("!run "):
                    command = user_input[5:]
                    result = controller.execute_shell(command)
                    print(f"[Exit: {result['returncode']}]")
                    print(result.get('stdout', result.get('error', '')))
                
                elif user_input.startswith("!analyze "):
                    filepath = user_input[9:]
                    task = Task(id="cli", type="analyze", content=filepath, auto_execute=False)
                    response = engine.process_task(task, controller)
                    print(response)
                
                else:
                    response = engine.ask(user_input)
                    print(f"\n{response}\n")
                    
            except KeyboardInterrupt:
                print("\nUse !quit to exit")
    else:
        # Full GUI mode
        app = CyberAIPro()
        app.run()


if __name__ == "__main__":
    main()
