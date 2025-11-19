# 🤖 aiOS - Agentic AI Operating System

<div align="center">

**An autonomous AI agent with full OS-level access, powered by local LLMs**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LM Studio](https://img.shields.io/badge/LM%20Studio-Compatible-purple.svg)](https://lmstudio.ai)

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Usage](#-usage)
  - [Web Interface](#web-interface-recommended)
  - [CLI Interface](#cli-interface)
- [Configuration](#-configuration)
- [Tool System](#-tool-system)
- [API Endpoints](#-api-endpoints)
- [Advanced Features](#-advanced-features)
- [Security Considerations](#-security-considerations)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**aiOS** (Agentic AI Operating System) is a powerful AI agent that provides autonomous OS-level control through natural language. It combines the capabilities of large language models with direct system access, enabling you to manage your Linux system through conversational AI.

Unlike traditional chatbots, aiOS can:
- **Execute system commands** with full root privileges
- **Read and write files** with multiple editing modes
- **Install and configure software** autonomously
- **Monitor system resources** in real-time
- **Make network requests** and interact with APIs
- **Manage processes** and system services
- **Iterate on tasks** until completion

The project includes both a **modern web interface** with real-time streaming and a **powerful CLI** for terminal enthusiasts.

---

## ✨ Features

### 🎨 Modern Web Interface
- **Real-time streaming responses** with Server-Sent Events (SSE)
- **Beautiful, responsive UI** with dark mode
- **Live system monitoring** (CPU, Memory, Disk, Context usage)
- **Conversation save/load** with JSON export/import
- **File upload/download** for conversation management
- **Markdown rendering** with syntax highlighting
- **Auto-scroll** with manual control
- **Stop/Resume** AI processing on demand

### 🛠️ Powerful Tool System
aiOS provides **9 specialized tools** for system interaction:

1. **execute_command** - Run shell commands with output capture
2. **execute_background_command** - Start long-running processes
3. **read_file** - Read entire files or specific line ranges
4. **edit_file** - Unified file editing (write, append, insert, replace)
5. **list_directory** - Browse directories with metadata
6. **get_file_info** - Get detailed file/directory information
7. **network_request** - Make HTTP/HTTPS requests
8. **get_processes** - List and filter running processes
9. **search_files** - Find files using glob patterns

### 🧠 Intelligent Features
- **Context summarization** - Automatic compression when approaching token limits
- **Iterative task completion** - AI continues until task is fully done
- **Error recovery** - Intelligent handling of failed commands
- **Token tracking** - Real-time usage monitoring
- **Conversation persistence** - Save and restore full chat history

### 🔒 Safety Features
- **Command validation** - Blocks dangerous operations
- **Root detection** - Warns when running with elevated privileges
- **Timeout protection** - Prevents hanging commands
- **Error isolation** - Graceful failure handling

---

## 🏗️ Architecture

```
aiOS/
├── web_agent.py          # Flask web server with SSE streaming
├── os_ai_agent.py        # CLI agent with interactive mode
├── templates/
│   └── web_interface.html # Modern web UI with JavaScript
├── .env                  # Configuration (optional)
└── README.md            # This file
```

### Technology Stack
- **Backend**: Python 3.8+, Flask, Flask-CORS
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **LLM Integration**: LM Studio API (OpenAI-compatible)
- **Streaming**: Server-Sent Events (SSE)
- **Tool Calling**: Function calling with streaming
- **Markdown**: Marked.js for rendering

---

## 🚀 Installation

### Prerequisites
- **Python 3.8+**
- **LM Studio** with a loaded model (e.g., Qwen2.5-Coder, DeepSeek-Coder)
- **Arch Linux** (or any Linux with root access)
- **Root privileges** for full system control

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/aiOS.git
cd aiOS
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

**Required packages:**
```
flask>=2.0.0
flask-cors>=3.0.0
requests>=2.25.0
psutil>=5.8.0
python-dotenv>=0.19.0
```

### Step 3: Configure LM Studio
1. Download and install [LM Studio](https://lmstudio.ai)
2. Load a model (recommended: Qwen2.5-Coder 30B or DeepSeek-Coder)
3. Start the local server on port 1234
4. Note your LM Studio URL (e.g., `http://localhost:1234`)

### Step 4: Configure aiOS (Optional)
Create a `.env` file in the project root:

```bash
LM_STUDIO_URL=http://localhost:1234
MODEL_NAME=qwen3-coder-30b
AGENT_NAME=aiOSagent
MAX_CONTEXT_TOKENS=32768
MAX_TOKENS_PER_RESPONSE=8192
LOG_FILE=/tmp/arch_agent_web.log
```

---

## 💻 Usage

### Web Interface (Recommended)

#### Start the Web Server
```bash
# Run with sudo for full system access
sudo python3 web_agent.py
```

#### Access the Interface
1. Open your browser
2. Navigate to `http://localhost:5000`
3. Start chatting with your AI OS!

**Example prompts:**
- "Install Docker and start the service"
- "Create a Python web scraper that saves to CSV"
- "Check disk usage and clean up old logs"
- "Set up a Nginx reverse proxy for port 8080"
- "Find all Python files in my home directory"

#### Web Interface Features
- **💬 Chat Interface** - Natural language commands
- **⏹️ Stop Button** - Halt AI processing anytime
- **💾 Save/Load** - Preserve conversations
- **📊 System Monitor** - Real-time resource tracking
- **🧹 Clear** - Reset conversation history

### CLI Interface

#### Start the CLI Agent
```bash
# Run with sudo for full system access
sudo python3 os_ai_agent.py
```

#### CLI Commands
- **Natural language** - "install nginx and start it"
- **`status`** - Show system information
- **`clear`** - Clear conversation history
- **`!command`** - Execute command directly
- **`exit`** - Quit the agent

#### XML Tags (CLI Mode)
The CLI agent uses XML-style tags for precise control:

```xml
<!-- Execute with AI feedback -->
<COMMAND return_output="true">ls -la</COMMAND>

<!-- Execute without feedback -->
<COMMAND return_output="false">systemctl start nginx</COMMAND>

<!-- Write files -->
<WRITEFILE filename="/etc/nginx/nginx.conf">
server {
    listen 80;
    server_name example.com;
}
</WRITEFILE>

<!-- Mark completion -->
<DONE>Installation complete!</DONE>
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LM_STUDIO_URL` | `http://localhost:1234` | LM Studio API endpoint |
| `MODEL_NAME` | `qwen3-coder-30b` | Model identifier |
| `AGENT_NAME` | `aiOSagent` | Agent display name |
| `MAX_CONTEXT_TOKENS` | `32768` | Maximum context window |
| `MAX_TOKENS_PER_RESPONSE` | `8192` | Max tokens per response |
| `LOG_FILE` | `/tmp/arch_agent_web.log` | Log file path |

### LM Studio Configuration
1. **Model Selection**: Choose a code-capable model (30B+ recommended)
2. **Context Length**: Set to match `MAX_CONTEXT_TOKENS`
3. **Temperature**: 0.7 (balanced creativity/precision)
4. **Server**: Enable local server on port 1234

---

## 🔧 Tool System

### Tool Calling Architecture
aiOS uses **LM Studio's function calling API** to provide structured tool access:

```python
{
    "type": "function",
    "function": {
        "name": "execute_command",
        "description": "Execute a shell command and get the output",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                }
            },
            "required": ["command"]
        }
    }
}
```

### Available Tools

#### 1. execute_command
Execute shell commands with output capture.

**Parameters:**
- `command` (string): Shell command to run

**Example:**
```json
{
  "command": "pacman -Syu --noconfirm"
}
```

#### 2. execute_background_command
Start long-running processes (servers, daemons).

**Parameters:**
- `command` (string): Command to run in background

**Example:**
```json
{
  "command": "python3 -m http.server 8000"
}
```

#### 3. read_file
Read file contents (entire or range).

**Parameters:**
- `filename` (string): Path to file
- `start_line` (integer, optional): Starting line (1-indexed)
- `end_line` (integer, optional): Ending line (inclusive)

**Example:**
```json
{
  "filename": "/etc/nginx/nginx.conf",
  "start_line": 10,
  "end_line": 20
}
```

#### 4. edit_file
Unified file editing with multiple operations.

**Operations:**
- **write**: Replace entire file
- **append**: Add to end of file
- **insert**: Insert at specific line
- **replace**: Find and replace text

**Parameters:**
- `filename` (string): Path to file
- `operation` (string): Operation type
- `content` (string): Content (for write/append/insert)
- `line_number` (integer): Line for insert operation
- `search` (string): Search text for replace
- `replace` (string): Replacement text

**Examples:**

Write entire file:
```json
{
  "filename": "config.json",
  "operation": "write",
  "content": "{\"port\": 8080}"
}
```

Append to file:
```json
{
  "filename": "log.txt",
  "operation": "append",
  "content": "New log entry\n"
}
```

Insert at line:
```json
{
  "filename": "script.py",
  "operation": "insert",
  "line_number": 5,
  "content": "import os\n"
}
```

Find and replace:
```json
{
  "filename": "config.yaml",
  "operation": "replace",
  "search": "port: 80",
  "replace": "port: 443"
}
```

#### 5. list_directory
List directory contents with metadata.

**Parameters:**
- `path` (string): Directory path (default: current)
- `show_hidden` (boolean): Include hidden files
- `recursive` (boolean): Recursive listing

**Example:**
```json
{
  "path": "/var/log",
  "show_hidden": true,
  "recursive": false
}
```

#### 6. get_file_info
Get detailed file/directory metadata.

**Parameters:**
- `path` (string): File or directory path

**Example:**
```json
{
  "path": "/etc/passwd"
}
```

#### 7. network_request
Make HTTP/HTTPS requests.

**Parameters:**
- `url` (string): Full URL
- `method` (string): HTTP method (GET/POST/PUT/DELETE/PATCH/HEAD)
- `headers` (object): HTTP headers
- `body` (string): Request body (for POST/PUT/PATCH)
- `timeout` (integer): Timeout in seconds

**Example:**
```json
{
  "url": "https://api.github.com/users/octocat",
  "method": "GET",
  "timeout": 30
}
```

#### 8. get_processes
List running processes with filtering.

**Parameters:**
- `filter` (string): Filter by name
- `sort_by` (string): Sort field (cpu/memory/pid/name)
- `limit` (integer): Max results (default: 20)

**Example:**
```json
{
  "filter": "python",
  "sort_by": "memory",
  "limit": 10
}
```

#### 9. search_files
Search for files using glob patterns.

**Parameters:**
- `pattern` (string): Glob pattern (e.g., `*.py`)
- `path` (string): Search directory (default: current)
- `type` (string): file/directory/both
- `recursive` (boolean): Recursive search
- `max_results` (integer): Max results (default: 100)

**Example:**
```json
{
  "pattern": "*.log",
  "path": "/var/log",
  "type": "file",
  "recursive": true,
  "max_results": 50
}
```

---

## 🌐 API Endpoints

### Web Server Endpoints

#### GET `/`
Serve the main web interface.

#### GET `/api/status`
Get current system status (CPU, memory, disk).

**Response:**
```json
{
  "hostname": "arch-vm",
  "user": "root",
  "cpu_percent": 15.2,
  "memory_percent": 45.8,
  "memory_used_gb": 7,
  "memory_total_gb": 16,
  "disk_percent": 62.3,
  "disk_used_gb": 125,
  "disk_total_gb": 200,
  "load_average": [0.5, 0.6, 0.7]
}
```

#### POST `/api/chat`
Process chat message with streaming events.

**Request:**
```json
{
  "message": "Install docker and start the service"
}
```

**Response:** Server-Sent Events (SSE) stream

Event types:
- `ai_thinking` - AI is processing
- `ai_response_chunk` - Streamed text chunk
- `ai_response_complete` - Response finished
- `tool_call_start` - Tool call initiated
- `tool_call_arguments` - Tool arguments streaming
- `tool_calls_planned` - All tools planned
- `command_start` / `command_result` - Command execution
- `file_write_start` / `file_write_success` - File operations
- `usage_stats` - Token usage update
- `task_complete` - Task finished
- `error` - Error occurred

#### POST `/api/stop`
Stop current AI processing.

#### POST `/api/clear`
Clear conversation history.

#### POST `/api/save`
Save conversation to file.

**Request:**
```json
{
  "filename": "chat_2025_11_17.json"
}
```

**Response:**
```json
{
  "status": "saved",
  "filepath": "/root/aiOS_chats/chat_2025_11_17.json",
  "message_count": 42
}
```

#### POST `/api/load`
Load conversation from file.

**Request:**
```json
{
  "filepath": "/root/aiOS_chats/chat_2025_11_17.json"
}
```

**Response:**
```json
{
  "status": "loaded",
  "filepath": "/root/aiOS_chats/chat_2025_11_17.json",
  "message_count": 42,
  "timestamp": "2025-11-17T10:30:00",
  "conversation_history": [...]
}
```

#### GET `/api/list-saves`
List all saved conversation files.

**Response:**
```json
{
  "saves": [
    {
      "filename": "chat_2025_11_17.json",
      "filepath": "/root/aiOS_chats/chat_2025_11_17.json",
      "size": 15420,
      "modified": "2025-11-17T10:30:00"
    }
  ]
}
```

#### POST `/api/download`
Download conversation file.

**Request:**
```json
{
  "filepath": "/root/aiOS_chats/chat_2025_11_17.json"
}
```

**Response:** JSON conversation data

#### POST `/api/restore`
Restore conversation from uploaded JSON.

**Request:** Full conversation JSON object

**Response:**
```json
{
  "status": "loaded",
  "message_count": 42,
  "timestamp": "2025-11-17T10:30:00",
  "conversation_history": [...]
}
```

---

## 🎯 Advanced Features

### Context Summarization
When conversation approaches token limit (`TARGET_CONTEXT_TOKENS`), aiOS automatically:
1. Keeps first and last 4 messages
2. Summarizes middle conversation
3. Replaces with concise summary
4. Reports tokens saved

**Trigger:** `current_tokens > TARGET_CONTEXT_TOKENS`

### Iterative Task Completion
The AI continues working until task is fully complete:
1. Receives user request
2. Plans tool calls
3. Executes tools
4. Analyzes results
5. Continues if needed
6. Stops when done

**Exit conditions:**
- Task completed successfully
- User stops processing
- Error requires user intervention

### Token Tracking
Real-time monitoring of:
- **Prompt tokens**: Input to LLM
- **Completion tokens**: Generated output
- **Total tokens**: Combined usage
- **Context tokens**: Conversation history
- **Task tokens**: Current task usage

**Display locations:**
- Header status bar (context %)
- Usage stats events
- Task completion summary

### Conversation Persistence
**Save format:**
```json
{
  "timestamp": "2025-11-17T10:30:00",
  "version": "1.0",
  "system_prompt": "You are aiOSagent...",
  "conversation_history": [
    {
      "role": "user",
      "content": "Install docker"
    },
    {
      "role": "assistant",
      "content": "I'll install docker...",
      "tool_calls": [...]
    },
    {
      "role": "tool",
      "tool_call_id": "call_123",
      "content": "{\"success\": true, ...}"
    }
  ]
}
```

**Features:**
- Full conversation state
- Tool call history
- Timestamp tracking
- Browser download
- Server-side storage
- Drag-and-drop upload

---

## 🔒 Security Considerations

### ⚠️ Important Warnings

**aiOS has full system access and runs with root privileges. Use with caution!**

### Safety Features
1. **Dangerous command blocking**
   - `rm -rf /` - Blocked
   - `dd if=` - Blocked
   - `mkfs` - Blocked
   - Other destructive operations

2. **User confirmation** (CLI mode)
   - Selective command execution
   - Review before running

3. **Timeout protection**
   - 120 second command timeout
   - Prevents hanging processes

4. **Error isolation**
   - Graceful failure handling
   - Conversation state preserved

### Best Practices
- **Run in VM** for testing
- **Review AI suggestions** before execution
- **Backup important data** before use
- **Monitor system logs** (`/tmp/arch_agent_web.log`)
- **Use environment isolation** (containers, VMs)
- **Limit network exposure** (localhost only)

### Network Security
- **Default binding**: `0.0.0.0:5000` (all interfaces)
- **Recommendation**: Use firewall rules
- **Production**: Add authentication layer

```bash
# Restrict to localhost only
# Edit web_agent.py line 2085:
app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
```

---

## 🛠️ Troubleshooting

### Common Issues

#### "Cannot connect to LM Studio"
**Solution:**
1. Check LM Studio is running
2. Verify model is loaded
3. Test API: `curl http://localhost:1234/v1/models`
4. Check firewall rules
5. Verify `LM_STUDIO_URL` in config

#### "Permission denied" errors
**Solution:**
1. Run with `sudo`
2. Check file permissions
3. Verify user has necessary privileges

#### "Command timed out"
**Solution:**
1. Increase timeout in `web_agent.py` line 481
2. Use `execute_background_command` for long tasks
3. Split into smaller operations

#### Web interface not loading
**Solution:**
1. Check Flask is running: `ps aux | grep web_agent`
2. Verify port 5000 is free: `lsof -i :5000`
3. Check browser console for errors
4. Review logs: `tail -f /tmp/arch_agent_web.log`

#### AI not responding
**Solution:**
1. Check LM Studio model is loaded
2. Verify token limits in config
3. Try clearing conversation history
4. Restart LM Studio server

#### Context limit reached
**Solution:**
1. Wait for automatic summarization
2. Manually clear conversation
3. Increase `MAX_CONTEXT_TOKENS`
4. Use shorter prompts

### Debugging

#### Enable Debug Logging
Edit `web_agent.py`:
```python
app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
```

#### Check Logs
```bash
# Real-time log monitoring
tail -f /tmp/arch_agent_web.log

# Search for errors
grep ERROR /tmp/arch_agent_web.log

# View full log
cat /tmp/arch_agent_web.log
```

#### Test LM Studio Connection
```bash
# Test API availability
curl http://localhost:1234/v1/models

# Test completion
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-coder-30b",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'
```

---

## 📊 Performance Tips

### Optimize Token Usage
1. **Clear old conversations** regularly
2. **Use shorter prompts** when possible
3. **Enable summarization** (automatic)
4. **Reduce context window** if not needed

### Speed Up Responses
1. **Use faster models** (smaller size)
2. **Reduce `MAX_TOKENS_PER_RESPONSE`**
3. **Disable unused tools** (edit tool definitions)
4. **Use SSD** for better I/O

### System Requirements
- **Minimum**: 8GB RAM, 4 CPU cores
- **Recommended**: 16GB RAM, 8 CPU cores
- **Model size**: 7B-30B parameters
- **Disk space**: 20GB+ free

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Clone your fork
git clone https://github.com/yourusername/aiOS.git
cd aiOS

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests (if available)
python -m pytest

# Start development server
python3 web_agent.py
```

### Code Style
- Follow PEP 8 for Python
- Use meaningful variable names
- Add docstrings to functions
- Comment complex logic
- Keep functions focused and small

### Reporting Issues
Please include:
- OS and version
- Python version
- LM Studio version
- Model being used
- Full error message
- Steps to reproduce

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 aiOS Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 Acknowledgments

- **LM Studio** - For the excellent local LLM server
- **Anthropic** - For Claude and AI safety research
- **OpenAI** - For the OpenAI API standard
- **Qwen Team** - For the Qwen2.5-Coder models
- **DeepSeek** - For DeepSeek-Coder models
- **Flask** - For the web framework
- **Marked.js** - For markdown rendering

---

## 📞 Support

Need help? Found a bug? Have a feature request?

- **Issues**: [GitHub Issues](https://github.com/yourusername/aiOS/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/aiOS/discussions)
- **Email**: your.email@example.com

---

## 🗺️ Roadmap

### Planned Features
- [ ] Multi-user support with authentication
- [ ] Docker containerization
- [ ] Plugin system for custom tools
- [ ] Voice interface integration
- [ ] Multi-model support (OpenAI, Anthropic, etc.)
- [ ] Conversation search and filtering
- [ ] Scheduled task execution
- [ ] Integration with popular DevOps tools
- [ ] Mobile-responsive improvements
- [ ] Real-time collaboration
- [ ] Audit logging and compliance features

### Completed Features
- [x] Web interface with SSE streaming
- [x] Tool calling system
- [x] Context summarization
- [x] Conversation save/load
- [x] Real-time system monitoring
- [x] Multiple file operations
- [x] Background command execution
- [x] Process management
- [x] Network requests
- [x] File search with glob patterns

---

## 📸 Screenshots

### Web Interface
![Web Interface](screenshots/web-interface.png)
*Modern dark-themed chat interface with real-time streaming*

### System Monitoring
![System Monitor](screenshots/system-monitor.png)
*Live CPU, memory, and disk usage tracking*

### Tool Execution
![Tool Execution](screenshots/tool-execution.png)
*Real-time tool call execution with formatted output*

---

## 🎓 Examples

### Example 1: Install and Configure Software
**User:** "Install nginx, create a basic config, and start the service"

**AI Response:**
```
I'll install nginx, configure it, and start the service for you.

[Executes: pacman -S nginx --noconfirm]
✅ nginx installed successfully

[Creates: /etc/nginx/nginx.conf]
✅ Configuration file created

[Executes: systemctl enable nginx]
[Executes: systemctl start nginx]
✅ nginx service started and enabled

The web server is now running on port 80!
```

### Example 2: System Maintenance
**User:** "Check disk usage, find large log files, and clean up old ones"

**AI Response:**
```
I'll analyze disk usage and clean up old logs.

[Executes: df -h]
Disk usage: 65% (130GB / 200GB used)

[Searches: /var/log for *.log files]
Found 47 log files

[Lists: large files > 100MB]
- /var/log/journal/system.log (450MB)
- /var/log/pacman.log (120MB)

[Removes: logs older than 30 days]
✅ Cleaned up 15 old log files (2.3GB freed)

Disk usage now: 62% (125GB / 200GB used)
```

### Example 3: Development Setup
**User:** "Set up a Python virtual environment with Flask and create a hello world app"

**AI Response:**
```
I'll create a Python Flask project for you.

[Creates: /home/user/flask_app/]
[Creates: /home/user/flask_app/venv]
[Executes: python -m venv venv]
✅ Virtual environment created

[Executes: venv/bin/pip install flask]
✅ Flask installed

[Creates: /home/user/flask_app/app.py]
✅ Created hello world Flask app

[Executes: chmod +x app.py]
✅ Made executable

Your Flask app is ready! Run with:
cd /home/user/flask_app && ./venv/bin/python app.py
```

---

<div align="center">

**Made with ❤️ by the aiOS team**

⭐ Star us on GitHub if you find this useful!

</div>
