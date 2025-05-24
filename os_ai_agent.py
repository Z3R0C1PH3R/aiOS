#!/usr/bin/env python3
"""
OS-Level AI Agent for ACOMMAND EXECUTION TAGS:

1. <COMMAND return_output="true">command</COMMAND> - Execute command and return output to AI for analysis
   Example: <COMMAND return_output="true">ls -la /etc</COMMAND>

2. <COMMAND return_output="false">command</COMMAND> - Execute command without returning output to AI
   Example: <COMMAND return_output="false">sudo systemctl start nginx</COMMAND>

3. <WRITEFILE filename="path/to/file">content</WRITEFILE> - Create/write files
   Example: <WRITEFILE filename="/etc/nginx/nginx.conf">server {{ listen 80; }}</WRITEFILE>

4. <DONE>optional message</DONE> - Indicates you've completed the task
   Example: <DONE>Firefox has been successfully installed and configured</DONE>Connects to LM Studio running Qwen2.5 Coder 7B
"""

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

# Configuration
LM_STUDIO_URL = "http://192.168.1.100:1234"  # Change to your laptop's IP
MODEL_NAME = "qwen2.5-coder-7b"
AGENT_NAME = "ArchAgent"
LOG_FILE = "/tmp/arch_agent.log"

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

class OSAgent:
    def __init__(self):
        self.lm_studio_url = LM_STUDIO_URL
        self.session = requests.Session()
        self.session.timeout = 30
        self.conversation_history = []
        self.system_prompt = self._build_system_prompt()
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the AI agent"""
        system_info = self._get_system_info()
        return f"""You are {AGENT_NAME}, an AI assistant running on Arch Linux with full system access.

SYSTEM INFORMATION:
{system_info}

CAPABILITIES:
- Execute shell commands using execute_command()
- Read/write files using file operations
- Monitor system resources
- Install packages with pacman
- Manage services with systemctl
- Network operations
- Create system services, files, interact with the system etc.

SAFETY RULES:
- Be careful with sudo commands
- Ask before making major system changes

RESPONSE FORMAT:
- For commands: Provide the exact command to run
- For file operations: Specify full paths
- For complex tasks: Break into steps
- Always explain what you're doing

You can execute commands by requesting them clearly. The user will see both your response and command outputs.
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
        """Execute a system command safely"""
        logger.info(f"Executing: {command}")
        
        # Safety checks for dangerous commands
        dangerous_patterns = [
            'rm -rf /', 'dd if=', 'mkfs', 'fdisk /dev/', 'parted /dev/',
            'format', 'del /f', '> /dev/', 'chmod 777 /'
        ]
        
        if any(pattern in command.lower() for pattern in dangerous_patterns):
            return {
                "success": False,
                "error": f"Dangerous command blocked: {command}",
                "output": "",
                "return_code": -1
            }
        
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
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out",
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

    def read_file(self, filepath: str, max_lines: int = 100) -> str:
        """Read file contents safely"""
        try:
            path = Path(filepath)
            if not path.exists():
                return f"File not found: {filepath}"
            
            if path.stat().st_size > 1024 * 1024:  # 1MB limit
                return f"File too large: {filepath}"
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                if len(lines) > max_lines:
                    content = ''.join(lines[:max_lines])
                    content += f"\n... (truncated, {len(lines)} total lines)"
                else:
                    content = ''.join(lines)
                return content
        except Exception as e:
            return f"Error reading file: {e}"

    def write_file(self, filepath: str, content: str) -> str:
        """Write content to file safely"""
        try:
            path = Path(filepath)
            # Don't overwrite system files
            system_dirs = ['/bin', '/sbin', '/usr/bin', '/usr/sbin', '/etc']
            if any(str(path).startswith(sdir) for sdir in system_dirs):
                return f"Cannot write to system directory: {filepath}"
            
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {filepath}"
        except Exception as e:
            return f"Error writing file: {e}"

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
                "max_tokens": 2048,
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
                
                # Keep conversation history manageable (last 10 exchanges)
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
                return ai_response
            else:
                return f"LM Studio API error: {response.status_code} - {response.text}"
                
        except requests.exceptions.RequestException as e:
            return f"Connection error to LM Studio: {e}"
        except Exception as e:
            return f"Error querying LLM: {e}"

    def process_ai_response(self, ai_response: str) -> None:
        """Process AI response and execute any commands"""
        print(f"\n🤖 {AGENT_NAME}: {ai_response}\n")
        
        # Look for command patterns
        lines = ai_response.split('\n')
        for line in lines:
            # Detect command suggestions (various formats)
            if any(pattern in line.lower() for pattern in ['run:', 'execute:', 'command:', '$ ', '# ']):
                # Extract command
                for prefix in ['run:', 'execute:', 'command:', '$ ', '# ']:
                    if prefix in line.lower():
                        cmd = line.split(prefix, 1)[-1].strip()
                        if cmd and not cmd.startswith('#'):  # Skip comments
                            self.execute_and_show(cmd)
                        break

    def execute_and_show(self, command: str) -> None:
        """Execute command and show results"""
        print(f"🔧 Executing: {command}")
        result = self.execute_command(command)
        
        if result["success"]:
            if result["output"].strip():
                print(f"✅ Output:\n{result['output']}")
            else:
                print("✅ Command completed successfully")
        else:
            print(f"❌ Error: {result['error']}")
            if result["output"]:
                print(f"Output: {result['output']}")

    def interactive_mode(self):
        """Run the agent in interactive mode"""
        print(f"🚀 {AGENT_NAME} starting...")
        print(f"Connected to LM Studio at: {self.lm_studio_url}")
        print("Type 'exit', 'quit', or 'bye' to stop the agent")
        print("Type 'clear' to clear conversation history")
        print("Type 'status' to see system status")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if not user_input:
                    continue
                    
                # Handle special commands
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == 'clear':
                    self.clear_conversation()
                    print("🧹 Conversation history cleared")
                    continue
                elif user_input.lower() == 'status':
                    self.show_system_status()
                    continue
                elif user_input.startswith('!'):
                    # Direct command execution
                    cmd = user_input[1:].strip()
                    if cmd:
                        self.execute_and_show(cmd)
                    continue
                
                # Query the AI
                print("🤔 Thinking...")
                ai_response = self.query_llm(user_input)
                self.process_ai_response(ai_response)
                
            except KeyboardInterrupt:
                print("\n\n👋 Agent stopped by user (Ctrl+C)")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                print(f"❌ Unexpected error: {e}")

def test_connection(url: str) -> bool:
    """Test connection to LM Studio"""
    try:
        response = requests.get(f"{url}/v1/models", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Main function"""
    print("=" * 60)
    print(f"  {AGENT_NAME} - OS-Level AI Agent for Arch Linux")
    print("=" * 60)
    
    # Security warning
    if os.geteuid() == 0:
        print("⚠️  WARNING: Running as root! Be extra careful with commands.")
    
    agent = OSAgent()
    
    # Test LM Studio connection
    print("🔄 Testing connection to LM Studio...")
    if not test_connection(agent.lm_studio_url):
        print(f"❌ Cannot connect to LM Studio at {agent.lm_studio_url}")
        print("\n🔧 Troubleshooting:")
        print("  1. Make sure LM Studio is running")
        print("  2. Check that Qwen2.5 Coder 7B is loaded")
        print("  3. Verify the IP address in the script")
        print("  4. Ensure firewall allows the connection")
        return 1
    
    # Test AI response
    print("🧠 Testing AI connection...")
    test_response = agent.query_llm("Hello! Please respond with: <COMMAND>echo 'AI connection test'</COMMAND>")
    if "error" in test_response.lower():
        print(f"❌ AI test failed: {test_response}")
        return 1
    
    print("✅ All systems ready!")
    agent.interactive_mode()
    return 0

if __name__ == "__main__":
    main()
