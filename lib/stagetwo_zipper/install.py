"""
Installation script for zlib_compat
Automatically detects and sets up zlib compatibility for CircuitPython
"""

import os
import sys

def check_zlib_availability():
    """Check if zlib is available and working"""
    try:
        import zlib
        # Test basic functionality
        test_data = b"test"
        compressed = zlib.compress(test_data)
        decompressed = zlib.decompress(compressed)
        if decompressed == test_data:
            print("✅ Standard zlib is available and working")
            return True
        else:
            print("⚠️ Standard zlib available but not working correctly")
            return False
    except ImportError:
        print("❌ Standard zlib not available")
        return False
    except Exception as e:
        print(f"⚠️ Standard zlib error: {e}")
        return False

def install_zlib_compat():
    """Install zlib_compat if needed"""
    if check_zlib_availability():
        print("Standard zlib is working, zlib_compat not needed")
        return True
    
    print("Installing zlib_compat...")
    
    # Check if zlib_compat.py exists
    if os.path.exists("zlib_compat.py"):
        print("✅ zlib_compat.py already exists")
    else:
        print("❌ zlib_compat.py not found - please ensure it's in the same directory")
        return False
    
    # Test zlib_compat
    try:
        import zlib_compat
        if zlib_compat.test_zlib_compat():
            print("✅ zlib_compat installed and tested successfully")
            return True
        else:
            print("❌ zlib_compat test failed")
            return False
    except Exception as e:
        print(f"❌ zlib_compat import failed: {e}")
        return False

def setup_zipper_with_compat():
    """Setup zipper.py to use zlib_compat if needed"""
    print("Setting up zipper with zlib compatibility...")
    
    # Test zipper functionality
    try:
        import zipper
        
        # Test basic functionality
        test_files = []
        
        # Create a test file
        with open("test_zipper_file.txt", "w") as f:
            f.write("This is a test file for zipper functionality.\n")
        test_files.append("test_zipper_file.txt")
        
        # Test zip creation (store mode)
        zipper.zip_files("test_store.zip", test_files, mode="store")
        print("✅ Store mode zip creation successful")
        
        # Test zip creation (deflate mode if available)
        try:
            zipper.zip_files("test_deflate.zip", test_files, mode="deflate")
            print("✅ Deflate mode zip creation successful")
        except RuntimeError as e:
            print(f"⚠️ Deflate mode not available: {e}")
        
        # Test extraction
        zipper.unzip("test_store.zip", "test_extract/")
        print("✅ Zip extraction successful")
        
        # Verify extracted content
        with open("test_extract/test_zipper_file.txt", "r") as f:
            content = f.read()
        
        if "This is a test file" in content:
            print("✅ Extracted content verified")
        else:
            print("❌ Extracted content verification failed")
            return False
        
        # Cleanup
        cleanup_files = [
            "test_zipper_file.txt",
            "test_store.zip",
            "test_deflate.zip",
            "test_extract/test_zipper_file.txt"
        ]
        
        for file in cleanup_files:
            try:
                os.remove(file)
            except:
                pass
        
        try:
            os.rmdir("test_extract")
        except:
            pass
        
        print("✅ Zipper setup and test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Zipper setup failed: {e}")
        return False

def main():
    """Main installation function"""
    print("=== zlib Compatibility Setup for StageTwo ===")
    print()
    
    # Check Python version and platform
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()
    
    # Step 1: Check zlib availability
    print("Step 1: Checking zlib availability...")
    zlib_available = check_zlib_availability()
    print()
    
    # Step 2: Install zlib_compat if needed
    if not zlib_available:
        print("Step 2: Installing zlib_compat...")
        if not install_zlib_compat():
            print("❌ Installation failed")
            return False
    else:
        print("Step 2: zlib_compat not needed")
    print()
    
    # Step 3: Test zipper functionality
    print("Step 3: Testing zipper functionality...")
    if not setup_zipper_with_compat():
        print("❌ Zipper setup failed")
        return False
    print()
    
    print("✅ All setup completed successfully!")
    print()
    print("Your zipper.py is now ready to use with compression support.")
    print("It will automatically use the best available compression library:")
    print("  - Standard zlib (if available)")
    print("  - zlib_compat (fallback for CircuitPython)")
    print("  - Store mode only (if no compression available)")
    
    return True

if __name__ == "__main__":
    main()
