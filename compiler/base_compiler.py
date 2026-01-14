"""
Base compiler class for the modular compilation system
"""

import os
import subprocess
import tempfile
from abc import ABC, abstractmethod


class BaseCompiler(ABC):
    """
    Abstract base class for all compilers
    """
    
    def __init__(self, language, file_extension):
        self.language = language
        self.file_extension = file_extension
    
    @abstractmethod
    def compile(self, code, timeout=10):
        """
        Compile the code and return the result
        :param code: Source code to compile
        :param timeout: Compilation timeout in seconds
        :return: Dictionary with success, output, and error fields
        """
        pass
    
    @abstractmethod
    def run(self, file_path, timeout=5):
        """
        Run the compiled code and return the result
        :param file_path: Path to the compiled file
        :param timeout: Execution timeout in seconds
        :return: Dictionary with success, output, and error fields
        """
        pass
    
    def compile_and_run(self, code, compile_timeout=10, run_timeout=5):
        """
        Compile and run the code in one step
        :param code: Source code to compile and run
        :param compile_timeout: Compilation timeout in seconds
        :param run_timeout: Execution timeout in seconds
        :return: Dictionary with success, output, and error fields
        """
        # Create a temporary file for the source code
        with tempfile.NamedTemporaryFile(mode='w', suffix=self.file_extension, delete=False) as temp_source:
            temp_source.write(code)
            temp_source_path = temp_source.name
        
        try:
            # Compile the code
            compile_result = self.compile(temp_source_path, compile_timeout)
            
            if not compile_result['success']:
                return compile_result
            
            # Run the code
            run_result = self.run(temp_source_path, run_timeout)
            return run_result
            
        finally:
            # Clean up temporary files
            try:
                os.remove(temp_source_path)
            except:
                pass  # Ignore cleanup errors