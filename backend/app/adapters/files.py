from typing import Any, Dict


# In-memory file store for demo purposes
_file_store: Dict[str, str] = {}


def read_file(params: Dict[str, Any]) -> Dict[str, Any]:
    """Read a file.
    
    Expected params:
    - path: string
    """
    if "path" not in params:
        raise ValueError("Missing required field: path")
    
    path = params["path"]
    content = _file_store.get(path, "")
    
    return {
        "path": path,
        "content": content
    }


def write_file(params: Dict[str, Any]) -> Dict[str, Any]:
    """Write a file.
    
    Expected params:
    - path: string
    - content: string
    """
    required_fields = ["path", "content"]
    for field in required_fields:
        if field not in params:
            raise ValueError(f"Missing required field: {field}")
    
    path = params["path"]
    content = params["content"]
    
    _file_store[path] = content
    
    return {
        "path": path,
        "status": "written"
    }
