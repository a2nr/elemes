"""
Compiler Factory for managing different language compilers
"""

from .c_compiler import CCompiler
from .python_compiler import PythonCompiler


class CompilerFactory:
    """
    Factory class to create and manage different language compilers
    """

    def __init__(self):
        self.compilers = {
            'c': CCompiler(),
            'python': PythonCompiler()
        }
        self.default_compiler = self.compilers['c']
    
    def get_compiler(self, language=None):
        """
        Get a compiler instance for the specified language
        :param language: Language identifier ('c', 'python', etc.)
        :return: Compiler instance
        """
        if language is None:
            return self.default_compiler
        
        language = language.lower()
        if language in self.compilers:
            return self.compilers[language]
        else:
            # Return default compiler if requested language is not available
            return self.default_compiler
    
    def get_available_languages(self):
        """
        Get list of available programming languages
        :return: List of available language identifiers
        """
        return list(self.compilers.keys())
    
    def get_language_display_name(self, language):
        """
        Get display name for a language
        :param language: Language identifier
        :return: Display name for the language
        """
        display_names = {
            'c': 'C',
            'python': 'Python'
        }
        return display_names.get(language, language.capitalize())


# Global compiler factory instance
compiler_factory = CompilerFactory()