"""
C Compiler implementation for the modular compilation system
"""

import subprocess
import os
from .base_compiler import BaseCompiler


class CCompiler(BaseCompiler):
    """
    Compiler class for C programming language
    """
    
    def __init__(self):
        super().__init__("C", ".c")
    
    def compile(self, file_path, timeout=10):
        """
        Compile C code
        :param file_path: Path to the C source file
        :param timeout: Compilation timeout in seconds
        :return: Dictionary with success, output, and error fields
        """
        # Create a temporary file for the executable
        temp_exe_path = file_path.replace('.c', '')
        
        try:
            # Compile the C code
            compile_result = subprocess.run(
                ['gcc', file_path, '-o', temp_exe_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if compile_result.returncode != 0:
                # Compilation failed
                return {
                    'success': False,
                    'output': compile_result.stdout,
                    'error': compile_result.stderr
                }
            else:
                # Compilation succeeded
                return {
                    'success': True,
                    'output': compile_result.stdout,
                    'error': compile_result.stderr if compile_result.stderr else None,
                    'executable_path': temp_exe_path
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': 'Compilation timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': f'Compilation error: {str(e)}'
            }
    
    def run(self, file_path, timeout=5):
        """
        Run compiled C program
        :param file_path: Path to the C source file (executable will be derived)
        :param timeout: Execution timeout in seconds
        :return: Dictionary with success, output, and error fields
        """
        temp_exe_path = file_path.replace('.c', '')
        
        if not os.path.exists(temp_exe_path):
            return {
                'success': False,
                'output': '',
                'error': 'Executable not found'
            }
        
        try:
            # Run the compiled program
            run_result = subprocess.run(
                [temp_exe_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result = {
                'success': True,
                'output': run_result.stdout,
                'error': run_result.stderr if run_result.stderr else None
            }
            
            # Clean up the executable
            try:
                os.remove(temp_exe_path)
            except:
                pass  # Ignore cleanup errors
            
            return result
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