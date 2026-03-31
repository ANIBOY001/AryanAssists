"""
CyberAI Pro - Web UI with FastAPI
Beautiful, responsive web interface with real-time updates
CACHE_BUST: v3.0-rebuild-001
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn

# Import our agent system
from cyberai_agent import IntelligentAgent, log

# Create FastAPI app
app = FastAPI(title="CyberAI Pro", version="2.0")

# Store active sessions
class SessionManager:
    def __init__(self):
        self.agents: Dict[str, IntelligentAgent] = {}
        self.connections: Dict[str, WebSocket] = {}
    
    def get_or_create_agent(self, session_id: str) -> IntelligentAgent:
        if session_id not in self.agents:
            self.agents[session_id] = IntelligentAgent()
        return self.agents[session_id]
    
    def remove_session(self, session_id: str):
        if session_id in self.agents:
            del self.agents[session_id]
        if session_id in self.connections:
            del self.connections[session_id]

session_manager = SessionManager()

# HTML Template (embedded for portability)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberAI Pro - Agent System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: grid;
            grid-template-columns: 300px 1fr 350px;
            height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            background: rgba(0,0,0,0.3);
            border-right: 1px solid rgba(255,255,255,0.1);
            padding: 20px;
            overflow-y: auto;
        }
        
        .logo {
            font-size: 24px;
            font-weight: bold;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 20px;
            padding: 10px;
            background: rgba(0,212,255,0.1);
            border-radius: 8px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            background: #00ff88;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .tool-list {
            list-style: none;
        }
        
        .tool-list li {
            padding: 10px;
            margin: 5px 0;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .tool-list li:hover {
            background: rgba(0,212,255,0.2);
        }
        
        /* Main Chat Area */
        .main-area {
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        
        .chat-header {
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 20px;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }
        
        .message {
            margin-bottom: 20px;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message-user {
            text-align: right;
        }
        
        .message-user .bubble {
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            display: inline-block;
            padding: 12px 16px;
            border-radius: 16px 16px 4px 16px;
            max-width: 80%;
            text-align: left;
        }
        
        .message-ai .bubble {
            background: rgba(255,255,255,0.1);
            display: inline-block;
            padding: 12px 16px;
            border-radius: 16px 16px 16px 4px;
            max-width: 80%;
            border-left: 3px solid #00d4ff;
        }
        
        .message-system .bubble {
            background: rgba(255,193,7,0.1);
            color: #ffc107;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.9em;
            font-family: monospace;
        }
        
        .input-area {
            display: flex;
            gap: 10px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        
        .input-area input {
            flex: 1;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 16px;
            outline: none;
        }
        
        .input-area input:focus {
            border-color: #00d4ff;
        }
        
        .input-area button {
            background: linear-gradient(135deg, #00d4ff, #7b2cbf);
            color: #fff;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.2s;
        }
        
        .input-area button:hover {
            transform: scale(1.05);
        }
        
        .input-area button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Right Panel - Execution Log */
        .right-panel {
            background: rgba(0,0,0,0.3);
            border-left: 1px solid rgba(255,255,255,0.1);
            padding: 20px;
            overflow-y: auto;
        }
        
        .panel-title {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #888;
            margin-bottom: 15px;
        }
        
        .execution-step {
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            border-left: 3px solid #00d4ff;
        }
        
        .execution-step.error {
            border-left-color: #ff4444;
        }
        
        .execution-step.success {
            border-left-color: #00ff88;
        }
        
        .step-header {
            font-weight: bold;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        
        .step-content {
            font-family: 'Consolas', monospace;
            font-size: 0.85em;
            color: #ccc;
            word-break: break-all;
        }
        
        .thinking {
            font-style: italic;
            color: #888;
            margin-bottom: 5px;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(0,0,0,0.2);
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255,255,255,0.3);
        }
        
        /* Loading Animation */
        .typing-indicator {
            display: none;
            align-items: center;
            gap: 4px;
            padding: 12px 16px;
            background: rgba(255,255,255,0.1);
            border-radius: 16px 16px 16px 4px;
            width: fit-content;
        }
        
        .typing-indicator.active {
            display: flex;
        }
        
        .dot {
            width: 8px;
            height: 8px;
            background: #00d4ff;
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out;
        }
        
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
    </style>
</head>
<body>
    <div class="container">
        <aside class="sidebar">
            <div class="logo">CyberAI Pro</div>
            <div class="status-indicator">
                <span class="status-dot"></span>
                <span>Agent Online</span>
            </div>
            
            <div class="panel-title" style="margin-top: 30px;">Available Tools</div>
            <ul class="tool-list">
                <li onclick="setInput(\'run_command: \')">⚡ Run Command</li>
                <li onclick="setInput(\'read_file: \')">📄 Read File</li>
                <li onclick="setInput(\'write_file: \')">✏️ Write File</li>
                <li onclick="setInput(\'list_directory: \')">📁 List Directory</li>
                <li onclick="setInput(\'open_browser: \')">🌐 Open Browser</li>
            </ul>
            
            <div class="panel-title" style="margin-top: 30px;">Quick Actions</div>
            <ul class="tool-list">
                <li onclick="setInput(\'Create a file hello.txt\')">+ Create File</li>
                <li onclick="setInput(\'List current directory\')">+ List Files</li>
                <li onclick="setInput(\'Open notepad\')">+ Open Notepad</li>
                <li onclick="setInput(\'Open chrome\')">+ Open Chrome</li>
            </ul>
        </aside>
        
        <main class="main-area">
            <div class="chat-header">
                <h2>Agent Interface</h2>
                <p style="color: #888; font-size: 0.9em;">Type a command or goal. The AI will plan and execute automatically.</p>
            </div>
            
            <div class="chat-messages" id="chatMessages">
                <div class="message message-system">
                    <div class="bubble">Welcome to CyberAI Pro Agent System. Connected to WebSocket.</div>
                </div>
                
                <div class="typing-indicator" id="typingIndicator">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            </div>
            
            <div class="input-area">
                <input type="text" id="messageInput" placeholder="Enter command or goal..." 
                       onkeypress="if(event.key===\'Enter\')sendMessage()">
                <button id="sendBtn" onclick="sendMessage()">Send</button>
            </div>
        </main>
        
        <aside class="right-panel">
            <div class="panel-title">Execution Log</div>
            <div id="executionLog"></div>
        </aside>
    </div>
    
    <script>
        const sessionId = Math.random().toString(36).substring(7);
        let ws = null;
        let reconnectAttempts = 0;
        
        function connect() {
            const protocol = window.location.protocol === \'https:\' ? \'wss:\' : \'ws:\';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${sessionId}`);
            
            ws.onopen = () => {
                console.log(\'Connected\');
                reconnectAttempts = 0;
                addSystemMessage(\'Connected to agent\');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
            
            ws.onclose = () => {
                console.log(\'Disconnected\');
                addSystemMessage(\'Disconnected - reconnecting...\');
                if (reconnectAttempts < 5) {
                    reconnectAttempts++;
                    setTimeout(connect, 2000);
                }
            };
            
            ws.onerror = (error) => {
                console.error(\'WebSocket error:\', error);
            };
        }
        
        function handleMessage(data) {
            switch(data.type) {
                case \'user\':
                    addUserMessage(data.content);
                    break;
                case \'ai\':
                    addAIMessage(data.content);
                    break;
                case \'thinking\':
                    showTyping(true);
                    break;
                case \'step\':
                    addExecutionStep(data);
                    showTyping(false);
                    break;
                case \'complete\':
                    showTyping(false);
                    addSystemMessage(\'Task complete\');
                    break;
                case \'error\':
                    showTyping(false);
                    addSystemMessage(\'Error: \' + data.content);
                    break;
            }
        }
        
        function sendMessage() {
            const input = document.getElementById(\'messageInput\');
            const btn = document.getElementById(\'sendBtn\');
            const text = input.value.trim();
            
            if (!text || !ws) return;
            
            ws.send(JSON.stringify({goal: text}));
            input.value = \'\';
            btn.disabled = true;
            
            setTimeout(() => btn.disabled = false, 1000);
        }
        
        function setInput(text) {
            document.getElementById(\'messageInput\').value = text;
            document.getElementById(\'messageInput\').focus();
        }
        
        function addUserMessage(text) {
            const container = document.getElementById(\'chatMessages\');
            const indicator = document.getElementById(\'typingIndicator\');
            
            const msg = document.createElement(\'div\');
            msg.className = \'message message-user\';
            msg.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
            
            container.insertBefore(msg, indicator);
            scrollToBottom();
        }
        
        function addAIMessage(text) {
            const container = document.getElementById(\'chatMessages\');
            const indicator = document.getElementById(\'typingIndicator\');
            
            const msg = document.createElement(\'div\');
            msg.className = \'message message-ai\';
            msg.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
            
            container.insertBefore(msg, indicator);
            scrollToBottom();
        }
        
        function addSystemMessage(text) {
            const container = document.getElementById(\'chatMessages\');
            const indicator = document.getElementById(\'typingIndicator\');
            
            const msg = document.createElement(\'div\');
            msg.className = \'message message-system\';
            msg.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
            
            container.insertBefore(msg, indicator);
            scrollToBottom();
        }
        
        function addExecutionStep(data) {
            const container = document.getElementById(\'executionLog\');
            
            const step = document.createElement(\'div\');
            step.className = \'execution-step\' + (data.error ? \' error\' : \' success\');
            
            let html = \'\';
            if (data.thought) {
                html += `<div class="thinking">🤔 ${escapeHtml(data.thought)}</div>`;
            }
            html += `<div class="step-header">⚡ ${escapeHtml(data.action)}</div>`;
            if (data.input) {
                html += `<div class="step-content">${escapeHtml(data.input)}</div>`;
            }
            if (data.result) {
                html += `<div class="step-content" style="margin-top: 5px; color: ${data.success ? \'#00ff88\' : \'#ff4444\'};">${escapeHtml(data.result)}</div>`;
            }
            
            step.innerHTML = html;
            container.appendChild(step);
            container.scrollTop = container.scrollHeight;
        }
        
        function showTyping(show) {
            const indicator = document.getElementById(\'typingIndicator\');
            if (show) {
                indicator.classList.add(\'active\');
            } else {
                indicator.classList.remove(\'active\');
            }
        }
        
        function scrollToBottom() {
            const container = document.getElementById(\'chatMessages\');
            container.scrollTop = container.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement(\'div\');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Connect on load
        connect();
    </script>
</body>
</html>
'''

# Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve main UI."""
    return HTMLResponse(content=HTML_TEMPLATE)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket for real-time agent communication."""
    await websocket.accept()
    session_manager.connections[session_id] = websocket
    
    agent = session_manager.get_or_create_agent(session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            goal = message.get("goal", "")
            if not goal:
                continue
            
            # Send user message back to UI
            await websocket.send_json({
                "type": "user",
                "content": goal
            })
            
            # Show thinking indicator
            await websocket.send_json({"type": "thinking"})
            
            # Run agent (this blocks but we can stream results)
            results = agent.run(goal)
            
            # Send each step to UI
            for step in results:
                # Handle both dict and string results
                result_data = step.get("result", {})
                if isinstance(result_data, dict):
                    result_str = result_data.get("result", "")
                    success = result_data.get("success", False)
                    thought = result_data.get("thought", "")
                else:
                    result_str = str(result_data)
                    success = True
                    thought = ""
                
                await websocket.send_json({
                    "type": "step",
                    "step": step.get("step"),
                    "action": step.get("action"),
                    "input": step.get("input", ""),
                    "result": result_str,
                    "success": success,
                    "thought": thought,
                    "error": not success
                })
            
            # Send completion
            await websocket.send_json({"type": "complete"})
            
    except WebSocketDisconnect:
        log(f"[WebSocket] Client {session_id} disconnected")
        session_manager.remove_session(session_id)
    except Exception as e:
        log(f"[WebSocket] Error: {e}", "red")
        try:
            await websocket.send_json({
                "type": "error",
                "content": str(e)
            })
        except:
            pass
        session_manager.remove_session(session_id)

# REST API endpoints
@app.post("/api/run")
async def run_goal(goal: str):
    """Run a goal and return results."""
    agent = CyberAgent()
    results = agent.run(goal)
    return {"results": results}

@app.get("/api/status")
async def status():
    """Get system status."""
    return {
        "status": "online",
        "sessions": len(session_manager.agents),
        "version": "2.0"
    }

def run_server(host: str = "0.0.0.0", port: int = 7860):
    """Run the web server."""
    log(f"[Server] Starting on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_server()
