"""Type definitions for the application"""

from typing import Optional

from app.core.vector_store.vector_manager import VectorManager


class AppState:
    """Application state type definition

    This class defines the structure of app.state for type checking
    and IDE support.
    """

    def __init__(self):
        self.vector_manager: Optional[VectorManager] = None

    def __setattr__(self, name: str, value) -> None:
        """Override __setattr__ to allow dynamic attribute setting"""
        object.__setattr__(self, name, value)

    def __getattr__(self, name: str):
        """Override __getattr__ to handle dynamic attributes"""
        # This allows for additional attributes to be added dynamically
        # while maintaining type safety for known attributes
        return object.__getattribute__(self, name)
