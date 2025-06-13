import json
import os

def create_system_manifest():
    """Create a comprehensive system manifest"""
    
    manifest = {
        # Core system files
        "boot.py": {
            "required": True,
            "description": "Boot loader and system initialization",
            "category": "system"
        },
        "code.py": {
            "required": True, 
            "description": "Main application entry point",
            "category": "system"
        },
        "recovery.py": {
            "required": True,
            "description": "Recovery system",
            "category": "system"
        },
        
        # Application files
        "bootmenu.py": {
            "required": False,
            "description": "Boot menu interface",
            "category": "application"
        },
        "loader.py": {
            "required": False,
            "description": "Application loader",
            "category": "application"
        },
        
        # Configuration files
        "settings.toml": {
            "required": False,
            "description": "System configuration",
            "category": "config"
        },
        
        # Directories
        "lib/": {
            "required": True,
            "description": "CircuitPython libraries",
            "category": "system"
        },
        "system/": {
            "required": True,
            "description": "System files and recovery data",
            "category": "system"
        },
        
        # Recovery files
        "system/recovery.zip": {
            "required": True,
            "description": "Core system recovery archive",
            "category": "recovery"
        },
        "system/manifest.json": {
            "required": True,
            "description": "System file manifest",
            "category": "system"
        },
        
        # Media files
        "stagetwo_boot.bmp": {
            "required": False,
            "description": "Boot splash screen",
            "category": "media"
        }
    }
    
    # Ensure system directory exists
    try:
        os.mkdir("/system")
    except OSError:
        pass  # Already exists
        
    # Write manifest
    with open("/system/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
        
    print("System manifest created successfully")
    return manifest

if __name__ == "__main__":
    create_system_manifest()
