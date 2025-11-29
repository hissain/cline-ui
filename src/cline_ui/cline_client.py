import subprocess
import json
import os
import shutil
import time
import re

def find_cline_executable():
    """
    Finds the cline executable in common locations.
    """
    # 1. Check PATH
    path = shutil.which("cline")
    if path:
        return path

    # 2. Check common installation directories
    home = os.path.expanduser("~")
    common_paths = [
        os.path.join(home, ".nvm/versions/node/v22.18.0/bin/cline"),
        "/usr/local/bin/cline",
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    
    return None

def get_cline_path():
    """
    Gets the path to the cline executable from the settings file,
    or auto-detects it.
    """
    settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
    if os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            path = settings.get('cline_path')
            if path and os.path.exists(path):
                return path

    # If not in settings or path is invalid, auto-detect
    return find_cline_executable()

def extract_json_objects(text):
    """
    Finds and parses all valid JSON objects from a string that may contain other text.
    Handles pretty-printed JSON across multiple lines.
    """
    json_objects = []
    brace_level = 0
    start_index = -1

    for i, char in enumerate(text):
        if char == '{':
            if brace_level == 0:
                start_index = i
            brace_level += 1
        elif char == '}':
            if brace_level > 0:
                brace_level -= 1
                if brace_level == 0 and start_index != -1:
                    substring = text[start_index:i+1]
                    try:
                        # Try to parse the found substring as a JSON object
                        json_obj = json.loads(substring)
                        json_objects.append(json_obj)
                    except json.JSONDecodeError:
                        # This substring wasn't a valid JSON object, so we ignore it
                        pass
                    start_index = -1
    return json_objects

def run_cline_command(prompt, update_callback=None, task_id=None):
    """
    Executes a command using the cline CLI, streams output, and returns the final response
    as soon as it is detected.
    """
    print(f"[{time.time()}] Starting run_cline_command")
    cline_path = get_cline_path()
    if not cline_path:
        return {"response": "Error: 'cline' executable not found. Please configure the correct path in the settings.", "task_id": None}

    # Append instruction to avoid browser if requested
    enhanced_prompt = prompt + " (NOTE: Do not use the browser tool. Answer directly from your knowledge.)"

    if task_id:
        # Resume existing task
        command = [
            cline_path,
            "task",
            "open",
            task_id,
            "--output-format",
            "json",
            "--mode",
            "act", # Use act mode when resuming to ensure interaction
            "--yolo",
            "--verbose"
        ]
        # We will pipe the prompt to stdin
    else:
        # New task
        command = [
            cline_path,
            enhanced_prompt,
            "--output-format",
            "json",
            "--mode",
            "plan",
            "--yolo",
            "--verbose"
        ]
    
    process = None
    try:
        print(f"[{time.time()}] Running command: {' '.join(command)}")
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            stdin=subprocess.PIPE if task_id else None,
            text=True,
            bufsize=1  # Line buffered
        )
        
        if task_id:
            try:
                print(f"[{time.time()}] Sending prompt to stdin for task {task_id}")
                if not enhanced_prompt.endswith('\n'):
                    enhanced_prompt += '\n'
                # Add extra newline to ensure it triggers
                process.stdin.write(enhanced_prompt + "\n")
                process.stdin.flush()
                # Give it a moment to latch on?
                time.sleep(2) 
                process.stdin.close()
                process.stdin = None # Prevent communicate from using closed stdin
            except Exception as e:
                print(f"[{time.time()}] Error writing to stdin: {e}")
        
        print(f"[{time.time()}] Streaming output...")
        accumulated_stdout = ""
        start_time = time.time()
        max_wait_time = 600 # Safety net (10 minutes)
        
        processed_count = 0
        detected_task_id = task_id

        while True:
            # Check for timeout
            if time.time() - start_time > max_wait_time:
                print(f"[{time.time()}] Max wait time exceeded.")
                break
            
            # Read a line (non-blocking if possible, but here we rely on readline)
            line = process.stdout.readline()
            
            if line:
                print(f"[{time.time()}] Read line: {line.strip()[:100]}...") # Print first 100 chars
                accumulated_stdout += line
                # Try to parse JSON objects from what we have so far
                print(f"[{time.time()}] Attempting to extract JSON objects...")
                json_objects = extract_json_objects(accumulated_stdout)
                
                # Process new objects
                new_objects = json_objects[processed_count:]
                for obj in new_objects:
                    processed_count += 1
                    status = None
                    if obj.get("say"):
                        say_type = obj.get("say")
                        if say_type == "api_req_started":
                            status = "Processing: API Request Started..."
                        elif say_type == "error_retry":
                            status = "Processing: API Request Failed, Retrying..."
                        elif say_type == "api_req_retried":
                            status = "Processing: API Request Retried..."
                        elif say_type == "text":
                            # We don't want to show full text stream as status, maybe just "Processing..."
                            pass
                        elif say_type == "checkpoint_created":
                            status = "Processing: Checkpoint created..."
                        else:
                            status = f"Processing: {say_type}..."
                    elif obj.get("ask") == "tool":
                         status = "Processing: Executing tool..."
                    
                    if status and update_callback:
                        update_callback(status)

                # Fallback: Parse verbose debug logs for status if no JSON object
                if not new_objects:
                    debug_match = re.search(r'\[DEBUG\]: State message \d+: type=say, say=(\w+)', line)
                    if debug_match:
                        say_type = debug_match.group(1)
                        status = None
                        if say_type == "api_req_started":
                            status = "Processing: API Request Started..."
                        elif say_type == "api_req_retried":
                             status = "Processing: API Request Retried..."
                        elif say_type == "checkpoint_created":
                             status = "Processing: Checkpoint created..."
                        
                        if status and update_callback:
                            update_callback(status)

                # Detect Task ID if new task
                if not detected_task_id:
                    task_id_match = re.search(r'Task created successfully with ID: (\d+)', accumulated_stdout)
                    if task_id_match:
                        detected_task_id = task_id_match.group(1)
                        print(f"[{time.time()}] Detected new Task ID: {detected_task_id}")

                final_object = None
                for obj in reversed(json_objects):
                    if obj.get("ask") == "plan_mode_respond":
                        final_object = obj
                        break
                
                if final_object:
                    print(f"[{time.time()}] Found final answer object while streaming.")
                    process.kill() # We got what we wanted
                    response_data = json.loads(final_object["text"])
                    return {"response": response_data["response"], "task_id": detected_task_id}
            
            # If line is empty, it means EOF (process closed stdout)
            if not line:
                break

        # If we get here, we either timed out or process finished without early exit
        print(f"[{time.time()}] Process finished or timed out.")
        if process.poll() is None:
            process.kill()
            
        stdout, stderr = process.communicate()
        accumulated_stdout += stdout
        
        # Final attempt to find Task ID if needed
        if not detected_task_id:
             task_id_match = re.search(r'Task created successfully with ID: (\d+)', accumulated_stdout)
             if task_id_match:
                 detected_task_id = task_id_match.group(1)

        if not accumulated_stdout:
            if stderr:
                return {"response": f"Error: {stderr}", "task_id": detected_task_id}
            return {"response": "Error: No output captured from command.", "task_id": detected_task_id}

        json_objects = extract_json_objects(accumulated_stdout)
        if not json_objects:
            return {"response": f"Error: No valid JSON objects found in the output. Full output: {accumulated_stdout}", "task_id": detected_task_id}

        final_object = None
        for obj in reversed(json_objects):
            if obj.get("ask") == "plan_mode_respond":
                final_object = obj
                break
        
        if final_object:
             response_data = json.loads(final_object["text"])
             return {"response": response_data["response"], "task_id": detected_task_id}
        else:
            return {"response": f"Error: Could not find the final answer in the output. Full output: {accumulated_stdout}", "task_id": detected_task_id}

    except FileNotFoundError:
        return {"response": f"Error: '{cline_path}' executable not found. Please configure the correct path in the settings.", "task_id": None}
    except Exception as e:
        if process:
             try:
                 process.kill()
             except:
                 pass
        return {"response": f"An unexpected error occurred: {e}", "task_id": None}
