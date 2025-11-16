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
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the AI agent"""
        system_info = self._get_system_info()
        return f"""You are {AGENT_NAME}, an AI assistant running on Arch Linux with full ROOT privileges.

SYSTEM INFORMATION:
{system_info}

CURRENT WORKING DIRECTORY: {os.getcwd()}

⚠️ EXECUTION CONTEXT:
- You are running as ROOT (UID 0) - No need to use 'sudo' in commands
- ALL commands must be NON-INTERACTIVE (no user input prompts)
- ALWAYS use --noconfirm, -y, or equivalent flags for package managers and interactive tools

COMMAND EXECUTION TAGS:

1. <COMMAND>command</COMMAND> - Execute command and see output automatically
   Example: <COMMAND>pacman -Syu --noconfirm</COMMAND>
   Example: <COMMAND>pacman -S firefox --noconfirm</COMMAND>
   ❌ WRONG: <COMMAND>sudo pacman -S firefox</COMMAND> (no sudo needed!)
   ❌ WRONG: <COMMAND>pacman -S firefox</COMMAND> (missing --noconfirm!)

2. <COMMAND_BACKGROUND>command</COMMAND_BACKGROUND> - Run long-running/blocking commands (servers, watch mode, etc.)
   Example: <COMMAND_BACKGROUND>python3 -m http.server 8000</COMMAND_BACKGROUND>
   Example: <COMMAND_BACKGROUND>npm run dev</COMMAND_BACKGROUND>

3. <WRITEFILE filename="path/to/file">content</WRITEFILE> - Create/write files directly
   Example: <WRITEFILE filename="/etc/nginx/nginx.conf">server {{ listen 80; }}</WRITEFILE>
   Note: Do NOT wrap content in markdown code blocks (```python etc.)
   Note: You have root access - can write anywhere on the system

4. <DONE>optional message</DONE> - Indicates you've completed the task
   Example: <DONE>Firefox has been successfully installed and configured</DONE>

WORKFLOW:
- ALWAYS use tags to perform actions - never just show code or instructions
- Use <COMMAND>cmd</COMMAND> to execute commands and see their output
- Use <COMMAND_BACKGROUND> for servers, daemons, watch modes, or any blocking process
- Use <WRITEFILE> instead of nano/vim for creating files - DO NOT just show code blocks
- After commands, you'll receive the output and can continue
- If a command FAILS, analyze the error and try to fix it before giving up
- End with <DONE> when your task is complete

ERROR HANDLING:
- ALWAYS check command outputs for errors
- If a command fails, read the error message carefully
- Try alternative approaches or fix the issue before continuing
- Don't ignore failed commands - they need to be resolved

CAPABILITIES:
- Execute ANY shell command with root privileges (no sudo needed)
- Run background processes (servers, daemons)
- Read/write ANY file on the system (root access)
- Monitor system resources
- Install packages with pacman (always use --noconfirm)
- Manage services with systemctl
- Network operations
- Modify system configuration files
- Create system services, users, groups, etc.

RESPONSE GUIDELINES:
- Do not tell the user how to do something, just do it
- ALWAYS use tags when creating files or running commands - never just show code
- When you need to write to a file, use <WRITEFILE> to actually create it
- When asked to run something, use <COMMAND> to actually execute it
- Make your responses clear and concise
- You can iterate and see command outputs to complete complex tasks
- MUST analyze errors and retry/fix failed commands
- ALWAYS include --noconfirm (or equivalent) for any interactive command
- NEVER use sudo (you're already root)
- Always end with <DONE> when task is complete
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

    def extract_commands_and_tags(self, text: str) -> dict:
        """Extract commands and special tags from AI response in order"""
        all_tags = []
        
        # Extract COMMAND_BACKGROUND tags (check this first to avoid conflicts)
        bg_command_pattern = r'<COMMAND_BACKGROUND>(.*?)</COMMAND_BACKGROUND>'
        for match in re.finditer(bg_command_pattern, text, re.DOTALL | re.IGNORECASE):
            cmd = match.group(1).strip()
            if cmd:
                all_tags.append((match.start(), 'command_background', cmd))
        
        # Extract regular COMMAND tags
        command_pattern = r'<COMMAND>(.*?)</COMMAND>'
        for match in re.finditer(command_pattern, text, re.DOTALL | re.IGNORECASE):
            # Skip if this is part of COMMAND_BACKGROUND
            if '<COMMAND_BACKGROUND>' not in text[max(0, match.start()-20):match.start()]:
                cmd = match.group(1).strip()
                if cmd:
                    all_tags.append((match.start(), 'command', cmd))
        
        # Extract WRITEFILE tags
        writefile_pattern = r'<WRITEFILE\s+filename="([^"]+)">(.*?)</WRITEFILE>'
        for match in re.finditer(writefile_pattern, text, re.DOTALL | re.IGNORECASE):
            filename = match.group(1).strip()
            content = match.group(2).strip()
            if filename:
                all_tags.append((match.start(), 'writefile', (filename, content)))
        
        # Check for DONE tag
        done_pattern = r'<DONE>(.*?)</DONE>'
        done_messages = re.findall(done_pattern, text, re.DOTALL | re.IGNORECASE)
        
        # Sort tags by position
        all_tags.sort(key=lambda x: x[0])
        
        return {
            "ordered_tags": all_tags,
            "done_messages": [msg.strip() for msg in done_messages if msg.strip()],
            "is_done": len(done_messages) > 0
        }

    def query_llm(self, prompt: str) -> str:
        """Query the LM Studio API"""
        try:
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    *self.conversation_history,
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 8192,
                "stream": False
            }
            
            response = self.session.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result["choices"][0]["message"]["content"]
                
                # Store conversation
                self.conversation_history.append({"role": "user", "content": prompt})
                self.conversation_history.append({"role": "assistant", "content": ai_response})
                
                # Keep conversation history manageable
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
                return ai_response
            else:
                return f"LM Studio API error: {response.status_code} - {response.text}"
                
        except requests.exceptions.RequestException as e:
            return f"Connection error to LM Studio: {e}"
        except Exception as e:
            return f"Error querying LLM: {e}"

    def process_request(self, user_input: str) -> dict:
        """Process user request and return structured response"""
        events = []
        
        def add_event(event_type: str, data: dict):
            events.append({
                "type": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            })
        
        # Query AI
        add_event("ai_thinking", {})
        ai_response = self.query_llm(user_input)
        add_event("ai_response", {"message": ai_response})
        
        # Process response iteratively
        self._process_with_iteration(ai_response, add_event)
        
        return {"events": events}

    def _process_with_iteration(self, ai_response: str, add_event):
        """Process AI response with iteration"""
        tags = self.extract_commands_and_tags(ai_response)
        
        # Execute all operations
        commands_needing_feedback = []
        has_errors = False
        
        for pos, tag_type, data in tags["ordered_tags"]:
            if tag_type == 'command':
                cmd = data
                add_event("command_start", {"command": cmd})
                
                result = self.execute_command(cmd)
                
                add_event("command_result", {
                    "command": cmd,
                    "success": result["success"],
                    "output": result["output"],
                    "error": result["error"],
                    "return_code": result["return_code"]
                })
                
                # Collect output for AI feedback
                formatted_output = self._format_command_result(cmd, result)
                commands_needing_feedback.append(formatted_output)
                
                if not result["success"]:
                    has_errors = True
            
            elif tag_type == 'command_background':
                cmd = data
                add_event("background_command_start", {"command": cmd})
                
                # Start background process
                try:
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    add_event("background_command_started", {
                        "command": cmd,
                        "pid": process.pid,
                        "message": f"Background process started with PID {process.pid}"
                    })
                    commands_needing_feedback.append(
                        f"Background Command: {cmd}\nStatus: Started successfully with PID {process.pid}"
                    )
                except Exception as e:
                    add_event("background_command_error", {
                        "command": cmd,
                        "error": str(e)
                    })
                    commands_needing_feedback.append(
                        f"Background Command: {cmd}\nError: {str(e)}"
                    )
                    has_errors = True
            
            elif tag_type == 'writefile':
                filename, content = data
                add_event("file_write_start", {"filename": filename})
                
                try:
                    # Clean content
                    cleaned_content = content.strip()
                    if cleaned_content.startswith('```python'):
                        cleaned_content = cleaned_content[9:]
                    if cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]
                    cleaned_content = cleaned_content.strip()
                    
                    # Check if content seems truncated
                    is_truncated = (
                        cleaned_content.endswith('...') or
                        (filename.endswith('.html') and not cleaned_content.endswith('</html>')) or
                        (filename.endswith('.py') and cleaned_content.count('def ') != cleaned_content.count('    return'))
                    )
                    
                    # Create directory if needed
                    dir_path = os.path.dirname(filename)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    with open(filename, 'w') as f:
                        f.write(cleaned_content)
                    
                    if is_truncated:
                        add_event("file_write_warning", {
                            "filename": filename,
                            "preview": cleaned_content[:200],
                            "warning": "File content may be truncated"
                        })
                        commands_needing_feedback.append(
                            f"File Written: {filename}\nStatus: SUCCESS but content appears TRUNCATED\n"
                            f"⚠️ The file content may be incomplete. Consider writing smaller files or splitting content."
                        )
                        has_errors = True
                    else:
                        add_event("file_write_success", {
                            "filename": filename,
                            "preview": cleaned_content[:200]
                        })
                        commands_needing_feedback.append(
                            f"File Written: {filename}\nStatus: Success\nSize: {len(cleaned_content)} bytes"
                        )
                except Exception as e:
                    add_event("file_write_error", {
                        "filename": filename,
                        "error": str(e)
                    })
                    commands_needing_feedback.append(
                        f"File Write: {filename}\nError: {str(e)}"
                    )
                    has_errors = True
        
        # Handle completion
        if tags["is_done"]:
            for msg in tags["done_messages"]:
                if msg:
                    add_event("task_complete", {"message": msg})
            return
        
        # Continue iteration if needed
        if commands_needing_feedback:
            # Emphasize errors if any occurred
            if has_errors:
                feedback_prompt = (
                    "⚠️ ATTENTION: Some commands/operations FAILED. You MUST fix these errors before proceeding.\n\n"
                    "Results:\n\n" +
                    "\n\n---\n\n".join(commands_needing_feedback) +
                    "\n\n🔴 CRITICAL: Analyze the errors above and fix them. Do not ignore failed commands!\n"
                    "Use <COMMAND> to retry or fix issues, or use <DONE>message</DONE> if the task cannot be completed."
                )
            else:
                feedback_prompt = (
                    "All operations completed successfully. Results:\n\n" +
                    "\n\n---\n\n".join(commands_needing_feedback) +
                    "\n\nPlease continue with your task or use <DONE>message</DONE> when finished."
                )
            
            add_event("ai_thinking", {})
            next_response = self.query_llm(feedback_prompt)
            add_event("ai_response", {"message": next_response})
            
            # Recursive iteration
            self._process_with_iteration(next_response, add_event)

    def _process_with_iteration_streaming(self, ai_response: str):
        """Generator that processes AI response and yields SSE events"""
        def add_event(event_type: str, data: dict):
            """Helper to format and yield SSE events"""
            event = {
                "type": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            return f"data: {json.dumps(event)}\n\n"
        
        # Process the response with iteration
        yield from self._process_iteration_generator(ai_response, add_event)
    
    def _process_iteration_generator(self, ai_response: str, add_event):
        """Generator version of _process_with_iteration"""
        # Check if stop was requested
        if self.stop_requested:
            yield add_event("task_stopped", {"message": "Processing stopped by user"})
            self.stop_requested = False
            return
        
        tags = self.extract_commands_and_tags(ai_response)
        
        # Execute all operations
        commands_needing_feedback = []
        has_errors = False
        
        for pos, tag_type, data in tags["ordered_tags"]:
            if tag_type == 'command':
                cmd = data
                yield add_event("command_start", {"command": cmd})
                
                result = self.execute_command(cmd)
                
                yield add_event("command_result", {
                    "command": cmd,
                    "success": result["success"],
                    "output": result["output"],
                    "error": result["error"],
                    "return_code": result["return_code"]
                })
                
                # Collect output for AI feedback
                formatted_output = self._format_command_result(cmd, result)
                commands_needing_feedback.append(formatted_output)
                
                if not result["success"]:
                    has_errors = True
            
            elif tag_type == 'command_background':
                cmd = data
                yield add_event("background_command_start", {"command": cmd})
                
                # Start background process
                try:
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    yield add_event("background_command_started", {
                        "command": cmd,
                        "pid": process.pid,
                        "message": f"Background process started with PID {process.pid}"
                    })
                    commands_needing_feedback.append(
                        f"Background Command: {cmd}\nStatus: Started successfully with PID {process.pid}"
                    )
                except Exception as e:
                    yield add_event("background_command_error", {
                        "command": cmd,
                        "error": str(e)
                    })
                    commands_needing_feedback.append(
                        f"Background Command: {cmd}\nError: {str(e)}"
                    )
                    has_errors = True
            
            elif tag_type == 'writefile':
                filename, content = data
                yield add_event("file_write_start", {"filename": filename})
                
                try:
                    # Clean content
                    cleaned_content = content.strip()
                    if cleaned_content.startswith('```python'):
                        cleaned_content = cleaned_content[9:]
                    if cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]
                    cleaned_content = cleaned_content.strip()
                    
                    # Check if content seems truncated
                    is_truncated = (
                        cleaned_content.endswith('...') or
                        (filename.endswith('.html') and not cleaned_content.endswith('</html>')) or
                        (filename.endswith('.py') and cleaned_content.count('def ') != cleaned_content.count('    return'))
                    )
                    
                    # Create directory if needed
                    dir_path = os.path.dirname(filename)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    with open(filename, 'w') as f:
                        f.write(cleaned_content)
                    
                    if is_truncated:
                        yield add_event("file_write_warning", {
                            "filename": filename,
                            "preview": cleaned_content[:200],
                            "warning": "File content may be truncated"
                        })
                        commands_needing_feedback.append(
                            f"File Written: {filename}\nStatus: SUCCESS but content appears TRUNCATED\n"
                            f"⚠️ The file content may be incomplete. Consider writing smaller files or splitting content."
                        )
                        has_errors = True
                    else:
                        yield add_event("file_write_success", {
                            "filename": filename,
                            "preview": cleaned_content[:200]
                        })
                        commands_needing_feedback.append(
                            f"File Written: {filename}\nStatus: Success\nSize: {len(cleaned_content)} bytes"
                        )
                except Exception as e:
                    yield add_event("file_write_error", {
                        "filename": filename,
                        "error": str(e)
                    })
                    commands_needing_feedback.append(
                        f"File Write: {filename}\nError: {str(e)}"
                    )
                    has_errors = True
        
        # Handle completion
        if tags["is_done"]:
            for msg in tags["done_messages"]:
                if msg:
                    yield add_event("task_complete", {"message": msg})
            return
        
        # Continue iteration if needed
        if commands_needing_feedback:
            # Emphasize errors if any occurred
            if has_errors:
                feedback_prompt = (
                    "⚠️ ATTENTION: Some commands/operations FAILED. You MUST fix these errors before proceeding.\n\n"
                    "Results:\n\n" +
                    "\n\n---\n\n".join(commands_needing_feedback) +
                    "\n\n🔴 CRITICAL: Analyze the errors above and fix them. Do not ignore failed commands!\n"
                    "Use <COMMAND> to retry or fix issues, or use <DONE>message</DONE> if the task cannot be completed."
                )
            else:
                feedback_prompt = (
                    "All operations completed successfully. Results:\n\n" +
                    "\n\n---\n\n".join(commands_needing_feedback) +
                    "\n\nPlease continue with your task or use <DONE>message</DONE> when finished."
                )
            
            yield add_event("ai_thinking", {})
            next_response = self.query_llm(feedback_prompt)
            yield add_event("ai_response", {"message": next_response})
            
            # Recursive iteration
            yield from self._process_iteration_generator(next_response, add_event)

    def _format_command_result(self, command: str, result: dict) -> str:
        """Format command result for AI feedback"""
        output_parts = [f"Command: {command}"]
        
        if result["success"]:
            if result["output"].strip():
                output_parts.append(f"Output:\n{result['output']}")
            else:
                output_parts.append("Command completed successfully (no output)")
        else:
            output_parts.append(f"Error: {result['error']}")
            if result["output"]:
                output_parts.append(f"Additional output: {result['output']}")
        
        output_parts.append(f"Return code: {result['return_code']}")
        return "\n".join(output_parts)

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
            # AI thinking
            yield f"data: {json.dumps({'type': 'ai_thinking', 'timestamp': datetime.now().isoformat(), 'data': {}})}\n\n"
            
            # Query AI
            ai_response = agent.query_llm(user_message)
            yield f"data: {json.dumps({'type': 'ai_response', 'timestamp': datetime.now().isoformat(), 'data': {'message': ai_response}})}\n\n"
            
            # Process response iteratively - yield from the generator
            for event in agent._process_with_iteration_streaming(ai_response):
                yield event
            
            # Send end marker
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
        except Exception as e:
            logger.error(f"Error processing chat: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
    
    return Response(generate_events(), mimetype='text/event-stream')

@app.route('/api/chat-legacy', methods=['POST'])
def chat_legacy():
    """Legacy non-streaming endpoint"""
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    try:
        result = agent.process_request(user_message)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error processing chat: {e}")
        return jsonify({"error": str(e)}), 500

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
