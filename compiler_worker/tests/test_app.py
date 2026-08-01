"""Regression tests for compiler_worker stdin passthrough.

compiler_worker/ is NOT a Python package — app.py is a standalone Flask
module. It is loaded via importlib from its absolute path.
"""

import os
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_PATH = os.path.join(os.path.dirname(_HERE), "app.py")

spec = importlib.util.spec_from_file_location("worker_app", _APP_PATH)
worker_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker_app)


# --- Python input() ---------------------------------------------------------


def test_python_input_single_line_with_stdin():
    code = 'nama = input("Siapa nama kamu? ")\nprint(f"Halo, {nama}!")\n'
    result = worker_app.run_python_code(code, stdin="Budi\n")
    assert result["success"] is True
    assert "Halo, Budi!" in result["output"]


def test_python_input_multiple_lines_with_stdin():
    code = (
        'nama = input("Nama: ")\n'
        'umur = input("Umur: ")\n'
        'print(f"{nama} berumur {umur} tahun")\n'
    )
    result = worker_app.run_python_code(code, stdin="Budi\n17\n")
    assert result["success"] is True
    assert "Budi berumur 17 tahun" in result["output"]


def test_python_input_empty_stdin_raises_eoferror():
    code = 'nama = input("Siapa nama kamu? ")\nprint(f"Halo, {nama}!")\n'
    result = worker_app.run_python_code(code, stdin="")
    # Worker reports success even when the child process exits with an error
    # (subprocess returncode is not checked); the traceback lands in stderr.
    assert result["success"] is True
    assert "EOFError" in result["error"]


# --- C scanf() --------------------------------------------------------------


def test_c_scanf_single_line_with_stdin():
    code = (
        "#include <stdio.h>\n"
        "int main() {\n"
        "    char nama[32];\n"
        "    scanf(\"%31s\", nama);\n"
        "    printf(\"Halo, %s!\\n\", nama);\n"
        "    return 0;\n"
        "}\n"
    )
    result = worker_app.run_c_code(code, stdin="Budi\n")
    assert result["success"] is True
    assert "Halo, Budi!" in result["output"]


def test_c_scanf_empty_stdin_returns_no_output():
    code = (
        "#include <stdio.h>\n"
        "int main() {\n"
        "    char nama[32] = \"\";\n"
        "    if (scanf(\"%31s\", nama) != 1) {\n"
        "        return 1;\n"
        "    }\n"
        "    printf(\"Halo, %s!\\n\", nama);\n"
        "    return 0;\n"
        "}\n"
    )
    result = worker_app.run_c_code(code, stdin="")
    assert result["success"] is True
    assert "Halo," not in result["output"]
