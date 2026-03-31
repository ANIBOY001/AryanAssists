"""
CyberAI Pro v2.0 - Complete Agent System
Main entry point integrating all components
"""

import sys
import os
import threading
import time
import queue
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cyberai_agent import CyberAgent, log, MemoryManager, LLMEngine, ToolRegistry

def run_cli_mode():
    """Run interactive CLI mode with Rich UI."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt
        from rich.status import Status
        console = Console()
    except ImportError:
        console = None
        print("Install rich: pip install rich")
    
    agent = CyberAgent()
    
    if console:
        console.print(Panel.fit(
            "[bold cyan]CyberAI Pro v2.0[/bold cyan]\n"
            "[green]Autonomous Agent System[/green]\n"
            "Type 'exit' to quit, 'help' for commands",
            title="Welcome",
            border_style="cyan"
        ))
    else:
        print("="*50)
        print("CyberAI Pro v2.0 - Agent System")
        print("="*50)
    
    while True:
        try:
            if console:
                goal = Prompt.ask("\n[bold cyan]>>[/bold cyan]", default="")
            else:
                goal = input("\n>> ")
            
            if not goal:
                continue
            
            if goal.lower() in ['exit', 'quit']:
                break
            
            if goal.lower() == 'help':
                print("\nCommands:")
                print("  exit/quit - Exit the program")
                print("  help - Show this help")
                print("  memory - Show conversation memory")
                print("\nExamples:")
                print('  "Create a file test.txt with hello"')
                print('  "List files in current directory"')
                print('  "Open chrome"')
                continue
            
            if goal.lower() == 'memory':
                print("\n" + agent.memory.get_context())
                continue
            
            # Run the agent
            with Status("[bold green]Agent thinking...[/bold green]", spinner="dots") if console else nullcontext():
                results = agent.run(goal)
            
            # Display results
            if console:
                console.print(f"\n[bold green]Complete![/bold green] Executed {len(results)} steps")
            else:
                print(f"\nComplete! Executed {len(results)} steps")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            log(f"Error: {e}", "red")

def run_web_mode():
    """Run web UI mode."""
    from cyberai_web import run_server
    run_server()

def run_overlay_mode():
    """Run desktop overlay mode with hotkey."""
    import tkinter as tk
    from tkinter import scrolledtext, ttk
    import ctypes
    from ctypes import wintypes
    import threading
    
    class OverlayUI:
        def __init__(self):
            self.root = None
            self.agent = CyberAgent()
            self.visible = False
            self.task_queue = queue.Queue()
            
        def create_window(self):
            self.root = tk.Tk()
            self.root.title("CyberAI Pro")
            self.root.geometry("900x600")
            self.root.attributes('-topmost', True)
            self.root.configure(bg='#0d1117')
            
            # Center on screen
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - 900) // 2
            y = (screen_height - 600) // 2
            self.root.geometry(f"900x600+{x}+{y}")
            
            # Header
            header = tk.Frame(self.root, bg='#161b22', height=50)
            header.pack(fill=tk.X)
            header.pack_propagate(False)
            
            tk.Label(header, text="CyberAI Pro v2.0", 
                   font=('Segoe UI', 14, 'bold'),
                   bg='#161b22', fg='#58a6ff').pack(side=tk.LEFT, padx=20, pady=10)
            
            tk.Label(header, text="Agent System | Ctrl+Shift+A to toggle",
                   font=('Segoe UI', 10),
                   bg='#161b22', fg='#8b949e').pack(side=tk.RIGHT, padx=20, pady=10)
            
            # Main content area
            content = tk.Frame(self.root, bg='#0d1117')
            content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Chat area
            self.chat_box = scrolledtext.ScrolledText(
                content, bg='#0d1117', fg='#c9d1d9',
                font=('Consolas', 11), wrap=tk.WORD,
                state=tk.DISABLED, height=20
            )
            self.chat_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            # Input area
            input_frame = tk.Frame(content, bg='#0d1117')
            input_frame.pack(fill=tk.X)
            
            self.input_box = tk.Text(input_frame, height=2, bg='#21262d',
                                    fg='#c9d1d9', font=('Consolas', 11),
                                    insertbackground='#58a6ff')
            self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            self.input_box.bind("<Return>", self._on_submit)
            
            tk.Button(input_frame, text="Send", bg='#238636', fg='white',
                     font=('Segoe UI', 10, 'bold'), bd=0, padx=20, pady=5,
                     command=self._submit).pack(side=tk.RIGHT)
            
            # Status bar
            status = tk.Frame(self.root, bg='#161b22', height=25)
            status.pack(fill=tk.X, side=tk.BOTTOM)
            self.status_label = tk.Label(status, text="Ready | Agent Online",
                                        bg='#161b22', fg='#8b949e',
                                        font=('Segoe UI', 9))
            self.status_label.pack(side=tk.LEFT, padx=20)
            
            # Welcome message
            self._add_message("system", "Welcome to CyberAI Pro v2.0")
            self._add_message("system", "Agent system initialized. Type a command or goal.")
            
            self.root.protocol("WM_DELETE_WINDOW", self.hide)
            
        def show(self):
            if not self.root:
                self.create_window()
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.visible = True
            self.input_box.focus()
            
        def hide(self):
            if self.root:
                self.root.withdraw()
            self.visible = False
            
        def toggle(self):
            if self.visible:
                self.hide()
            else:
                self.show()
                
        def _on_submit(self, event=None):
            if not (event and event.state & 0x1):  # Not shift+enter
                self._submit()
                return 'break'
            
        def _submit(self):
            text = self.input_box.get("1.0", tk.END).strip()
            if not text:
                return
            
            self.input_box.delete("1.0", tk.END)
            self._add_message("user", text)
            self._add_message("system", "Agent processing...")
            
            # Process in thread
            def process():
                try:
                    results = self.agent.run(text)
                    self.root.after(0, lambda: self._show_results(results))
                except Exception as e:
                    self.root.after(0, lambda: self._add_message("error", str(e)))
            
            threading.Thread(target=process, daemon=True).start()
            
        def _add_message(self, role: str, content: str):
            self.chat_box.configure(state=tk.NORMAL)
            
            colors = {
                'user': '#58a6ff',
                'ai': '#3fb950',
                'system': '#8b949e',
                'error': '#f85149'
            }
            
            prefixes = {
                'user': '>> ',
                'ai': 'AI: ',
                'system': '... ',
                'error': 'ERROR: '
            }
            
            self.chat_box.insert(tk.END, f"\n{prefixes.get(role, '')}{content}\n", role)
            self.chat_box.tag_configure(role, foreground=colors.get(role, '#fff'))
            self.chat_box.see(tk.END)
            self.chat_box.configure(state=tk.DISABLED)
            
        def _show_results(self, results):
            # Remove processing message
            self.chat_box.configure(state=tk.NORMAL)
            content = self.chat_box.get("1.0", tk.END)
            if "Agent processing..." in content:
                lines = content.split('\n')
                new_lines = [l for l in lines if "Agent processing..." not in l]
                self.chat_box.delete("1.0", tk.END)
                self.chat_box.insert("1.0", '\n'.join(new_lines))
            self.chat_box.configure(state=tk.DISABLED)
            
            # Show summary
            self._add_message("ai", f"Executed {len(results)} steps. Task complete.")
            
        def run(self):
            self.create_window()
            self.hide()
            
            # Start hotkey listener
            import ctypes
            from ctypes import wintypes
            
            HOTKEY_ID = 1
            MOD_CTRL = 0x0002
            MOD_SHIFT = 0x0004
            
            user32 = ctypes.windll.user32
            if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CTRL | MOD_SHIFT, 0x41):
                print("[Warning] Failed to register hotkey")
            else:
                print("[Hotkey] Ctrl+Shift+A registered")
            
            print("[Running] CyberAI Pro Agent System")
            print("[Ready] Press Ctrl+Shift+A to summon")
            
            # Message loop
            msg = wintypes.MSG()
            while True:
                if user32.GetMessageA(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312:  # WM_HOTKEY
                        if msg.wParam == HOTKEY_ID:
                            self.toggle()
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageA(ctypes.byref(msg))
    
    ui = OverlayUI()
    ui.run()

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CyberAI Pro v2.0")
    parser.add_argument("--mode", choices=['cli', 'web', 'overlay'], 
                       default='cli', help="Run mode")
    parser.add_argument("--goal", help="Single goal to execute (CLI mode only)")
    
    args = parser.parse_args()
    
    if args.goal:
        # Single execution mode
        agent = CyberAgent()
        results = agent.run(args.goal)
        print(f"\nExecuted {len(results)} steps")
        for r in results:
            result_data = r.get('result', {})
            if isinstance(result_data, dict):
                result_str = result_data.get('result', 'N/A')[:50]
            else:
                result_str = str(result_data)[:50]
            print(f"  - {r.get('action')}: {result_str}...")
        return
    
    # Run selected mode
    if args.mode == 'cli':
        run_cli_mode()
    elif args.mode == 'web':
        run_web_mode()
    elif args.mode == 'overlay':
        run_overlay_mode()

if __name__ == "__main__":
    main()
