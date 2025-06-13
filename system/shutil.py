"""
Simplified shutil module for CircuitPython
Provides basic file and directory operations similar to CPython's shutil
"""
import os
import gc

def copy(src, dst):
    """
    Copy a file from src to dst.
    
    Args:
        src (str): Source file path
        dst (str): Destination file path
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # If dst is a directory, use the source filename
        try:
            os.listdir(dst)
            # It's a directory, so append the source filename
            dst = dst + "/" + src.split("/")[-1]
        except OSError:
            # Not a directory, use dst as is
            pass
        
        # Copy the file
        with open(src, "rb") as src_file:
            with open(dst, "wb") as dst_file:
                while True:
                    chunk = src_file.read(1024)
                    if not chunk:
                        break
                    dst_file.write(chunk)
                    # Force garbage collection to avoid memory issues
                    gc.collect()
        return True
    except Exception as e:
        print(f"Error copying {src} to {dst}: {e}")
        return False

def copyfile(src, dst):
    """
    Copy a file from src to dst.
    
    Args:
        src (str): Source file path
        dst (str): Destination file path
    
    Returns:
        bool: True if successful, False otherwise
    """
    return copy(src, dst)

def copytree(src, dst, ignore=None):
    """
    Recursively copy a directory tree from src to dst.
    
    Args:
        src (str): Source directory path
        dst (str): Destination directory path
        ignore (callable): Function that takes a directory path and list of contents,
                          returns a list of names to ignore (not implemented)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Create destination directory if it doesn't exist
    try:
        os.listdir(dst)
    except OSError:
        try:
            os.mkdir(dst)
        except OSError as e:
            print(f"Error creating directory {dst}: {e}")
            return False
    
    # Get list of files and directories in source
    try:
        items = os.listdir(src)
    except OSError as e:
        print(f"Error listing directory {src}: {e}")
        return False
    
    success = True
    
    # Copy each item
    for item in items:
        src_path = f"{src}/{item}"
        dst_path = f"{dst}/{item}"
        
        try:
            # Check if item is a directory
            try:
                os.listdir(src_path)
                is_dir = True
            except OSError:
                is_dir = False
            
            if is_dir:
                # Recursively copy directory
                if not copytree(src_path, dst_path, ignore):
                    success = False
            else:
                # Copy file
                if not copy(src_path, dst_path):
                    success = False
        except Exception as e:
            print(f"Error processing {src_path}: {e}")
            success = False
    
    return success

def rmtree(path):
    """
    Recursively delete a directory tree.
    
    Args:
        path (str): Directory path to delete
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get list of files and directories
        items = os.listdir(path)
        
        # Delete each item
        for item in items:
            item_path = f"{path}/{item}"
            
            try:
                # Check if item is a directory
                try:
                    os.listdir(item_path)
                    is_dir = True
                except OSError:
                    is_dir = False
                
                if is_dir:
                    # Recursively delete directory
                    rmtree(item_path)
                else:
                    # Delete file
                    os.remove(item_path)
            except Exception as e:
                print(f"Error deleting {item_path}: {e}")
                return False
        
        # Delete the directory itself
        os.rmdir(path)
        return True
    except Exception as e:
        print(f"Error deleting directory tree {path}: {e}")
        return False

def disk_usage(path):
    """
    Return disk usage statistics for the given path.
    
    Args:
        path (str): Path to check
    
    Returns:
        tuple: (total, used, free) in bytes, or None if not available
    """
    try:
        import storage
        
        # Try to get the filesystem stats
        fs_stat = os.statvfs(path)
        if fs_stat:
            block_size = fs_stat[0]
            total_blocks = fs_stat[2]
            free_blocks = fs_stat[3]
            
            total = block_size * total_blocks
            free = block_size * free_blocks
            used = total - free
            
            return (total, used, free)
    except:
        pass
    
    return None

def which(cmd):
    """
    Return the path to an executable (not implemented in CircuitPython).
    
    Args:
        cmd (str): Command name
    
    Returns:
        None: Always returns None in CircuitPython
    """
    return None
