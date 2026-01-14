"""
Python Compiler/Interpreter implementation for the modular compilation system
"""

import subprocess
import tempfile
import os
from .base_compiler import BaseCompiler


class PythonCompiler(BaseCompiler):
    """
    Compiler/Interpreter class for Python programming language
    """
    
    def __init__(self):
        super().__init__("Python", ".py")
    
    def compile(self, file_path, timeout=10):
        """
        Check Python syntax (simulate compilation)
        :param file_path: Path to the Python source file
        :param timeout: Compilation timeout in seconds
        :return: Dictionary with success, output, and error fields
        """
        try:
            # Use Python's compile function to check syntax
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Attempt to compile the code to check for syntax errors
            compile(code, file_path, 'exec')
            
            # If we reach this point, syntax is valid
            return {
                'success': True,
                'output': '',
                'error': None
            }
        except SyntaxError as e:
            return {
                'success': False,
                'output': '',
                'error': f"SyntaxError: {e.msg} at line {e.lineno}"
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': f'Syntax check error: {str(e)}'
            }
    
    def run(self, file_path, timeout=5):
        """
        Run Python code
        :param file_path: Path to the Python source file
        :param timeout: Execution timeout in seconds
        :return: Dictionary with success, output, and error fields
        """
        try:
            # Run the Python script
            run_result = subprocess.run(
                ['python3', file_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'success': True,
                'output': run_result.stdout,
                'error': run_result.stderr if run_result.stderr else None
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': 'Program execution timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': f'Runtime error: {str(e)}'
            }