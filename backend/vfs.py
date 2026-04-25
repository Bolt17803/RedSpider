import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class FileSystemProvider(ABC):
    """
    Abstract base class for a Virtual File System.
    This allows swapping between Local Disk, S3 Buckets, or other cloud storage
    providers without changing the core application logic.
    """
    
    @abstractmethod
    def get_tree(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Returns a hierarchical tree structure of the project directory.
        Format:
        [
            {
                "name": "src",
                "type": "directory",
                "path": "src",
                "children": [ ... ]
            },
            {
                "name": "main.py",
                "type": "file",
                "path": "main.py"
            }
        ]
        """
        pass

    @abstractmethod
    def get_file_content(self, project_id: str, file_path: str) -> str:
        """
        Returns the raw string content of the requested file.
        """
        pass


class LocalFileSystemProvider(FileSystemProvider):
    """
    Implementation of the Virtual File System using the local disk.
    """
    def __init__(self, base_playground_path: str):
        self.base_playground_path = base_playground_path

    def _get_project_root(self, project_id: str) -> str:
        # Prevent traversal attacks
        safe_project_id = os.path.basename(project_id)
        return os.path.join(self.base_playground_path, safe_project_id)

    def get_tree(self, project_id: str) -> List[Dict[str, Any]]:
        root_dir = self._get_project_root(project_id)
        if not os.path.exists(root_dir):
            return []

        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', '.env', '.next'}
        
        def build_tree(current_path: str, relative_base: str = "") -> List[Dict[str, Any]]:
            tree = []
            try:
                with os.scandir(current_path) as it:
                    entries = list(it)
                    # Sort directories first, then files alphabetically
                    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
                    
                    for entry in entries:
                        if entry.name in ignore_dirs:
                            continue
                            
                        rel_path = os.path.join(relative_base, entry.name).replace('\\', '/')
                        
                        if entry.is_dir():
                            tree.append({
                                "name": entry.name,
                                "type": "directory",
                                "path": rel_path,
                                "children": build_tree(entry.path, rel_path)
                            })
                        else:
                            tree.append({
                                "name": entry.name,
                                "type": "file",
                                "path": rel_path
                            })
            except PermissionError:
                pass
            return tree

        return build_tree(root_dir)

    def get_file_content(self, project_id: str, file_path: str) -> str:
        root_dir = self._get_project_root(project_id)
        
        # Normalize and prevent directory traversal
        safe_file_path = os.path.normpath(file_path).lstrip('/')
        if '..' in safe_file_path.split(os.sep):
            raise ValueError("Invalid file path")
            
        full_path = os.path.join(root_dir, safe_file_path)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        if not os.path.isfile(full_path):
            raise ValueError(f"Not a file: {file_path}")

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback or error for binary files
            return "[Binary file or unsupported encoding]"
        except Exception as e:
            raise Exception(f"Failed to read file: {str(e)}")
