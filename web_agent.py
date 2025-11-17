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
    
    def _format_size(self, size_bytes: int) -> str:
        """Convert bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
        
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
                    "name": "read_file",
                    "description": "Read file contents. Can read entire file or specific line ranges. Use this before editing to see current content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "Absolute or relative path to the file to read"
                            },
                            "start_line": {
                                "type": "integer",
                                "description": "Optional: Starting line number (1-indexed). Omit to read entire file.",
                                "minimum": 1
                            },
                            "end_line": {
                                "type": "integer",
                                "description": "Optional: Ending line number (1-indexed, inclusive). Only used with start_line.",
                                "minimum": 1
                            }
                        },
                        "required": ["filename"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Edit a file with multiple operations: write (overwrite entire file), append (add to end), insert (add at specific line), or replace (find & replace text). Choose the operation that best fits your need.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "Absolute or relative path to the file"
                            },
                            "operation": {
                                "type": "string",
                                "enum": ["write", "append", "insert", "replace"],
                                "description": "write: Replace entire file | append: Add to end | insert: Add at line number | replace: Find & replace text"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write/append/insert (not used for 'replace' operation)"
                            },
                            "line_number": {
                                "type": "integer",
                                "description": "Line number for 'insert' operation (1-indexed). Content will be inserted BEFORE this line.",
                                "minimum": 1
                            },
                            "search": {
                                "type": "string",
                                "description": "Text to search for in 'replace' operation"
                            },
                            "replace": {
                                "type": "string",
                                "description": "Text to replace with in 'replace' operation"
                            }
                        },
                        "required": ["filename", "operation"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List contents of a directory with detailed information. Better than 'ls' command as it returns structured data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Absolute or relative path to directory (default: current directory)"
                            },
                            "show_hidden": {
                                "type": "boolean",
                                "description": "Include hidden files/directories (starting with .)"
                            },
                            "recursive": {
                                "type": "boolean",
                                "description": "List subdirectories recursively (tree view)"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_info",
                    "description": "Get detailed metadata about a file or directory: size, permissions, modified date, type, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Absolute or relative path to file or directory"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "network_request",
                    "description": "Make HTTP/HTTPS requests. Use for API calls, health checks, fetching data. Returns parsed JSON automatically.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Full URL to request (must include http:// or https://)"
                            },
                            "method": {
                                "type": "string",
                                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"],
                                "description": "HTTP method (default: GET)"
                            },
                            "headers": {
                                "type": "object",
                                "description": "Optional HTTP headers as key-value pairs"
                            },
                            "body": {
                                "type": "string",
                                "description": "Request body (for POST/PUT/PATCH). Will be sent as-is."
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Request timeout in seconds (default: 30)"
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_processes",
                    "description": "List running processes with CPU and memory usage. Filter and sort results. Better than parsing 'ps' output.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filter": {
                                "type": "string",
                                "description": "Filter processes by name (case-insensitive substring match)"
                            },
                            "sort_by": {
                                "type": "string",
                                "enum": ["cpu", "memory", "pid", "name"],
                                "description": "Sort processes by this field (default: cpu)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of processes to return (default: 20)"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for files and directories by name pattern. Supports glob patterns (*, ?, [abc]). Better than 'find' command.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Glob pattern to match (e.g., '*.py', 'config.*', 'test_*.js')"
                            },
                            "path": {
                                "type": "string",
                                "description": "Directory to search in (default: current directory)"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["file", "directory", "both"],
                                "description": "What to search for (default: both)"
                            },
                            "recursive": {
                                "type": "boolean",
                                "description": "Search in subdirectories recursively (default: true)"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 100)"
                            }
                        },
                        "required": ["pattern"]
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
You have access to these tools via function calling:

1. execute_command(command): Run shell commands and see output
   - Use for: package installation, system commands, checking status
   - Examples: "pacman -Syu --noconfirm", "ls -la", "systemctl status nginx"
   - Remember: NO sudo, ALWAYS --noconfirm for pacman

2. execute_background_command(command): Start long-running processes
   - Use for: servers, daemons, watch modes, blocking processes
   - Examples: "python3 -m http.server 8000", "npm run dev"

FILE OPERATIONS:
3. read_file(filename, start_line?, end_line?): Read file contents
   - Entire file: read_file("config.json")
   - Specific lines: read_file("app.py", start_line=10, end_line=20)
   - Use BEFORE editing to see current content

4. edit_file(filename, operation, ...): Unified file editing tool
   
   operation="write" - Replace ENTIRE file
   - edit_file("config.json", "write", content="...")
   - Use for: new files or complete rewrites
   
   operation="append" - Add to end of file
   - edit_file("log.txt", "append", content="New log entry\n")
   - Use for: adding to logs, appending data
   
   operation="insert" - Insert at specific line number
   - edit_file("app.py", "insert", content="import os\n", line_number=5)
   - Content inserted BEFORE the line number (1-indexed)
   - Use for: adding imports, inserting functions, adding config entries
   
   operation="replace" - Find and replace text
   - edit_file("config.json", "replace", search="8080", replace="3000")
   - Replaces ALL occurrences
   - Use for: changing values, updating text

SYSTEM OPERATIONS:
5. list_directory(path?, show_hidden?, recursive?): List directory contents
   - list_directory(".") - Current directory
   - list_directory("/etc", show_hidden=True) - Include hidden files
   - list_directory("/var/log", recursive=True) - Recursive listing
   - Returns structured data with file metadata (size, type, permissions, modified date)

6. get_file_info(path): Get detailed file/directory metadata
   - get_file_info("config.json") - Size, permissions, dates, type, line count
   - Better than 'stat' command - returns structured data
   - Use for checking file properties before operations

7. network_request(url, method?, headers?, body?, timeout?): Make HTTP requests
   - network_request("https://api.example.com/data") - GET request
   - network_request("https://api.example.com/upload", method="POST", body='{{"key":"value"}}')
   - Automatically parses JSON responses
   - Use for: API calls, downloading data, checking endpoints

8. get_processes(filter?, sort_by?, limit?): List running processes
   - get_processes() - Top 20 processes by CPU
   - get_processes(filter="python", sort_by="memory") - Filter by name, sort by memory
   - get_processes(limit=50) - Get top 50 processes
   - Better than 'ps' - returns structured data with CPU%, memory%, status

9. search_files(pattern, path?, type?, recursive?, max_results?): Search for files
   - search_files("*.py") - Find all Python files in current directory
   - search_files("config.*", path="/etc", recursive=True) - Search /etc recursively
   - search_files("*.log", type="file", max_results=50) - Only files, limit results
   - Uses glob patterns: * (any), ? (single char), [abc] (character set)

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
            return None  # Need some history to summarize
        
        logger.info("Summarizing conversation context...")
        
        tokens_before = self.get_conversation_tokens()
        
        # Keep first user message and last 4 messages, summarize the middle
        first_msg = self.conversation_history[0]
        recent_msgs = self.conversation_history[-4:]
        to_summarize = self.conversation_history[1:-4]
        
        if not to_summarize:
            return None
        
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
                result = response.json()
                summary = result["choices"][0]["message"]["content"]
                
                # Replace middle conversation with summary
                self.conversation_history = [
                    first_msg,
                    {"role": "system", "content": f"[Previous conversation summary: {summary}]"},
                    *recent_msgs
                ]
                
                tokens_after = self.get_conversation_tokens()
                tokens_saved = tokens_before - tokens_after
                
                logger.info(f"Context summarized. New length: {len(self.conversation_history)} messages")
                
                # Return summarization info
                return {
                    "summarized": True,
                    "tokens_before": tokens_before,
                    "tokens_after": tokens_after,
                    "tokens_saved": tokens_saved,
                    "messages_summarized": len(to_summarize)
                }
        except Exception as e:
            logger.error(f"Failed to summarize context: {e}")
            return None
    
    def query_llm(self, prompt: str, use_tools: bool = True) -> dict:
        """Query LM Studio API with tool calling support"""
        try:
            # Check if we need to summarize
            summarization_info = None
            current_tokens = self.get_conversation_tokens()
            if current_tokens > TARGET_CONTEXT_TOKENS:
                summarization_info = self.summarize_context()
            
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
                usage = result.get("usage", {})
                
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
                    "finish_reason": result["choices"][0].get("finish_reason"),
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    },
                    "context_info": {
                        "conversation_messages": len(self.conversation_history),
                        "estimated_context_tokens": self.get_conversation_tokens(),
                        "max_context_tokens": MAX_CONTEXT_TOKENS
                    },
                    "summarization": summarization_info
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
            
            elif tool_name == "read_file":
                filename = arguments["filename"]
                start_line = arguments.get("start_line")
                end_line = arguments.get("end_line")
                
                with open(filename, 'r') as f:
                    if start_line is not None:
                        # Read specific lines
                        lines = f.readlines()
                        start_idx = max(0, start_line - 1)
                        end_idx = end_line if end_line is None else min(len(lines), end_line)
                        selected_lines = lines[start_idx:end_idx]
                        content = ''.join(selected_lines)
                        
                        return {
                            "success": True,
                            "output": content,
                            "filename": filename,
                            "start_line": start_line,
                            "end_line": end_idx,
                            "lines_read": len(selected_lines),
                            "return_code": 0
                        }
                    else:
                        # Read entire file
                        content = f.read()
                        return {
                            "success": True,
                            "output": content,
                            "filename": filename,
                            "size": len(content),
                            "lines": len(content.splitlines()),
                            "return_code": 0
                        }
            
            elif tool_name == "edit_file":
                filename = arguments["filename"]
                operation = arguments["operation"]
                
                if operation == "write":
                    # Overwrite entire file
                    content = arguments.get("content", "")
                    
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
                        "operation": "write",
                        "size": len(cleaned_content),
                        "return_code": 0
                    }
                
                elif operation == "append":
                    # Append to end of file
                    content = arguments.get("content", "")
                    
                    # Create directory if needed
                    dir_path = os.path.dirname(filename)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    with open(filename, 'a') as f:
                        f.write(content)
                    
                    return {
                        "success": True,
                        "output": f"Content appended to: {filename} ({len(content)} bytes added)",
                        "filename": filename,
                        "operation": "append",
                        "bytes_added": len(content),
                        "return_code": 0
                    }
                
                elif operation == "insert":
                    # Insert at specific line
                    content = arguments.get("content", "")
                    line_number = arguments.get("line_number", 1)
                    
                    # Read existing content
                    try:
                        with open(filename, 'r') as f:
                            lines = f.readlines()
                    except FileNotFoundError:
                        lines = []
                    
                    # Insert content (line_number is 1-indexed, insert BEFORE that line)
                    insert_idx = max(0, min(line_number - 1, len(lines)))
                    
                    # Ensure content ends with newline if it doesn't
                    if content and not content.endswith('\n'):
                        content += '\n'
                    
                    lines.insert(insert_idx, content)
                    
                    # Create directory if needed
                    dir_path = os.path.dirname(filename)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    # Write back
                    with open(filename, 'w') as f:
                        f.writelines(lines)
                    
                    return {
                        "success": True,
                        "output": f"Content inserted at line {line_number} in {filename}",
                        "filename": filename,
                        "operation": "insert",
                        "line_number": line_number,
                        "return_code": 0
                    }
                
                elif operation == "replace":
                    # Find and replace
                    search = arguments.get("search", "")
                    replace = arguments.get("replace", "")
                    
                    with open(filename, 'r') as f:
                        content = f.read()
                    
                    # Count occurrences
                    count = content.count(search)
                    
                    if count == 0:
                        return {
                            "success": False,
                            "error": f"Search text not found in {filename}",
                            "output": "No matches found",
                            "return_code": 1
                        }
                    
                    # Replace all occurrences
                    new_content = content.replace(search, replace)
                    
                    with open(filename, 'w') as f:
                        f.write(new_content)
                    
                    return {
                        "success": True,
                        "output": f"Replaced {count} occurrence(s) in {filename}",
                        "filename": filename,
                        "operation": "replace",
                        "replacements": count,
                        "search": search,
                        "replace": replace,
                        "return_code": 0
                    }
                
                else:
                    return {
                        "success": False,
                        "error": f"Unknown operation: {operation}",
                        "return_code": 1
                    }
            
            elif tool_name == "list_directory":
                path = arguments.get("path", ".")
                show_hidden = arguments.get("show_hidden", False)
                recursive = arguments.get("recursive", False)
                
                results = []
                
                def scan_dir(dir_path, level=0):
                    try:
                        entries = []
                        for entry in os.scandir(dir_path):
                            if not show_hidden and entry.name.startswith('.'):
                                continue
                            
                            stat_info = entry.stat()
                            is_dir = entry.is_dir()
                            
                            entry_info = {
                                "name": entry.name,
                                "path": entry.path,
                                "type": "directory" if is_dir else "file",
                                "size": stat_info.st_size if not is_dir else 0,
                                "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                                "permissions": oct(stat_info.st_mode)[-3:],
                                "level": level
                            }
                            entries.append(entry_info)
                            
                            if recursive and is_dir:
                                scan_dir(entry.path, level + 1)
                        
                        # Sort: directories first, then alphabetically
                        entries.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
                        results.extend(entries)
                    except PermissionError:
                        pass
                
                scan_dir(path)
                
                # Format output
                output_lines = []
                for item in results:
                    indent = "  " * item["level"]
                    icon = "📁" if item["type"] == "directory" else "📄"
                    size_str = f"{item['size']:,} bytes" if item["type"] == "file" else ""
                    output_lines.append(f"{indent}{icon} {item['name']} {size_str}")
                
                return {
                    "success": True,
                    "output": "\n".join(output_lines),
                    "path": path,
                    "count": len(results),
                    "items": results,
                    "return_code": 0
                }
            
            elif tool_name == "get_file_info":
                path = arguments["path"]
                
                stat_info = os.stat(path)
                is_dir = os.path.isdir(path)
                is_file = os.path.isfile(path)
                is_link = os.path.islink(path)
                
                info = {
                    "path": path,
                    "name": os.path.basename(path),
                    "type": "directory" if is_dir else "file" if is_file else "symlink" if is_link else "other",
                    "size": stat_info.st_size,
                    "size_human": self._format_size(stat_info.st_size),
                    "permissions": oct(stat_info.st_mode)[-3:],
                    "owner_uid": stat_info.st_uid,
                    "group_gid": stat_info.st_gid,
                    "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    "accessed": datetime.fromtimestamp(stat_info.st_atime).isoformat()
                }
                
                # Add file-specific info
                if is_file:
                    try:
                        with open(path, 'r') as f:
                            content = f.read()
                            info["lines"] = len(content.splitlines())
                            info["characters"] = len(content)
                    except:
                        pass
                
                # Format output
                output = f"""Path: {info['path']}
Type: {info['type']}
Size: {info['size_human']} ({info['size']:,} bytes)
Permissions: {info['permissions']}
Modified: {info['modified']}
Created: {info['created']}"""
                
                if "lines" in info:
                    output += f"\nLines: {info['lines']:,}"
                
                return {
                    "success": True,
                    "output": output,
                    "info": info,
                    "return_code": 0
                }
            
            elif tool_name == "network_request":
                url = arguments["url"]
                method = arguments.get("method", "GET").upper()
                headers = arguments.get("headers", {})
                body = arguments.get("body")
                timeout = arguments.get("timeout", 30)
                
                try:
                    request_kwargs = {
                        "method": method,
                        "url": url,
                        "headers": headers,
                        "timeout": timeout
                    }
                    
                    if body and method in ["POST", "PUT", "PATCH"]:
                        request_kwargs["data"] = body
                    
                    response = requests.request(**request_kwargs)
                    
                    # Try to parse JSON
                    try:
                        response_data = response.json()
                        content_type = "json"
                    except:
                        response_data = response.text
                        content_type = "text"
                    
                    return {
                        "success": True,
                        "output": json.dumps(response_data, indent=2) if content_type == "json" else response_data,
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "content_type": content_type,
                        "data": response_data,
                        "return_code": 0
                    }
                except requests.exceptions.Timeout:
                    return {
                        "success": False,
                        "error": f"Request timed out after {timeout} seconds",
                        "return_code": 1
                    }
                except requests.exceptions.ConnectionError as e:
                    return {
                        "success": False,
                        "error": f"Connection error: {str(e)}",
                        "return_code": 1
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Request failed: {str(e)}",
                        "return_code": 1
                    }
            
            elif tool_name == "get_processes":
                filter_name = arguments.get("filter", "")
                sort_by = arguments.get("sort_by", "cpu")
                limit = arguments.get("limit", 20)
                
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'username']):
                    try:
                        pinfo = proc.info
                        
                        # Filter by name
                        if filter_name and filter_name.lower() not in pinfo['name'].lower():
                            continue
                        
                        processes.append({
                            "pid": pinfo['pid'],
                            "name": pinfo['name'],
                            "cpu_percent": pinfo['cpu_percent'] or 0,
                            "memory_percent": pinfo['memory_percent'] or 0,
                            "status": pinfo['status'],
                            "user": pinfo['username']
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Sort processes
                sort_keys = {
                    "cpu": lambda x: x["cpu_percent"],
                    "memory": lambda x: x["memory_percent"],
                    "pid": lambda x: x["pid"],
                    "name": lambda x: x["name"].lower()
                }
                processes.sort(key=sort_keys.get(sort_by, sort_keys["cpu"]), reverse=(sort_by in ["cpu", "memory"]))
                
                # Limit results
                processes = processes[:limit]
                
                # Format output
                output_lines = [f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'STATUS':<12} {'NAME'}"]
                output_lines.append("-" * 60)
                for proc in processes:
                    output_lines.append(
                        f"{proc['pid']:<8} {proc['cpu_percent']:<8.1f} {proc['memory_percent']:<8.1f} "
                        f"{proc['status']:<12} {proc['name']}"
                    )
                
                return {
                    "success": True,
                    "output": "\n".join(output_lines),
                    "processes": processes,
                    "count": len(processes),
                    "return_code": 0
                }
            
            elif tool_name == "search_files":
                pattern = arguments["pattern"]
                search_path = arguments.get("path", ".")
                search_type = arguments.get("type", "both")
                recursive = arguments.get("recursive", True)
                max_results = arguments.get("max_results", 100)
                
                import glob as glob_module
                
                # Build glob pattern
                if recursive:
                    glob_pattern = os.path.join(search_path, "**", pattern)
                else:
                    glob_pattern = os.path.join(search_path, pattern)
                
                # Search
                results = []
                for path in glob_module.glob(glob_pattern, recursive=recursive):
                    is_dir = os.path.isdir(path)
                    
                    # Filter by type
                    if search_type == "file" and is_dir:
                        continue
                    if search_type == "directory" and not is_dir:
                        continue
                    
                    stat_info = os.stat(path)
                    results.append({
                        "path": path,
                        "name": os.path.basename(path),
                        "type": "directory" if is_dir else "file",
                        "size": stat_info.st_size if not is_dir else 0,
                        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                    })
                    
                    if len(results) >= max_results:
                        break
                
                # Format output
                output_lines = []
                for item in results:
                    icon = "📁" if item["type"] == "directory" else "📄"
                    size_str = f"({item['size']:,} bytes)" if item["type"] == "file" else ""
                    output_lines.append(f"{icon} {item['path']} {size_str}")
                
                return {
                    "success": True,
                    "output": "\n".join(output_lines) if output_lines else "No matches found",
                    "pattern": pattern,
                    "results": results,
                    "count": len(results),
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
        
        # Emit summarization event if context was summarized
        if response.get("summarization"):
            yield yield_event("context_summarized", {
                "tokens_before": response["summarization"]["tokens_before"],
                "tokens_after": response["summarization"]["tokens_after"],
                "tokens_saved": response["summarization"]["tokens_saved"],
                "messages_summarized": response["summarization"]["messages_summarized"]
            })
        
        # Emit usage stats
        if response.get("usage"):
            yield yield_event("usage_stats", {
                "prompt_tokens": response["usage"]["prompt_tokens"],
                "completion_tokens": response["usage"]["completion_tokens"],
                "total_tokens": response["usage"]["total_tokens"],
                "context_info": response.get("context_info", {})
            })
        
        # Emit tool calls info if any
        if response.get("tool_calls"):
            tool_names = [tc["function"]["name"] for tc in response["tool_calls"]]
            yield yield_event("tool_calls_planned", {
                "count": len(response["tool_calls"]),
                "tools": tool_names
            })
        
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
                elif tool_name == "edit_file":
                    operation = arguments.get("operation", "write")
                    yield yield_event("file_write_start", {"filename": arguments["filename"], "operation": operation})
                elif tool_name == "read_file":
                    yield yield_event("file_read_start", {"filename": arguments["filename"]})
                elif tool_name == "list_directory":
                    yield yield_event("list_directory_start", {"path": arguments.get("path", ".")})
                elif tool_name == "get_file_info":
                    yield yield_event("get_file_info_start", {"path": arguments["path"]})
                elif tool_name == "network_request":
                    yield yield_event("network_request_start", {"url": arguments["url"], "method": arguments.get("method", "GET")})
                elif tool_name == "get_processes":
                    yield yield_event("get_processes_start", {"filter": arguments.get("filter", "")})
                elif tool_name == "search_files":
                    yield yield_event("search_files_start", {"pattern": arguments["pattern"], "path": arguments.get("path", ".")})
                
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
                elif tool_name == "edit_file":
                    operation = result.get("operation", arguments.get("operation", "write"))
                    if result["success"]:
                        event_data = {
                            "filename": arguments["filename"],
                            "operation": operation
                        }
                        
                        # Add operation-specific data
                        if operation == "write":
                            event_data["content"] = arguments.get("content", "")
                        elif operation == "append":
                            event_data["content"] = arguments.get("content", "")
                            event_data["bytes_added"] = result.get("bytes_added", 0)
                        elif operation == "insert":
                            event_data["content"] = arguments.get("content", "")
                            event_data["line_number"] = result.get("line_number", 0)
                        elif operation == "replace":
                            event_data["replacements"] = result.get("replacements", 0)
                            event_data["search"] = result.get("search", "")
                            event_data["replace"] = result.get("replace", "")
                        
                        yield yield_event("file_write_success", event_data)
                    else:
                        yield yield_event("file_write_error", {
                            "filename": arguments["filename"],
                            "error": result["error"]
                        })
                elif tool_name == "read_file":
                    if result["success"]:
                        event_data = {
                            "filename": arguments["filename"],
                            "content": result["output"]
                        }
                        
                        # Add info based on what was read
                        if "lines" in result:
                            # Full file read
                            event_data["size"] = result.get("size", 0)
                            event_data["lines"] = result.get("lines", 0)
                        else:
                            # Partial read
                            event_data["start_line"] = result.get("start_line", 1)
                            event_data["end_line"] = result.get("end_line", 0)
                            event_data["lines_read"] = result.get("lines_read", 0)
                        
                        yield yield_event("file_read_success", event_data)
                    else:
                        yield yield_event("file_read_error", {
                            "filename": arguments["filename"],
                            "error": result["error"]
                        })
                elif tool_name == "list_directory":
                    if result["success"]:
                        yield yield_event("list_directory_success", {
                            "path": result["path"],
                            "count": result["count"],
                            "output": result["output"],
                            "items": result.get("items", [])
                        })
                    else:
                        yield yield_event("list_directory_error", {
                            "path": arguments.get("path", "."),
                            "error": result["error"]
                        })
                elif tool_name == "get_file_info":
                    if result["success"]:
                        yield yield_event("get_file_info_success", {
                            "path": result["info"]["path"],
                            "output": result["output"],
                            "info": result["info"]
                        })
                    else:
                        yield yield_event("get_file_info_error", {
                            "path": arguments["path"],
                            "error": result["error"]
                        })
                elif tool_name == "network_request":
                    if result["success"]:
                        yield yield_event("network_request_success", {
                            "url": arguments["url"],
                            "method": arguments.get("method", "GET"),
                            "status_code": result["status_code"],
                            "output": result["output"],
                            "content_type": result["content_type"]
                        })
                    else:
                        yield yield_event("network_request_error", {
                            "url": arguments["url"],
                            "method": arguments.get("method", "GET"),
                            "error": result["error"]
                        })
                elif tool_name == "get_processes":
                    if result["success"]:
                        yield yield_event("get_processes_success", {
                            "count": result["count"],
                            "output": result["output"],
                            "processes": result.get("processes", [])
                        })
                    else:
                        yield yield_event("get_processes_error", {
                            "error": result["error"]
                        })
                elif tool_name == "search_files":
                    if result["success"]:
                        yield yield_event("search_files_success", {
                            "pattern": result["pattern"],
                            "count": result["count"],
                            "output": result["output"],
                            "results": result.get("results", [])
                        })
                    else:
                        yield yield_event("search_files_error", {
                            "pattern": arguments["pattern"],
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
            
            # Emit usage stats
            if response.get("usage"):
                yield yield_event("usage_stats", {
                    "prompt_tokens": response["usage"]["prompt_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "total_tokens": response["usage"]["total_tokens"],
                    "context_info": response.get("context_info", {})
                })
            
            # Emit tool calls info if any
            if response.get("tool_calls"):
                tool_names = [tc["function"]["name"] for tc in response["tool_calls"]]
                yield yield_event("tool_calls_planned", {
                    "count": len(response["tool_calls"]),
                    "tools": tool_names
                })
            
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
