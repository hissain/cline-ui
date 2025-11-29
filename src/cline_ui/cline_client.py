import subprocess
import json
import os
import shutil
import time

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

def run_cline_command(prompt):
    """
    Executes a command using the cline CLI, streams output, and returns the final response
    as soon as it is detected.
    """
    print(f"[{time.time()}] Starting run_cline_command")
    cline_path = get_cline_path()
    if not cline_path:
        return "Error: 'cline' executable not found. Please configure the correct path in the settings."

    command = [
        cline_path,
        prompt,
        "--output-format",
        "json",
        "--mode",
        "plan"
    ]
    
    process = None
    try:
        print(f"[{time.time()}] Running command: {' '.join(command)}")
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            bufsize=1  # Line buffered
        )
        
        print(f"[{time.time()}] Streaming output...")
        accumulated_stdout = ""
        start_time = time.time()
        max_wait_time = 120 # Safety net
        
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
                
                final_object = None
                for obj in reversed(json_objects):
                    if obj.get("ask") == "plan_mode_respond":
                        final_object = obj
                        break
                
                if final_object:
                    print(f"[{time.time()}] Found final answer object while streaming.")
                    process.kill() # We got what we wanted
                    response_data = json.loads(final_object["text"])
                    return response_data["response"]
            
            # If line is empty, it means EOF (process closed stdout)
            if not line:
                break

        # If we get here, we either timed out or process finished without early exit
        print(f"[{time.time()}] Process finished or timed out.")
        if process.poll() is None:
            process.kill()
            
        stdout, stderr = process.communicate()
        accumulated_stdout += stdout
        
        if not accumulated_stdout:
            if stderr:
                return f"Error: {stderr}"
            return "Error: No output captured from command."

        json_objects = extract_json_objects(accumulated_stdout)
        if not json_objects:
            return f"Error: No valid JSON objects found in the output. Full output: {accumulated_stdout}"

        final_object = None
        for obj in reversed(json_objects):
            if obj.get("ask") == "plan_mode_respond":
                final_object = obj
                break
        
        if final_object:
             response_data = json.loads(final_object["text"])
             return response_data["response"]
        else:
            return f"Error: Could not find the final answer in the output. Full output: {accumulated_stdout}"

    except FileNotFoundError:
        return f"Error: '{cline_path}' executable not found. Please configure the correct path in the settings."
    except Exception as e:
        if process:
             try:
                 process.kill()
             except:
                 pass
        return f"An unexpected error occurred: {e}"
