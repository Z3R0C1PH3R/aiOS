#!/usr/bin/env python3
"""
Web Frontend for OS AI Agent
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import queue
import sys
from os_ai_agent import OSAgent, AGENT_NAME, LM_STUDIO_URL
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'aios-secret-key-change-in-production'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global agent instance
agent = None
agent_lock = threading.Lock()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebOSAgent(OSAgent):
    """Extended OS Agent that emits events to web interface"""
    
    def __init__(self, socket_io):
        super().__init__()
        self.socketio = socket_io
        
    def emit_message(self, msg_type, content):
        """Emit message to web interface"""
        self.socketio.emit('agent_message', {
            'type': msg_type,
            'content': content
        })
    
    def execute_and_show(self, command: str) -> None:
        """Execute command and emit results to web"""
        self.emit_message('command_start', f"Executing: {command}")
        result = self.execute_command(command)
        
        if result["success"]:
            if result["output"].strip():
                self.emit_message('command_output', result['output'])
            else:
                self.emit_message('command_success', "Command completed successfully")
        else:
            self.emit_message('command_error', f"Error: {result['error']}")
            if result["output"]:
                self.emit_message('command_output', result['output'])
    
    def process_response_with_iteration(self, ai_response: str) -> None:
        """Process AI response and emit updates to web"""
        self.emit_message('ai_response', ai_response)
        
        # Extract all tags
        tags = self.extract_commands_and_tags(ai_response)
        
        # Execute operations
        commands_needing_feedback = []
        
        if tags["ordered_tags"]:
            self.emit_message('info', f"Processing {len(tags['ordered_tags'])} operation(s)...")
            
            for pos, tag_type, data in tags["ordered_tags"]:
                if tag_type == 'command':
                    return_output, cmd = data
                    self.emit_message('command_start', f"Executing: {cmd}")
                    
                    result = self.execute_command(cmd)
                    
                    if result["success"]:
                        if result["output"].strip():
                            self.emit_message('command_output', result['output'])
                        else:
                            self.emit_message('command_success', "Command completed successfully")
                    else:
                        self.emit_message('command_error', f"Error: {result['error']}")
                        if result["output"]:
                            self.emit_message('command_output', result['output'])
                    
                    if return_output:
                        formatted_output = self.execute_with_feedback(cmd)
                        commands_needing_feedback.append(formatted_output)
                
                elif tag_type == 'writefile':
                    filename, content = data
                    self.emit_message('file_write', f"Writing file: {filename}")
                    try:
                        cleaned_content = content.strip()
                        if cleaned_content.startswith('```python'):
                            cleaned_content = cleaned_content[9:]
                        if cleaned_content.startswith('```'):
                            cleaned_content = cleaned_content[3:]
                        if cleaned_content.endswith('```'):
                            cleaned_content = cleaned_content[:-3]
                        cleaned_content = cleaned_content.strip()
                        
                        import os
                        dir_path = os.path.dirname(filename)
                        if dir_path:
                            os.makedirs(dir_path, exist_ok=True)
                        
                        with open(filename, 'w') as f:
                            f.write(cleaned_content)
                        self.emit_message('file_success', f"File '{filename}' written successfully")
                    except Exception as e:
                        self.emit_message('file_error', f"Error writing file '{filename}': {e}")
        
        # Handle DONE messages
        if tags["is_done"]:
            self.emit_message('task_complete', "Task completed!")
            for msg in tags["done_messages"]:
                if msg:
                    self.emit_message('done_message', msg)
            return
        
        # Continue iteration if needed
        if commands_needing_feedback:
            feedback_prompt = (
                "Here are the results of the commands you requested:\n\n" +
                "\n\n---\n\n".join(commands_needing_feedback) +
                "\n\nPlease continue with your task. Use <COMMAND return_output=\"true\">cmd</COMMAND> "
                "for commands you need output from, <COMMAND return_output=\"false\">cmd</COMMAND> "
                "for commands without feedback, <WRITEFILE filename=\"path\">content</WRITEFILE> "
                "for files, or <DONE>message</DONE> when finished."
            )
            
            self.emit_message('info', "Sending command results to AI...")
            next_response = self.query_llm(feedback_prompt)
            self.process_response_with_iteration(next_response)
        
        elif tags["ordered_tags"] and not tags["is_done"]:
            feedback_prompt = "Operations completed successfully. Please continue with your task or use <DONE>message</DONE> when finished."
            self.emit_message('info', "Notifying AI that operations completed...")
            next_response = self.query_llm(feedback_prompt)
            self.process_response_with_iteration(next_response)

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html', agent_name=AGENT_NAME, lm_studio_url=LM_STUDIO_URL)

@app.route('/api/status')
def get_status():
    """Get system status"""
    with agent_lock:
        if agent:
            return jsonify({
                'connected': True,
                'system_info': agent._get_system_info()
            })
    return jsonify({'connected': False})

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")

@socketio.on('user_message')
def handle_message(data):
    """Handle user message"""
    user_input = data.get('message', '').strip()
    
    if not user_input:
        return
    
    with agent_lock:
        if not agent:
            emit('agent_message', {
                'type': 'error',
                'content': 'Agent not initialized'
            })
            return
        
        try:
            # Handle special commands
            if user_input.lower() == 'clear':
                agent.clear_conversation()
                emit('agent_message', {
                    'type': 'info',
                    'content': 'Conversation history cleared'
                })
                return
            elif user_input.lower() == 'status':
                system_info = agent._get_system_info()
                emit('agent_message', {
                    'type': 'system_status',
                    'content': system_info
                })
                return
            elif user_input.startswith('!'):
                cmd = user_input[1:].strip()
                if cmd:
                    agent.execute_and_show(cmd)
                return
            
            # Query the AI
            emit('agent_message', {
                'type': 'thinking',
                'content': 'Thinking...'
            })
            
            ai_response = agent.query_llm(user_input)
            agent.process_response_with_iteration(ai_response)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            emit('agent_message', {
                'type': 'error',
                'content': f"Error: {str(e)}"
            })

def init_agent():
    """Initialize the agent"""
    global agent
    with agent_lock:
        agent = WebOSAgent(socketio)
        logger.info("Agent initialized")

if __name__ == '__main__':
    init_agent()
    print(f"🌐 Starting web server for {AGENT_NAME}...")
    print(f"🔗 Access the interface at: http://0.0.0.0:5000")
    print(f"🤖 Connected to LM Studio at: {LM_STUDIO_URL}")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
