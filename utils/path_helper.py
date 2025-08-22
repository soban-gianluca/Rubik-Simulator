import sys
import os

def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for dev and PyInstaller bundle.
    """
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except AttributeError:
        # Use the project root, not the utils folder
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)
