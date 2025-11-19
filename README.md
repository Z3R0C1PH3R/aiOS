# 🤖 aiOS - Agentic AI Operating System

<div align="center">

**An autonomous AI agent with full OS-level access, powered by local LLMs**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![LM Studio](https://img.shields.io/badge/LM%20Studio-Compatible-purple.svg)](https://lmstudio.ai)

</div>

---

## 🌟 Overview

**aiOS** is an autonomous AI agent that provides OS-level control through natural language. Talk to your system, and let the AI handle command execution, file operations, software installation, and system management autonomously.

**What it does:**
- Execute system commands with root privileges
- Read, write, and edit files automatically
- Install and configure software
- Monitor system resources in real-time
- Make network requests
- Manage processes and services
- Iterate on complex tasks until completion

---

## ✨ Features

### 🎨 Web Interface
- Real-time streaming responses (SSE)
- Beautiful dark-themed UI
- Live system monitoring (CPU, Memory, Disk, Context)
- Save/load conversations
- Markdown rendering with syntax highlighting
- Stop/resume AI processing

### 🛠️ Tool System
The AI has access to 9 specialized tools:

1. **execute_command** - Run shell commands
2. **execute_background_command** - Start long-running processes
3. **read_file** - Read files (full or line ranges)
4. **edit_file** - Write, append, insert, or replace file content
5. **list_directory** - Browse directories with metadata
6. **get_file_info** - Get file/directory details
7. **network_request** - Make HTTP/HTTPS requests
8. **get_processes** - List and filter processes
9. **search_files** - Find files using glob patterns

### 🧠 Smart Features
- **Context summarization** - Auto-compress when approaching token limits
- **Iterative completion** - AI continues until task is done
- **Token tracking** - Real-time usage monitoring
- **Conversation persistence** - Full chat history save/restore

---

## 🚀 Installation

### Prerequisites
- Python 3.8+
- LM Studio with a loaded model (Qwen2.5-Coder, DeepSeek-Coder, etc.)
- Linux with root access
- Root privileges for full system control

### Quick Start

1. **Clone the repo**
```bash
git clone https://github.com/yourusername/aiOS.git
cd aiOS
```

2. **Install dependencies**
```bash
pip install flask flask-cors requests psutil python-dotenv
```

3. **Configure (optional)**
Create `.env` file:
```bash
LM_STUDIO_URL=http://localhost:1234
MODEL_NAME=qwen3-coder-30b
MAX_CONTEXT_TOKENS=32768
MAX_TOKENS_PER_RESPONSE=8192
```

4. **Start LM Studio**
- Load your model (30B recommended)
- Start server on port 1234

5. **Run aiOS**
```bash
sudo python3 web_agent.py
```

6. **Access the interface**
Open browser: `http://localhost:5000`

---

## 💻 Usage

### Example Prompts
- "Install Docker and start the service"
- "Create a Python web scraper that saves to CSV"
- "Check disk usage and clean up old logs"
- "Set up Nginx reverse proxy for port 8080"
- "Find all Python files in /home and list their sizes"

### Web Interface Features
- **💬 Chat** - Natural language commands
- **⏹️ Stop** - Halt AI processing anytime
- **💾 Save/Load** - Preserve conversations
- **📊 Monitor** - Real-time resource tracking
- **🧹 Clear** - Reset conversation

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LM_STUDIO_URL` | `http://localhost:1234` | LM Studio API endpoint |
| `MODEL_NAME` | `qwen3-coder-30b` | Model name |
| `MAX_CONTEXT_TOKENS` | `32768` | Max context window |
| `MAX_TOKENS_PER_RESPONSE` | `8192` | Max tokens per response |
| `LOG_FILE` | `/tmp/arch_agent_web.log` | Log file path |

---

## 🌐 API Endpoints

### Core Endpoints

- `GET /` - Web interface
- `GET /api/status` - System status (CPU, memory, disk)
- `POST /api/chat` - Process message (SSE stream)
- `POST /api/stop` - Stop AI processing
- `POST /api/clear` - Clear conversation

### Conversation Management

- `POST /api/save` - Save conversation to file
- `POST /api/load` - Load conversation from file
- `GET /api/list-saves` - List saved conversations
- `POST /api/download` - Download conversation file
- `POST /api/restore` - Restore from uploaded JSON

---

## 🎯 Advanced Features

### Context Summarization
Auto-compresses conversation when approaching token limit. Keeps first and last 4 messages, summarizes the middle.

### Iterative Task Completion
AI continues working until task is complete:
1. Receives request
2. Plans tool calls
3. Executes tools
4. Analyzes results
5. Continues or stops

### Token Tracking
Real-time monitoring displayed in header status bar and task summaries.

### Conversation Persistence
Save conversations with full state including tool calls and system responses. Download as JSON or restore from uploaded files.

---

## 🔒 Security

### ⚠️ WARNING
**aiOS runs with root privileges and has full system access. Use with caution!**

### Safety Features
- Blocks dangerous commands (`rm -rf /`, `dd`, `mkfs`, etc.)
- 120 second command timeout
- Error isolation and graceful failure handling

### Best Practices
- **Run in VM** for testing
- **Backup data** before use
- **Monitor logs**: `/tmp/arch_agent_web.log`
- **Limit network exposure**: Bind to localhost only

To restrict to localhost:
```python
# Edit web_agent.py line 2085:
app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
```

---

## 🛠️ Troubleshooting

### Common Issues

**"Cannot connect to LM Studio"**
- Check LM Studio is running
- Verify model is loaded
- Test: `curl http://localhost:1234/v1/models`

**"Permission denied"**
- Run with `sudo`
- Check file permissions

**Web interface not loading**
- Check Flask: `ps aux | grep web_agent`
- Verify port: `lsof -i :5000`
- Check logs: `tail -f /tmp/arch_agent_web.log`

**AI not responding**
- Verify LM Studio model loaded
- Try clearing conversation
- Restart LM Studio

### Debug Logging
```python
# Edit web_agent.py:
app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
```

---

## 📊 Performance

### System Requirements
- **Minimum**: 8GB RAM, 4 CPU cores
- **Recommended**: 16GB RAM, 8 CPU cores
- **Model**: 7B-30B parameters
- **Storage**: 20GB+ free

### Optimization Tips
- Clear old conversations regularly
- Use shorter prompts
- Reduce context window if not needed
- Use faster/smaller models for simple tasks

---

## 🤝 Contributing

Contributions welcome!

1. Fork the repo
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 🎓 Examples

### Example 1: Install Software
**User:** "Install nginx and start the service"

**AI:**
```
[Executes: pacman -S nginx --noconfirm]
✅ nginx installed

[Executes: systemctl enable nginx && systemctl start nginx]
✅ Service started and enabled

Nginx is now running on port 80!
```

### Example 2: System Cleanup
**User:** "Find and delete log files older than 30 days"

**AI:**
```
[Searches: /var/log for *.log]
Found 47 log files

[Filters: files older than 30 days]
15 files match criteria (2.3GB)

[Removes: old log files]
✅ Cleaned up 15 files, freed 2.3GB
```

### Example 3: Development Setup
**User:** "Create a Flask hello world app with virtual environment"

**AI:**
```
[Creates: /home/user/flask_app/]
[Executes: python -m venv venv]
✅ Virtual environment created

[Executes: venv/bin/pip install flask]
✅ Flask installed

[Creates: app.py with hello world code]
✅ App created

Ready! Run with: cd flask_app && ./venv/bin/python app.py
```

---

## 🗺️ Roadmap

### Planned
- [ ] Multi-user authentication
- [ ] Docker containerization
- [ ] Plugin system for custom tools
- [ ] Multi-model support (OpenAI, Anthropic)
- [ ] Mobile-responsive UI
- [ ] Audit logging

### Completed
- [x] Web interface with SSE streaming
- [x] Tool calling system
- [x] Context summarization
- [x] Conversation save/load
- [x] Real-time system monitoring

---

<div align="center">

**Made with ❤️ by the aiOS team**

⭐ Star us on GitHub!

</div>
