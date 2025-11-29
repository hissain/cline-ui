import subprocess
import json

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
    Executes a command using the cline CLI, handles the streaming output,
    and returns the final response.
    """
    command = [
        "cline",
        prompt,
        "--output-format",
        "json",
        "--mode",
        "plan"
    ]
    
    print(f"Executing command: {' '.join(command)}")
    print("Waiting for command to finish (will time out if it runs too long)...")
    
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        stdout = None
        stderr = None
        
        try:
            stdout, stderr = process.communicate(timeout=60)
            print("Command finished on its own.")
        except subprocess.TimeoutExpired:
            print("Command timed out as expected. Terminating and processing output.")
            process.kill()
            stdout, stderr = process.communicate()

        if not stdout:
            print("Error: No output captured from command.")
            if stderr:
                print(f"Stderr: {stderr}")
            return None

        # Use the robust extractor to get a list of valid JSON objects from the raw output
        json_objects = extract_json_objects(stdout)
        
        if not json_objects:
            print("Error: No valid JSON objects found in the output.")
            print("--- Full Raw Output ---")
            print(stdout)
            return None

        # Find the final answer object by searching backwards through the valid objects.
        final_object = None
        for obj in reversed(json_objects):
            if obj.get("ask") == "plan_mode_respond":
                final_object = obj
                break
        
        if final_object:
            # The actual response is a JSON string inside the 'text' field.
            response_data = json.loads(final_object["text"])
            return response_data["response"]
        else:
            print("Error: Could not find the final answer in the output.")
            print("--- Full Raw Output ---")
            print(stdout)
            return None

    except FileNotFoundError:
        print("Error: 'cline' executable not found. Make sure it's built and in your PATH.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

# Example usage
if __name__ == "__main__":
    my_prompt = "Explain the importance of reproducible builds in software engineering."
    final_answer = run_cline_command(my_prompt)
    if final_answer:
        print("\n--- Final Answer ---")
        print(final_answer)
