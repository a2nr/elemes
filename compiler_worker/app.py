import subprocess
import os
import tempfile
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

def run_c_code(code, timeout=5):
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = os.path.join(tmpdir, "program.c")
        exe_path = os.path.join(tmpdir, "program")
        
        with open(source_path, "w") as f:
            f.write(code)
            
        # Compile
        try:
            compile_res = subprocess.run(
                ["gcc", source_path, "-o", exe_path],
                capture_output=True, text=True, timeout=10
            )
            if compile_res.returncode != 0:
                return {"success": False, "output": compile_res.stdout, "error": compile_res.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Compilation timed out"}
            
        # Run
        try:
            run_res = subprocess.run(
                [exe_path],
                capture_output=True, text=True, timeout=timeout
            )
            return {"success": True, "output": run_res.stdout, "error": run_res.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Program execution timed out"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

def run_python_code(code, timeout=5):
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp.write(code.encode('utf-8'))
        tmp_path = tmp.name
        
    try:
        run_res = subprocess.run(
            ["python3", tmp_path],
            capture_output=True, text=True, timeout=timeout
        )
        return {"success": True, "output": run_res.stdout, "error": run_res.stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "Program execution timed out"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.route('/execute', methods=['POST'])
def execute():
    data = request.json
    code = data.get("code", "")
    language = data.get("language", "").lower()
    
    if language == "c":
        return jsonify(run_c_code(code))
    elif language == "python":
        return jsonify(run_python_code(code))
    else:
        return jsonify({"success": False, "output": "", "error": f"Unsupported language: {language}"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
