"""
JSON report hooks for pytest.
This file contains hooks specific to pytest-json-report plugin.
It should only be loaded when the json-report plugin is being used.
"""

def pytest_json_runtest_metadata(item, call):
    """Add bundle and points information to JSON report metadata."""
    # Only add metadata during setup phase
    if call.when != "setup":
        return {}
    
    metadata = {}
    
    # Extract bundle and points from markers
    for marker in item.iter_markers():
        if marker.name == "bundle" and marker.args:
            metadata["bundle"] = marker.args[0]
        elif marker.name == "points" and marker.args:
            metadata["points"] = marker.args[0]
    
    # Ensure defaults if not specified
    if "bundle" not in metadata:
        metadata["bundle"] = 1
    if "points" not in metadata:
        metadata["points"] = 0
        
    return metadata