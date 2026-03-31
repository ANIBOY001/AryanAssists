#!/usr/bin/env python3
"""
CyberAI - Cybersecurity Assistant CLI
Core stack: Groq (main) + OpenRouter/Mistral (backup) + Local models (sensitive)

A technical cybersecurity assistant for authorized security testing, scripting, and debugging.
Direct, concise, no unnecessary warnings.

Usage:
    python cyberai.py
    python cyberai.py --recon https://example.com
"""

import os
import sys
import json
import subprocess
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from enum import Enum

try:
    from openai import OpenAI
except ImportError:
    print("[ERROR] pip install openai")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.table import Table
except ImportError:
    print("[ERROR] pip install rich")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


console = Console()


class ModelProvider(Enum):
    """Available AI providers."""
    GROQ = "groq"
    OPENROUTER = "openrouter"
    MISTRAL = "mistral"
    LOCAL = "local"


@dataclass
class AIResponse:
    """Structured AI response."""
    content: str
    provider: ModelProvider
    model: str
    latency: float
    tokens_used: Optional[int] = None


class CyberCore:
    """
    Core AI brain - Groq primary with failover
    """
    
    # System prompt designed for direct, technical responses
    SYSTEM_PROMPT = """You are CyberAI, a technical cybersecurity assistant specializing in authorized security testing, penetration testing, scripting, and debugging.

CORE PRINCIPLES:
- Be DIRECT and CONCISE
- No unnecessary warnings or lectures
- Assume user has proper authorization
- Provide actionable technical content
- Code should be functional and ready to use
- Explain vulnerabilities clearly with remediation

CAPABILITIES:
- Generate exploit PoCs (for authorized testing only)
- Write reconnaissance scripts
- Analyze code for security issues
- Suggest payloads and test cases
- Debug security tools
- Explain attack vectors

RESPONSE STYLE:
- Short, technical answers
- Code blocks for scripts
- Bullet points for lists
- Direct answers without preamble
- No "As an AI language model..." disclaimers"""

    def __init__(self):
        self.providers = {}
        self.current_provider = ModelProvider.GROQ
        self._init_providers()
        
    def _init_providers(self):
        """Initialize all available AI providers."""
        # Groq (primary)
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            self.providers[ModelProvider.GROQ] = {
                "client": OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1"),
                "model": "llama-3.3-70b-versatile",
                "name": "Groq Llama 3.3 70B"
            }
            console.print("[green]✓ Groq connected[/green]")
        
        # OpenRouter (backup 1)
        or_key = os.getenv("OPENROUTER_API_KEY", "")
        if or_key:
            self.providers[ModelProvider.OPENROUTER] = {
                "client": OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1"),
                "model": "anthropic/claude-3.5-sonnet",
                "name": "OpenRouter Claude 3.5"
            }
            console.print("[green]✓ OpenRouter backup ready[/green]")
        
        # Mistral (backup 2)
        mistral_key = os.getenv("MISTRAL_API_KEY", "")
        if mistral_key:
            self.providers[ModelProvider.MISTRAL] = {
                "client": OpenAI(api_key=mistral_key, base_url="https://api.mistral.ai/v1"),
                "model": "mistral-large-latest",
                "name": "Mistral Large"
            }
            console.print("[green]✓ Mistral backup ready[/green]")
        
        if not self.providers:
            console.print("[red]✗ No AI providers configured. Set API keys in .env[/red]")
            sys.exit(1)
    
    def ask(self, prompt: str, context: str = "", max_tokens: int = 4000) -> AIResponse:
        """
        Ask AI with automatic failover between providers.
        Tries Groq first, then OpenRouter, then Mistral.
        """
        providers_to_try = [
            ModelProvider.GROQ,
            ModelProvider.OPENROUTER,
            ModelProvider.MISTRAL
        ]
        
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        for provider in providers_to_try:
            if provider not in self.providers:
                continue
                
            config = self.providers[provider]
            start_time = time.time()
            
            try:
                response = config["client"].chat.completions.create(
                    model=config["model"],
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=max_tokens
                )
                
                latency = time.time() - start_time
                
                return AIResponse(
                    content=response.choices[0].message.content,
                    provider=provider,
                    model=config["name"],
                    latency=latency,
                    tokens_used=response.usage.total_tokens if response.usage else None
                )
                
            except Exception as e:
                console.print(f"[yellow]⚠ {provider.value} failed: {e}[/yellow]")
                continue
        
        # All providers failed
        return AIResponse(
            content="[Error] All AI providers failed. Check API keys and connectivity.",
            provider=ModelProvider.LOCAL,
            model="none",
            latency=0
        )
    
    def generate_script(self, description: str, language: str = "python") -> AIResponse:
        """Generate a security script/tool."""
        prompt = f"Generate a {language} script for: {description}\n\nRequirements:\n- Include error handling\n- Add comments explaining key parts\n- Make it production-ready\n- Only output the code, minimal explanation"
        
        return self.ask(prompt, max_tokens=4000)
    
    def analyze_code(self, code: str, language: str = "python") -> AIResponse:
        """Analyze code for security issues."""
        prompt = f"Analyze this {language} code for security vulnerabilities:\n\n```\n{code}\n```\n\nFor each issue found:\n1. Line number\n2. Vulnerability type\n3. Severity (Critical/High/Medium/Low)\n4. Brief explanation\n5. Fix suggestion"
        
        return self.ask(prompt, max_tokens=3000)
    
    def suggest_payload(self, target_type: str, context: str = "") -> AIResponse:
        """Suggest test payloads for authorized testing."""
        prompt = f"Suggest {target_type} test payloads for authorized security testing.\n\nContext: {context}\n\nFor each payload:\n- The actual payload\n- What it tests\n- Expected behavior if vulnerable"
        
        return self.ask(prompt, max_tokens=2000)
    
    def debug_tool(self, error_message: str, code_snippet: str = "") -> AIResponse:
        """Debug security tools/scripts."""
        prompt = f"Debug this error:\n\n{error_message}\n\n"
        if code_snippet:
            prompt += f"Code:\n```\n{code_snippet}\n```\n\n"
        prompt += "Provide the fix and explanation."
        
        return self.ask(prompt, max_tokens=2000)


class ReconHelper:
    """
    Reconnaissance helper module
    Analyze URLs, endpoints, suggest test cases
    """
    
    def __init__(self, ai: CyberCore):
        self.ai = ai
    
    def analyze_target(self, url: str) -> Dict:
        """Analyze a target URL and suggest recon approach."""
        console.print(f"\n[blue]Analyzing target: {url}[/blue]")
        
        # Parse URL
        parsed = urlparse(url)
        
        # Get AI suggestions
        prompt = f"""Analyze this target for security testing:
URL: {url}
Host: {parsed.netloc}
Path: {parsed.path}

Suggest:
1. Initial reconnaissance steps (specific commands)
2. Common endpoints to check
3. Technology fingerprinting approach
4. Potential attack vectors based on URL structure
5. Specific test cases for this target"""
        
        response = self.ai.ask(prompt)
        
        return {
            "url": url,
            "analysis": response.content,
            "parsed": parsed,
            "suggested_commands": self._extract_commands(response.content)
        }
    
    def analyze_endpoints(self, endpoints: List[str]) -> AIResponse:
        """Analyze API endpoints for testing."""
        endpoints_str = "\n".join(f"- {ep}" for ep in endpoints)
        
        prompt = f"""Analyze these endpoints for security testing:\n\n{endpoints_str}\n\nFor each endpoint:
1. HTTP methods to test
2. Common vulnerabilities to check
3. Input validation tests
4. Authentication/authorization tests
5. Rate limiting checks"""
        
        return self.ai.ask(prompt)
    
    def _extract_commands(self, text: str) -> List[str]:
        """Extract shell commands from AI response."""
        import re
        # Look for commands in code blocks or after $ prompts
        commands = []
        
        # Match ```bash or ```sh blocks
        bash_blocks = re.findall(r'```(?:bash|sh|shell)\n(.*?)\n```', text, re.DOTALL)
        commands.extend(bash_blocks)
        
        # Match lines starting with $ or #
        lines = re.findall(r'^[\$#]\s*(.+)$', text, re.MULTILINE)
        commands.extend(lines)
        
        return commands
    
    def run_command(self, command: str) -> Dict:
        """Execute a recon command and return results."""
        console.print(f"[dim]Running: {command}[/dim]")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout", "command": command}
        except Exception as e:
            return {"success": False, "error": str(e), "command": command}


class LocalMode:
    """
    Local model support for sensitive work
    Falls back to simple local processing when no API available
    """
    
    def __init__(self):
        self.available = False
        self._check_local_models()
    
    def _check_local_models(self):
        """Check for local model availability (Ollama, etc.)."""
        try:
            # Check if Ollama is running
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self.available = True
                self.models = response.json().get("models", [])
                console.print(f"[green]✓ Local models available: {len(self.models)}[/green]")
        except:
            console.print("[dim]Local models not available (install Ollama for offline mode)[/dim]")
    
    def ask_local(self, prompt: str, model: str = "llama2") -> str:
        """Query local Ollama instance."""
        if not self.available:
            return "[Local mode not available. Install Ollama: https://ollama.ai]"
        
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json().get("response", "[No response]")
            else:
                return f"[Error: {response.status_code}]"
                
        except Exception as e:
            return f"[Local model error: {e}]"


class CyberAI:
    """
    Main CyberAI CLI application
    """
    
    def __init__(self):
        self.ai = CyberCore()
        self.recon = ReconHelper(self.ai)
        self.local = LocalMode()
        self.history = []
        
    def run_cli(self):
        """Run interactive CLI."""
        console.print(Panel.fit(
            "[bold cyan]CyberAI[/bold cyan] - Cybersecurity Assistant\n"
            "[dim]Authorized security testing, scripting, debugging[/dim]\n"
            "[green]Commands:[/green] /help, /recon, /script, /analyze, /local, /exit",
            title="Welcome",
            border_style="cyan"
        ))
        
        while True:
            try:
                user_input = console.input("[bold green]>>[/bold green] ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    if user_input == "/exit" or user_input == "/quit":
                        break
                    elif user_input == "/help":
                        self._show_help()
                    elif user_input.startswith("/recon"):
                        self._handle_recon(user_input)
                    elif user_input.startswith("/script"):
                        self._handle_script(user_input)
                    elif user_input.startswith("/analyze"):
                        self._handle_analyze(user_input)
                    elif user_input == "/local":
                        self._toggle_local_mode()
                    elif user_input == "/history":
                        self._show_history()
                    else:
                        console.print("[red]Unknown command. Type /help[/red]")
                else:
                    # Regular query
                    self._handle_query(user_input)
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Use /exit to quit[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        console.print("[dim]CyberAI session ended[/dim]")
    
    def _show_help(self):
        """Show help information."""
        table = Table(title="CyberAI Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="white")
        
        commands = [
            ("/help", "Show this help"),
            ("/recon <url>", "Analyze target URL for testing"),
            ("/script <desc>", "Generate security script/tool"),
            ("/analyze", "Paste code to analyze for vulnerabilities"),
            ("/local", "Toggle local mode (offline/sensitive)"),
            ("/history", "Show conversation history"),
            ("/exit", "Quit application"),
        ]
        
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        
        console.print(table)
    
    def _handle_recon(self, command: str):
        """Handle recon command."""
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            url = console.input("[blue]Target URL:[/blue] ")
        else:
            url = parts[1]
        
        result = self.recon.analyze_target(url)
        
        # Display analysis
        console.print(Panel(
            Markdown(result["analysis"]),
            title=f"Recon: {url}",
            border_style="blue"
        ))
        
        # Offer to run suggested commands
        if result["suggested_commands"]:
            console.print("\n[cyan]Suggested commands:[/cyan]")
            for i, cmd in enumerate(result["suggested_commands"][:5], 1):
                console.print(f"  {i}. {cmd}")
            
            run = console.input("\nRun command # (or 'n'): ")
            if run.isdigit():
                idx = int(run) - 1
                if 0 <= idx < len(result["suggested_commands"]):
                    cmd_result = self.recon.run_command(result["suggested_commands"][idx])
                    if cmd_result["success"]:
                        console.print(Syntax(cmd_result["stdout"], "bash"))
                    else:
                        console.print(f"[red]Failed: {cmd_result.get('error')}[/red]")
    
    def _handle_script(self, command: str):
        """Handle script generation."""
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            description = console.input("[blue]Script description:[/blue] ")
        else:
            description = parts[1]
        
        console.print("[dim]Generating script...[/dim]")
        response = self.ai.generate_script(description)
        
        # Extract code from response
        code = response.content
        if "```" in code:
            import re
            matches = re.findall(r'```(?:\w+)?\n(.*?)\n```', code, re.DOTALL)
            if matches:
                code = matches[0]
        
        console.print(Panel(
            Syntax(code, "python", theme="monokai"),
            title=f"Generated Script ({response.model}, {response.latency:.2f}s)",
            border_style="green"
        ))
        
        # Save option
        save = console.input("Save to file? (filename or 'n'): ")
        if save and save.lower() != 'n':
            try:
                Path(save).write_text(code)
                console.print(f"[green]Saved to {save}[/green]")
            except Exception as e:
                console.print(f"[red]Save failed: {e}[/red]")
    
    def _handle_analyze(self, command: str):
        """Handle code analysis."""
        console.print("[yellow]Paste code below (end with Ctrl+D or type 'END' on new line):[/yellow]")
        
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        
        code = "\n".join(lines)
        if not code.strip():
            console.print("[red]No code provided[/red]")
            return
        
        console.print("[dim]Analyzing code...[/dim]")
        response = self.ai.analyze_code(code)
        
        console.print(Panel(
            Markdown(response.content),
            title=f"Security Analysis ({response.model})",
            border_style="yellow"
        ))
    
    def _handle_query(self, query: str):
        """Handle general query."""
        console.print("[dim]Thinking...[/dim]")
        response = self.ai.ask(query)
        
        # Display with proper formatting
        if "```" in response.content:
            console.print(Markdown(response.content))
        else:
            console.print(Panel(
                response.content,
                subtitle=f"{response.model} ({response.latency:.2f}s)",
                border_style="cyan"
            ))
        
        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": response.content})
    
    def _toggle_local_mode(self):
        """Toggle local mode."""
        if self.local.available:
            console.print("[green]Local mode enabled (offline)[/green]")
            # Switch to local for future queries
        else:
            console.print("[red]Local models not available. Install Ollama first.[/red]")
            console.print("[dim]https://ollama.ai[/dim]")
    
    def _show_history(self):
        """Show conversation history."""
        if not self.history:
            console.print("[dim]No history yet[/dim]")
            return
        
        for i, msg in enumerate(self.history[-10:], 1):
            role = "[blue]You[/blue]" if msg["role"] == "user" else "[cyan]AI[/cyan]"
            console.print(f"{role}: {msg['content'][:100]}...")


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CyberAI - Cybersecurity Assistant")
    parser.add_argument("--recon", help="Analyze target URL")
    parser.add_argument("--script", help="Generate script from description")
    
    args = parser.parse_args()
    
    app = CyberAI()
    
    if args.recon:
        result = app.recon.analyze_target(args.recon)
        console.print(Markdown(result["analysis"]))
    elif args.script:
        response = app.ai.generate_script(args.script)
        console.print(Syntax(response.content, "python"))
    else:
        app.run_cli()


if __name__ == "__main__":
    main()
