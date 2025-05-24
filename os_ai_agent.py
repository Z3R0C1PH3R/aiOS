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

CURRENT WORKING DIRECTORY: {os.getcwd()}

COMMAND EXECUTION TAGS:

1. <COMMAND>command</COMMAND> - Execute command and see output automatically
   Example: <COMMAND>sudo pacman -S firefox</COMMAND>

2. <WRITEFILE filename="path/to/file">content</WRITEFILE> - Create/write files. This wont execute any commands.
   Example: <WRITEFILE filename="/etc/nginx/nginx.conf">server {{ listen 80; }}</WRITEFILE>
   Note: Do NOT wrap content in markdown code blocks (```python etc.)

3. <DONE>optional message</DONE> - Indicates you've completed the task
   Example: <DONE>Firefox has been successfully installed and configured</DONE>

WORKFLOW:
- ALWAYS use tags to perform actions - never just show code or instructions
- Use <COMMAND return_output="true">cmd</COMMAND> when you need to see output to continue
- Use <COMMAND return_output="false">cmd</COMMAND> for commands that don't need feedback
- Use <WRITEFILE> instead of nano/vim for creating files - DO NOT just show code blocks
- After commands with return_output="true", you'll receive the output and can continue
- End with <DONE> when your task is complete

CAPABILITIES:
- Execute shell commands and see their output
- Read/write files 
- Monitor system resources
- Install packages with pacman
- Manage services with systemctl
- Network operations
- Create system services, files, interact with the system etc.

SAFETY RULES:
- Be careful with sudo commands
- Don't delete anything important
- If you do not need to read any input always have a <DONE> tag
- Do NOT use markdown code blocks (```python) inside WRITEFILE tags

RESPONSE GUIDELINES:
- Do not tell the user how to do something, just do it
- ALWAYS use tags when creating files or running commands - never just show code
- When you need to write to a use <WRITEFILE> to actually create it
- When asked to run something, use <COMMAND> to actually execute it
- Make your responses clear and concise
- You can iterate and see command outputs to complete complex tasks
- If you do not need to read any input always have a <DONE> tag

IMPORTANT: Never just show code blocks - always use <WRITEFILE> and <COMMAND> tags to actually perform actions!
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
                timeout=120  # Increased timeout for package installations
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
        # Find all tags with their positions to maintain order
        all_tags = []
        
        # Extract COMMAND tags with return_output parameter
        command_pattern = r'<COMMAND\s+return_output="(true|false)">(.*?)</COMMAND>'
        for match in re.finditer(command_pattern, text, re.DOTALL | re.IGNORECASE):
            return_output = match.group(1).lower() == "true"
            cmd = match.group(2).strip()
            if cmd:
                all_tags.append((match.start(), 'command', (return_output, cmd)))
        
        # Extract legacy COMMAND tags (assume return_output=true for backward compatibility)
        legacy_command_pattern = r'<COMMAND>(.*?)</COMMAND>'
        for match in re.finditer(legacy_command_pattern, text, re.DOTALL | re.IGNORECASE):
            cmd = match.group(1).strip()
            if cmd:
                # Check if this isn't already captured by the parameterized pattern
                already_captured = any(tag[1] == 'command' and cmd in tag[2][1] 
                                     for tag in all_tags if tag[0] <= match.start() <= tag[0] + 100)
                if not already_captured:
                    all_tags.append((match.start(), 'command', (True, cmd)))
        
        # Extract WRITEFILE tags
        writefile_pattern = r'<WRITEFILE\s+filename="([^"]+)">(.*?)</WRITEFILE>'
        for match in re.finditer(writefile_pattern, text, re.DOTALL | re.IGNORECASE):
            filename = match.group(1).strip()
            content = match.group(2).strip()
            if filename:
                all_tags.append((match.start(), 'writefile', (filename, content)))
        
        # Check for DONE tag (AI is finished)
        done_pattern = r'<DONE>(.*?)</DONE>'
        done_messages = re.findall(done_pattern, text, re.DOTALL | re.IGNORECASE)
        
        # Sort tags by position to maintain order
        all_tags.sort(key=lambda x: x[0])
        
        # Separate into ordered lists
        commands_with_output = []
        writefiles = []
        
        for pos, tag_type, data in all_tags:
            if tag_type == 'command':
                commands_with_output.append(data)
            elif tag_type == 'writefile':
                writefiles.append(data)
        
        return {
            "commands_with_output": commands_with_output,
            "writefiles": writefiles,
            "done_messages": [msg.strip() for msg in done_messages if msg.strip()],
            "is_done": len(done_messages) > 0,
            "ordered_tags": all_tags  # For debugging/future use
        }

    def extract_commands(self, text: str) -> list:
        """Extract commands from <COMMAND> tags (legacy method)"""
        pattern = r'<COMMAND>(.*?)</COMMAND>'
        commands = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        return [cmd.strip() for cmd in commands if cmd.strip()]

    def execute_with_feedback(self, command: str) -> str:
        """Execute command and return formatted output for AI"""
        result = self.execute_command(command)
        
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

    def execute_and_show(self, command: str) -> None:
        """Execute command and display results"""
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
                print(f"Additional output: {result['output']}")

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

    def clear_conversation(self) -> None:
        """Clear the conversation history to start fresh"""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def process_response_with_iteration(self, ai_response: str) -> None:
        """Process AI response with automatic command execution and iteration until DONE"""
        print(f"\n🤖 {AGENT_NAME}: {ai_response}")
        
        # Extract all tags
        tags = self.extract_commands_and_tags(ai_response)
        
        # Step 1: Execute ALL commands and writefiles in order they appear
        commands_needing_feedback = []
        execution_successful = True
        
        if tags["ordered_tags"]:
            print(f"\n🔄 Processing {len(tags['ordered_tags'])} operation(s) in order...")
            
            for pos, tag_type, data in tags["ordered_tags"]:
                if tag_type == 'command':
                    return_output, cmd = data
                    print(f"\n🔧 Executing: {cmd}")
                    print(f"   📊 Return output to AI: {'Yes' if return_output else 'No'}")
                    
                    result = self.execute_command(cmd)
                    
                    # Show clear output to user
                    if result["success"]:
                        if result["output"].strip():
                            print(f"✅ Command Output:")
                            print("─" * 50)
                            print(result["output"])
                            print("─" * 50)
                        else:
                            print("✅ Command completed successfully (no output)")
                    else:
                        print(f"❌ Command failed with error:")
                        print("─" * 50)
                        print(f"Error: {result['error']}")
                        if result["output"]:
                            print(f"Output: {result['output']}")
                        print("─" * 50)
                        execution_successful = False
                    
                    # Collect output for AI feedback if needed (regardless of success)
                    if return_output:
                        formatted_output = self.execute_with_feedback(cmd)
                        commands_needing_feedback.append(formatted_output)
                
                elif tag_type == 'writefile':
                    filename, content = data
                    print(f"\n📝 Writing file: {filename}")
                    try:
                        # Clean content - remove markdown code blocks if present
                        cleaned_content = content.strip()
                        if cleaned_content.startswith('```python'):
                            cleaned_content = cleaned_content[9:]  # Remove ```python
                        if cleaned_content.startswith('```'):
                            cleaned_content = cleaned_content[3:]   # Remove ```
                        if cleaned_content.endswith('```'):
                            cleaned_content = cleaned_content[:-3]  # Remove trailing ```
                        cleaned_content = cleaned_content.strip()
                        
                        # Create directory if it doesn't exist (only if filename has a directory path)
                        dir_path = os.path.dirname(filename)
                        if dir_path:  # Only create directories if there's actually a directory path
                            os.makedirs(dir_path, exist_ok=True)
                        
                        with open(filename, 'w') as f:
                            f.write(cleaned_content)
                        print(f"✅ File '{filename}' written successfully")
                        print("📄 File content preview:")
                        print("─" * 50)
                        print(cleaned_content[:200] + ("..." if len(cleaned_content) > 200 else ""))
                        print("─" * 50)
                    except Exception as e:
                        print(f"❌ Error writing file '{filename}': {e}")
                        execution_successful = False
        
        # Step 2: Handle DONE messages (task completion)
        if tags["is_done"]:
            print(f"\n✅ Task completed!")
            for msg in tags["done_messages"]:
                if msg:
                    print(f"📝 Final message: {msg}")
            return  # Exit without continuing iteration
        
        # Step 3: Send feedback to AI only if there were commands needing feedback
        if commands_needing_feedback:
            feedback_prompt = (
                "Here are the results of the commands you requested:\n\n" +
                "\n\n---\n\n".join(commands_needing_feedback) +
                "\n\nPlease continue with your task. Use <COMMAND return_output=\"true\">cmd</COMMAND> "
                "for commands you need output from, <COMMAND return_output=\"false\">cmd</COMMAND> "
                "for commands without feedback, <WRITEFILE filename=\"path\">content</WRITEFILE> "
                "for files, or <DONE>message</DONE> when finished."
            )
            
            print("\n🔄 Sending command results to AI...")
            print("📤 AI Prompt:")
            print("─" * 50)
            print(feedback_prompt)
            print("─" * 50)
            
            print("\n🤔 AI is analyzing the output...")
            next_response = self.query_llm(feedback_prompt)
            self.process_response_with_iteration(next_response)
        
        # Step 4: If there were operations but no commands needing feedback, still continue if not done
        elif tags["ordered_tags"] and not tags["is_done"]:
            feedback_prompt = (
                f"Operations completed successfully. Please continue with your task or use <DONE>message</DONE> when finished."
            )
            
            print("\n🔄 Notifying AI that operations completed...")
            print("📤 AI Prompt:")
            print("─" * 50)
            print(feedback_prompt)
            print("─" * 50)
            
            print("\n🤔 AI continuing...")
            next_response = self.query_llm(feedback_prompt)
            self.process_response_with_iteration(next_response)

    def process_response(self, ai_response: str) -> None:
        """Process AI response and handle command execution"""
        print(f"\n🤖 {AGENT_NAME}: {ai_response}")
        
        # Extract commands from response
        commands = self.extract_commands(ai_response)
        
        if commands:
            print(f"\n🔍 Found {len(commands)} command(s) to execute:")
            for i, cmd in enumerate(commands, 1):
                print(f"  {i}. {cmd}")
            
            # Ask for confirmation
            while True:
                choice = input(f"\n❓ Execute commands? (y)es/(n)o/(s)elective: ").lower().strip()
                
                if choice in ['y', 'yes']:
                    print()
                    for cmd in commands:
                        self.execute_and_show(cmd)
                    break
                elif choice in ['n', 'no']:
                    print("❌ Command execution cancelled")
                    break
                elif choice in ['s', 'selective']:
                    print()
                    for cmd in commands:
                        exec_choice = input(f"Execute '{cmd}'? (y/n): ").lower().strip()
                        if exec_choice in ['y', 'yes']:
                            self.execute_and_show(cmd)
                    break
                else:
                    print("Please enter 'y', 'n', or 's'")

    def show_system_status(self) -> None:
        """Display current system status"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            print(f"""
📊 System Status:
├─ Hostname: {socket.gethostname()}
├─ User: {os.getenv("USER")}
├─ CPU Usage: {cpu_percent}%
├─ Memory: {memory.percent}% ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)
├─ Disk: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)
└─ Load Average: {', '.join(map(str, os.getloadavg()))}
""")
        except Exception as e:
            print(f"Error getting system status: {e}")

    def interactive_mode(self):
        """Run the agent in interactive mode"""
        print(f"🚀 {AGENT_NAME} started successfully!")
        print(f"🔗 Connected to: {self.lm_studio_url}")
        print("\n📋 Commands:")
        print("  • Type your request in natural language")
        print("  • 'status' - Show system information")
        print("  • 'clear' - Clear conversation history")
        print("  • 'exit' - Quit the agent")
        print("  • '!command' - Execute command directly")
        print("\n🏷️  AI can now use these tags:")
        print("  • <COMMAND return_output=\"true\">cmd</COMMAND> - Auto-execute and return output to AI")
        print("  • <COMMAND return_output=\"false\">cmd</COMMAND> - Auto-execute without AI feedback")
        print("  • <WRITEFILE filename=\"path\">content</WRITEFILE> - Create/write files")
        print("  • <DONE>message</DONE> - Task completed")
        print("-" * 60)
        
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
                self.process_response_with_iteration(ai_response)
                
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
    exit(main())