#!/usr/bin/env python3
"""
Web-based frontend for OS-Level AI Agent
Flask server with real-time chat interface
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import subprocess
import os
import json
import requests
import psutil
import socket
import re
from pathlib import Path
from typing import Dict, Any
import logging
from datetime import datetime
import threading
import queue

# Configuration
LM_STUDIO_URL = "http://10.184.27.52:1234"
MODEL_NAME = "qwen3-coder-30b"
AGENT_NAME = "ArchAgent"
LOG_FILE = "/tmp/arch_agent_web.log"
MAX_CONTEXT_TOKENS = 16384  # Model's context window
TARGET_CONTEXT_TOKENS = 12000  # Trigger summarization at 75% capacity

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global agent instance
agent = None

class OSAgent:
    def __init__(self):
        self.lm_studio_url = LM_STUDIO_URL
        self.session = requests.Session()
        self.session.timeout = 30
        self.conversation_history = []
        self.system_prompt = self._build_system_prompt()
        self.stop_requested = False
        self.tools = self._define_tools()
        
    def _define_tools(self) -> list:
        """Define available tools for LM Studio tool calling"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Execute a shell command and get the output. Use this for running system commands, installing packages, checking status, etc. ALWAYS use --noconfirm flag for package managers. Do NOT use 'sudo' prefix - you are already root.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to execute. Use --noconfirm for pacman, -y for apt/yum. Never use sudo."
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_background_command",
                    "description": "Start a long-running background process (servers, daemons, watch modes). The command will run in the background and won't block execution.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The command to run in the background"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or overwrite a file with content. Use this instead of text editors. You have root access to write anywhere.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "Absolute or relative path to the file"
                            },
                            "content": {
                                "type": "string",
                                "description": "The complete file content (do not use markdown code blocks)"
                            }
                        },
                        "required": ["filename", "content"]
                    }
                }
            }
        ]
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the AI agent"""
        system_info = self._get_system_info()
        return f"""You are {AGENT_NAME}, an AI assistant running on Arch Linux with full ROOT privileges.

SYSTEM INFORMATION:
{system_info}

CURRENT WORKING DIRECTORY: {os.getcwd()}

EXECUTION CONTEXT:
- You are running as ROOT (UID 0) - DO NOT use 'sudo' in commands
- ALL commands must be NON-INTERACTIVE (no user input prompts)
- ALWAYS use --noconfirm, -y, or equivalent flags for package managers

AVAILABLE TOOLS:
You have access to three tools via function calling:

1. execute_command(command): Run shell commands and see output
   - Use for: package installation, system commands, file operations, checks
   - Examples: "pacman -Syu --noconfirm", "ls -la", "systemctl status nginx"
   - Remember: NO sudo, ALWAYS --noconfirm for pacman

2. execute_background_command(command): Start long-running processes
   - Use for: servers, daemons, watch modes, blocking processes
   - Examples: "python3 -m http.server 8000", "npm run dev"

3. write_file(filename, content): Create/write files
   - Use for: creating configuration files, scripts, code
   - You have root access - can write anywhere
   - DO NOT use markdown code blocks in content

WORKFLOW:
- Use tools to perform all actions
- After each tool call, analyze the result before proceeding
- If a command fails, read the error and try to fix it
- Chain tool calls as needed to complete complex tasks
- Provide clear explanations of what you're doing
- **IMPORTANT: When you're done, respond WITHOUT making any more tool calls**

WHEN TO STOP MAKING TOOL CALLS:
- ✅ User's question has been fully answered
- ✅ User is just chatting casually (hello, thanks, etc.) - respond conversationally WITHOUT tools
- ✅ Task is complete and verified
- ✅ You have all the information needed to answer
- ✅ Files have been successfully created
- ✅ Commands executed successfully and you've confirmed it worked
- ❌ DON'T keep exploring or running commands "just to check" unless specifically asked
- ❌ DON'T run informational commands (ls, cat, file, etc.) unless user asks for that info

**TO STOP: Simply respond with text ONLY, without calling any tools. The conversation will end naturally.**

ERROR HANDLING:
- ALWAYS check tool call results for errors
- If a command fails, analyze the error message
- Try alternative approaches before giving up
- Explain what went wrong and what you're trying next

RESPONSE GUIDELINES:
- Do not just explain what to do - use tools to actually do it
- Be concise but informative
- Use tools whenever possible instead of showing code
- Explain your reasoning when making decisions
- Always use --noconfirm (or equivalent) for interactive commands
- Never use sudo (you're already root)

IMPORTANT: Use function calls to perform actions, not text instructions!
"""

    def _get_system_info(self) -> str:
        """Get current system information"""
        try:
            info = {
                "hostname": socket.gethostname(),
                "user": os.getenv("USER", "unknown"),
                "cwd": os.getcwd(),
                "cpu_count": psutil.cpu_count(),
                "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "disk_usage": f"{psutil.disk_usage('/').percent:.1f}%",
                "kernel": os.uname().release
            }
            return json.dumps(info, indent=2)
        except Exception as e:
            return f"Error getting system info: {e}"

    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a system command with sudo privileges"""
        logger.info(f"Executing: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out after 120 seconds",
                "output": "",
                "return_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "return_code": -1
            }

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def get_conversation_tokens(self) -> int:
        """Estimate total tokens in conversation history"""
        total = self.estimate_tokens(self.system_prompt)
        for msg in self.conversation_history:
            if isinstance(msg.get("content"), str):
                total += self.estimate_tokens(msg["content"])
            if "tool_calls" in msg:
                total += len(msg["tool_calls"]) * 100  # Rough estimate for tool calls
        return total
    
    def summarize_context(self):
        """Summarize old conversation when approaching token limit"""
        if len(self.conversation_history) < 6:
            return  # Need some history to summarize
        
        logger.info("Summarizing conversation context...")
        
        # Keep first user message and last 4 messages, summarize the middle
        first_msg = self.conversation_history[0]
        recent_msgs = self.conversation_history[-4:]
        to_summarize = self.conversation_history[1:-4]
        
        if not to_summarize:
            return
        
        # Build summary prompt
        conversation_text = "\n".join([
            f"{msg['role']}: {msg.get('content', '[tool call]')}"
            for msg in to_summarize
        ])
        
        summary_prompt = f"""Summarize this conversation concisely, focusing on:
1. What tasks were completed
2. Any important system changes made
3. Current state of the system
4. Any errors encountered and how they were resolved

Conversation to summarize:
{conversation_text}

Provide a brief summary (2-3 sentences):"""
        
        try:
            response = self.session.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": summary_prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200
                }
            )
            
            if response.status_code == 200:
                summary = response.json()["choices"][0]["message"]["content"]
                
                # Replace middle conversation with summary
                self.conversation_history = [
                    first_msg,
                    {"role": "system", "content": f"[Previous conversation summary: {summary}]"},
                    *recent_msgs
                ]
                logger.info(f"Context summarized. New length: {len(self.conversation_history)} messages")
        except Exception as e:
            logger.error(f"Failed to summarize context: {e}")
    
    def query_llm(self, prompt: str, use_tools: bool = True) -> dict:
        """Query LM Studio API with tool calling support"""
        try:
            # Check if we need to summarize
            current_tokens = self.get_conversation_tokens()
            if current_tokens > TARGET_CONTEXT_TOKENS:
                self.summarize_context()
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                *self.conversation_history,
                {"role": "user", "content": prompt}
            ]
            
            payload = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096,
                "stream": False
            }
            
            if use_tools:
                payload["tools"] = self.tools
            
            response = self.session.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                message = result["choices"][0]["message"]
                
                # Store user message
                self.conversation_history.append({"role": "user", "content": prompt})
                
                # Store assistant response
                if message.get("tool_calls"):
                    self.conversation_history.append({
                        "role": "assistant",
                        "tool_calls": message["tool_calls"],
                        "content": message.get("content") or ""
                    })
                else:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": message.get("content", "")
                    })
                
                return {
                    "success": True,
                    "message": message.get("content"),
                    "tool_calls": message.get("tool_calls", []),
                    "finish_reason": result["choices"][0].get("finish_reason")
                }
            else:
                return {
                    "success": False,
                    "error": f"LM Studio API error: {response.status_code} - {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Connection error to LM Studio: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Error querying LLM: {e}"}
    
    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call"""
        try:
            if tool_name == "execute_command":
                return self.execute_command(arguments["command"])
            
            elif tool_name == "execute_background_command":
                cmd = arguments["command"]
                try:
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    return {
                        "success": True,
                        "output": f"Background process started with PID {process.pid}",
                        "pid": process.pid,
                        "return_code": 0
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "output": "",
                        "return_code": -1
                    }
            
            elif tool_name == "write_file":
                filename = arguments["filename"]
                content = arguments["content"]
                
                # Clean content (remove markdown code blocks if present)
                cleaned_content = content.strip()
                if cleaned_content.startswith('```'):
                    lines = cleaned_content.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == '```':
                        lines = lines[:-1]
                    cleaned_content = '\n'.join(lines)
                
                # Create directory if needed
                dir_path = os.path.dirname(filename)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)
                
                with open(filename, 'w') as f:
                    f.write(cleaned_content)
                
                return {
                    "success": True,
                    "output": f"File written: {filename} ({len(cleaned_content)} bytes)",
                    "filename": filename,
                    "size": len(cleaned_content),
                    "return_code": 0
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                    "return_code": -1
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "return_code": -1
            }

    def process_request_streaming(self, user_input: str):
        """Generator that processes request with tool calling and yields SSE events"""
        def yield_event(event_type: str, data: dict):
            """Yield SSE formatted event"""
            event = {
                "type": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            return f"data: {json.dumps(event)}\n\n"
        
        # Check if stop was requested
        if self.stop_requested:
            yield yield_event("task_stopped", {"message": "Processing stopped by user"})
            self.stop_requested = False
            return
        
        # Initial AI query
        yield yield_event("ai_thinking", {})
        response = self.query_llm(user_input, use_tools=True)
        
        if not response["success"]:
            yield yield_event("error", {"message": response.get("error", "Unknown error")})
            return
        
        if response["message"]:
            yield yield_event("ai_response", {"message": response["message"]})
        
        # Process tool calls iteratively - LLM decides when to stop
        iteration = 0
        
        while response.get("tool_calls"):
            iteration += 1
            
            # Check stop again
            if self.stop_requested:
                yield yield_event("task_stopped", {"message": "Processing stopped by user"})
                self.stop_requested = False
                return
            
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    yield yield_event("error", {"message": f"Invalid tool arguments: {tool_call['function']['arguments']}"})
                    continue
                
                # Emit tool start event
                if tool_name == "execute_command":
                    yield yield_event("command_start", {"command": arguments["command"]})
                elif tool_name == "execute_background_command":
                    yield yield_event("background_command_start", {"command": arguments["command"]})
                elif tool_name == "write_file":
                    yield yield_event("file_write_start", {"filename": arguments["filename"]})
                
                # Execute tool
                result = self.execute_tool(tool_name, arguments)
                
                # Emit result event
                if tool_name == "execute_command":
                    yield yield_event("command_result", {
                        "command": arguments["command"],
                        "success": result["success"],
                        "output": result.get("output", ""),
                        "error": result.get("error", ""),
                        "return_code": result.get("return_code", 0)
                    })
                elif tool_name == "execute_background_command":
                    if result["success"]:
                        yield yield_event("background_command_started", {
                            "command": arguments["command"],
                            "pid": result.get("pid"),
                            "message": result["output"]
                        })
                    else:
                        yield yield_event("background_command_error", {
                            "command": arguments["command"],
                            "error": result["error"]
                        })
                elif tool_name == "write_file":
                    if result["success"]:
                        yield yield_event("file_write_success", {
                            "filename": arguments["filename"],
                            "content": arguments["content"]  # Full content, not just preview
                        })
                    else:
                        yield yield_event("file_write_error", {
                            "filename": arguments["filename"],
                            "error": result["error"]
                        })
                
                # Add tool result to conversation
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result)
                })
            
            # Get next AI response
            yield yield_event("ai_thinking", {})
            response = self.query_llm("", use_tools=True)
            
            if response.get("message"):
                yield yield_event("ai_response", {"message": response["message"]})
            
            if not response.get("tool_calls"):
                yield yield_event("task_complete", {"message": "Task completed"})
                break

    def get_system_status(self) -> dict:
        """Get current system status"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "hostname": socket.gethostname(),
                "user": os.getenv("USER"),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used // (1024**3),
                "memory_total_gb": memory.total // (1024**3),
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used // (1024**3),
                "disk_total_gb": disk.total // (1024**3),
                "load_average": list(os.getloadavg())
            }
        except Exception as e:
            return {"error": str(e)}

    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []


# Flask routes
@app.route('/')
def index():
    """Serve the main page"""
    return render_template('web_interface.html')

@app.route('/api/status')
def status():
    """Get system status"""
    return jsonify(agent.get_system_status())

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process chat message with streaming events"""
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    def generate_events():
        """Generator function for SSE"""
        try:
            # Process request with streaming - this handles everything
            for event in agent.process_request_streaming(user_message):
                yield event
            
            # Send end marker
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
        except Exception as e:
            logger.error(f"Error processing chat: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
    
    return Response(generate_events(), mimetype='text/event-stream')

@app.route('/api/clear', methods=['POST'])
def clear():
    """Clear conversation history"""
    agent.clear_conversation()
    return jsonify({"status": "cleared"})

@app.route('/api/stop', methods=['POST'])
def stop():
    """Stop current AI processing"""
    agent.stop_requested = True
    return jsonify({"status": "stop_requested"})

@app.route('/api/execute', methods=['POST'])
def execute():
    """Execute a direct command"""
    data = request.json
    command = data.get('command', '').strip()
    
    if not command:
        return jsonify({"error": "Empty command"}), 400
    
    try:
        result = agent.execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return jsonify({"error": str(e)}), 500


def test_connection(url: str) -> bool:
    """Test connection to LM Studio"""
    try:
        response = requests.get(f"{url}/v1/models", timeout=5)
        return response.status_code == 200
    except:
        return False


def main():
    """Main function"""
    global agent
    
    print("=" * 60)
    print(f"  {AGENT_NAME} - Web Interface")
    print("=" * 60)
    
    # Check if running with elevated privileges
    if os.geteuid() != 0:
        print("❌ Not running with elevated privileges!")
        print("🔧 Please run with sudo:")
        print(f"   sudo python3 {__file__}")
        return 1
    
    print("✅ Running with elevated privileges")
    
    agent = OSAgent()
    
    # Test LM Studio connection
    print("🔄 Testing connection to LM Studio...")
    if not test_connection(agent.lm_studio_url):
        print(f"❌ Cannot connect to LM Studio at {agent.lm_studio_url}")
        print("\n🔧 Troubleshooting:")
        print("  1. Make sure LM Studio is running")
        print("  2. Check that the model is loaded")
        print("  3. Verify the IP address in the script")
        return 1
    
    print("✅ LM Studio connected!")
    print("\n🌐 Starting web server...")
    print(f"📡 Access the interface at: http://localhost:5000")
    print(f"📡 Or from network: http://{socket.gethostname()}:5000")
    print("\nPress Ctrl+C to stop the server")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    
    return 0


if __name__ == "__main__":
    exit(main())
