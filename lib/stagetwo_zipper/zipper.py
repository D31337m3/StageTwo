import struct
import os

# Enhanced zlib import with fallback chain
COMPRESSION_AVAILABLE = False
COMPRESSION_TYPE = "none"

try:
    import zlib
    COMPRESSION_AVAILABLE = True
    COMPRESSION_TYPE = "standard"
    print("Using standard zlib library")
except ImportError:
    try:
        import zlib_compat as zlib
        COMPRESSION_AVAILABLE = True
        COMPRESSION_TYPE = "compat"
        print("Using zlib_compat library")
    except ImportError:
        zlib = None
        print("No compression library available - store mode only")

# --- ZIP constants ---
ZIP_STORED = 0  # No compression
ZIP_DEFLATED = 8  # Deflate compression

def get_compression_info():
    """Get information about available compression"""
    return {
        "available": COMPRESSION_AVAILABLE,
        "type": COMPRESSION_TYPE,
        "library": "zlib" if COMPRESSION_TYPE == "standard" else "zlib_compat" if COMPRESSION_TYPE == "compat" else None
    }

def zip_files(zip_path, file_list, mode="store", compression_level=1):
    """
    Create a ZIP archive from file_list.
    
    Args:
        zip_path: Path to output ZIP file
        file_list: List of files to include
        mode: "store" (no compression) or "deflate" (compression if available)
        compression_level: 0-9, where 0=no compression, 1=fast, 9=best (limited support in compat mode)
    """
    if mode not in ("store", "deflate"):
        raise ValueError("mode must be 'store' or 'deflate'")
    
    if mode == "deflate" and not COMPRESSION_AVAILABLE:
        print("Warning: Deflate mode requested but no compression available, falling back to store mode")
        mode = "store"
    
    central_dir = []
    offset = 0
    files_processed = 0
    total_uncompressed = 0
    total_compressed = 0

    print(f"Creating ZIP archive: {zip_path}")
    print(f"Compression mode: {mode}")
    if mode == "deflate":
        print(f"Compression type: {COMPRESSION_TYPE}")
        print(f"Compression level: {compression_level}")

    with open(zip_path, "wb") as zf:
        for fname in file_list:
            if not os.path.exists(fname):
                print(f"Warning: File not found: {fname}")
                continue
                
            print(f"Processing: {fname}")
            
            try:
                with open(fname, "rb") as f:
                    data = f.read()
            except Exception as e:
                print(f"Error reading {fname}: {e}")
                continue
            
            original_size = len(data)
            total_uncompressed += original_size
            
            if mode == "deflate" and COMPRESSION_AVAILABLE:
                try:
                    # Use raw deflate (no zlib header), appropriate level for memory efficiency
                    level = max(0, min(compression_level, 1 if COMPRESSION_TYPE == "compat" else 9))
                    compressor = zlib.compressobj(level=level, wbits=-15)
                    compressed = compressor.compress(data)
                    compressed += compressor.flush()
                    
                    # Only use compression if it actually reduces size
                    if len(compressed) < original_size:
                        data_to_write = compressed
                        compress_type = ZIP_DEFLATED
                        comp_size = len(compressed)
                        print(f"  Compressed: {original_size} -> {comp_size} bytes ({comp_size/original_size:.1%})")
                    else:
                        data_to_write = data
                        compress_type = ZIP_STORED
                        comp_size = len(data)
                        print(f"  Stored (compression not beneficial): {original_size} bytes")
                        
                except Exception as e:
                    print(f"  Compression failed for {fname}: {e}, using store mode")
                    data_to_write = data
                    compress_type = ZIP_STORED
                    comp_size = len(data)
            else:
                data_to_write = data
                compress_type = ZIP_STORED
                comp_size = len(data)
                print(f"  Stored: {original_size} bytes")
            
            total_compressed += comp_size
            
            # Calculate CRC32
            crc32 = _calculate_crc32(data)
            
            # Local file header
            local_header = struct.pack(
                "<4s2B4HL2L2H",
                b"PK\x03\x04",  # signature
                20, 0,          # version, flags
                compress_type,  # compression
                0, 0,           # mod time/date (simplified)
                crc32,          # crc32
                comp_size, len(data),  # compressed, uncompressed sizes
                len(fname), 0   # name len, extra len
            )
            
            zf.write(local_header)
            zf.write(fname.encode('utf-8'))
            zf.write(data_to_write)
            
            # Central directory entry
            central_dir.append((
                fname, offset, comp_size, len(data), compress_type, crc32
            ))
            offset += len(local_header) + len(fname.encode('utf-8')) + comp_size
            files_processed += 1
        
        # Write central directory
        cd_start = offset
        for fname, file_offset, comp_size, uncomp_size, compress_type, crc32 in central_dir:
            cd_header = struct.pack(
                "<4s4B4HL3L5H2L",
                b"PK\x01\x02",  # signature
                20, 20, 0, 0,   # version made by, version needed, flags
                compress_type,  # compression method
                0, 0,           # mod time/date
                crc32,          # crc32
                comp_size, uncomp_size,  # compressed, uncompressed sizes
                len(fname.encode('utf-8')), 0, 0, 0, 0,  # name, extra, comment lens, disk, internal attr
                0, file_offset  # external attr, local header offset
            )
            zf.write(cd_header)
            zf.write(fname.encode('utf-8'))
            offset += len(cd_header) + len(fname.encode('utf-8'))
        
        # End of central directory record
        eocd = struct.pack(
            "<4s4H2LH",
            b"PK\x05\x06",  # signature
            0, 0,           # disk numbers
            len(central_dir), len(central_dir),  # entries
            offset - cd_start, cd_start,  # central dir size, offset
            0               # comment length
        )
        zf.write(eocd)
    
    # Summary
    print(f"✅ ZIP archive created successfully!")
    print(f"Files processed: {files_processed}")
    print(f"Total uncompressed: {total_uncompressed} bytes")
    print(f"Total compressed: {total_compressed} bytes")
    if total_uncompressed > 0:
        ratio = total_compressed / total_uncompressed
        print(f"Overall compression ratio: {ratio:.1%}")

def unzip(zip_path, out_dir=".", verify_crc=True):
    """
    Extract all files from a ZIP archive.
    
    Args:
        zip_path: Path to ZIP file
        out_dir: Output directory
        verify_crc: Whether to verify CRC32 checksums
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")
    
    print(f"Extracting ZIP archive: {zip_path}")
    print(f"Output directory: {out_dir}")
    
    files_extracted = 0
    total_compressed = 0
    total_uncompressed = 0
    
    with open(zip_path, "rb") as zf:
        while True:
            sig = zf.read(4)
            if not sig:
                break
                
            if sig == b"PK\x03\x04":  # Local file header
                version = struct.unpack("<H", zf.read(2))[0]
                flags = struct.unpack("<H", zf.read(2))[0]
                comp_method = struct.unpack("<H", zf.read(2))[0]
                mod_time = struct.unpack("<H", zf.read(2))[0]
                mod_date = struct.unpack("<H", zf.read(2))[0]
                crc32_stored = struct.unpack("<L", zf.read(4))[0]
                comp_size = struct.unpack("<L", zf.read(4))[0]
                uncomp_size = struct.unpack("<L", zf.read(4))[0]
                name_len = struct.unpack("<H", zf.read(2))[0]
                extra_len = struct.unpack("<H", zf.read(2))[0]
                
                fname = zf.read(name_len).decode('utf-8')
                extra_data = zf.read(extra_len)
                compressed_data = zf.read(comp_size)
                
                print(f"Extracting: {fname}")
                
                # Decompress data
                if comp_method == ZIP_STORED:
                    out_data = compressed_data
                elif comp_method == ZIP_DEFLATED:
                    if not COMPRESSION_AVAILABLE:
                        raise RuntimeError(f"Cannot extract {fname}: deflate compression not supported (no zlib available)")
                    
                    try:
                        # Use raw inflate (no zlib header)
                        decompressor = zlib.decompressobj(wbits=-15)
                        out_data = decompressor.decompress(compressed_data)
                        print(f"  Decompressed: {comp_size} -> {len(out_data)} bytes")
                    except Exception as e:
                        raise RuntimeError(f"Decompression failed for {fname}: {e}")
                else:
                    raise NotImplementedError(f"Compression method {comp_method} not supported for {fname}")
                
                # Verify size
                if len(out_data) != uncomp_size:
                    raise RuntimeError(f"Size mismatch for {fname}: expected {uncomp_size}, got {len(out_data)}")
                
                # Verify CRC32 if requested and available
                if verify_crc and crc32_stored != 0:
                    calculated_crc32 = _calculate_crc32(out_data)
                    if calculated_crc32 != crc32_stored:
                        print(f"⚠️ Warning: CRC32 mismatch for {fname} (expected {crc32_stored:08x}, got {calculated_crc32:08x})")
                
                # Create output path
                out_path = os.path.join(out_dir, fname)
                out_dir_path = os.path.dirname(out_path)
                
                # Create directories if needed
                if out_dir_path and out_dir_path != "." and out_dir_path != out_dir:
                    _makedirs(out_dir_path)
                
                # Write extracted file
                try:
                    with open(out_path, "wb") as out_file:
                        out_file.write(out_data)
                    print(f"  ✅ Extracted to: {out_path}")
                except Exception as e:
                    print(f"  ❌ Failed to write {out_path}: {e}")
                    continue
                
                files_extracted += 1
                total_compressed += comp_size
                total_uncompressed += len(out_data)
                
            elif sig == b"PK\x01\x02":  # Central directory file header
                # Skip central directory entries
                zf.read(42)  # Fixed part of central directory header
                name_len = struct.unpack("<H", zf.read(2))[0]
                extra_len = struct.unpack("<H", zf.read(2))[0]
                comment_len = struct.unpack("<H", zf.read(2))[0]
                zf.read(12)  # Rest of fixed part
                zf.read(name_len + extra_len + comment_len)  # Variable parts
                
            elif sig == b"PK\x05\x06":  # End of central directory
                break
            else:
                # Unknown signature, try to continue
                print(f"⚠️ Warning: Unknown signature: {sig}")
                break
    
    # Summary
    print(f"✅ Extraction completed!")
    print(f"Files extracted: {files_extracted}")
    print(f"Total compressed data: {total_compressed} bytes")
    print(f"Total uncompressed data: {total_uncompressed} bytes")

def _makedirs(path):
    """Create directories recursively"""
    try:
        parts = path.split('/')
        current = ""
        for part in parts:
            if part:  # Skip empty parts
                current = current + "/" + part if current else part
                try:
                    os.mkdir(current)
                except OSError:
                    pass  # Directory might already exist
    except Exception as e:
        print(f"Warning: Could not create directory {path}: {e}")

def _calculate_crc32(data):
    """Calculate CRC32 checksum (IEEE 802.3 polynomial)"""
    # Pre-computed CRC32 table for better performance
    if not hasattr(_calculate_crc32, 'table'):
        _calculate_crc32.table = []
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
            _calculate_crc32.table.append(crc)
    
    crc = 0xFFFFFFFF
    for byte in data:
        crc = _calculate_crc32.table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    
    return crc ^ 0xFFFFFFFF

def test_zipper():
    """Test zipper functionality with current setup"""
    print("=== Testing Zipper Functionality ===")
    print()
    
    # Show compression info
    comp_info = get_compression_info()
    print(f"Compression available: {comp_info['available']}")
    print(f"Compression type: {comp_info['type']}")
    print(f"Library: {comp_info['library']}")
    print()
    
    # Create test files
    test_files = []
    test_data = [
        ("test1.txt", "Hello, World!\nThis is a test file for zipper.\n" * 10),
        ("test2.py", "# Python test file\nprint('Hello from zipper test!')\n" * 5),
        ("test3.dat", bytes(range(256)) * 4)  # Binary data
    ]
    
    print("Creating test files...")
    for fname, content in test_data:
        try:
            mode = "w" if isinstance(content, str) else "wb"
            with open(fname, mode) as f:
                f.write(content)
            test_files.append(fname)
            print(f"  Created: {fname}")
        except Exception as e:
            print(f"  Failed to create {fname}: {e}")
    
    if not test_files:
        print("❌ No test files created")
        return False
    
    print()
    
    # Test store mode
    print("Testing store mode...")
    try:
        zip_files("test_store.zip", test_files, mode="store")
        print("✅ Store mode ZIP creation successful")
    except Exception as e:
        print(f"❌ Store mode failed: {e}")
        return False
    
    # Test deflate mode if available
    if COMPRESSION_AVAILABLE:
        print("\nTesting deflate mode...")
        try:
            zip_files("test_deflate.zip", test_files, mode="deflate", compression_level=1)
            print("✅ Deflate mode ZIP creation successful")
        except Exception as e:
            print(f"❌ Deflate mode failed: {e}")
    else:
        print("\n⚠️ Skipping deflate mode (compression not available)")
    
    # Test extraction
    print("\nTesting extraction...")
    try:
        # Create extraction directory
        extract_dir = "test_extract"
        _makedirs(extract_dir)
        
        # Extract store mode zip
        unzip("test_store.zip", extract_dir)
        print("✅ Store mode extraction successful")
        
        # Verify extracted files
        for fname in test_files:
            extracted_path = os.path.join(extract_dir, fname)
            if os.path.exists(extracted_path):
                print(f"  ✅ Verified: {fname}")
            else:
                print(f"  ❌ Missing: {fname}")
                return False
        
        # Test deflate extraction if available
        if COMPRESSION_AVAILABLE and os.path.exists("test_deflate.zip"):
            extract_dir2 = "test_extract_deflate"
            _makedirs(extract_dir2)
            unzip("test_deflate.zip", extract_dir2)
            print("✅ Deflate mode extraction successful")
        
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return False
    
    # Cleanup
    print("\nCleaning up test files...")
    cleanup_files = test_files + ["test_store.zip", "test_deflate.zip"]
    cleanup_dirs = ["test_extract", "test_extract_deflate"]
    
    for fname in cleanup_files:
        try:
            os.remove(fname)
        except:
            pass
    
    for dirname in cleanup_dirs:
        try:
            # Remove files in directory first
            for fname in test_files:
                try:
                    os.remove(os.path.join(dirname, fname))
                except:
                    pass
            os.rmdir(dirname)
        except:
            pass
    
    print("✅ All tests completed successfully!")
    return True

def list_zip_contents(zip_path):
    """List contents of a ZIP file without extracting"""
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")
    
    print(f"Contents of {zip_path}:")
    print("-" * 60)
    print(f"{'Name':<30} {'Size':<10} {'Compressed':<10} {'Method'}")
    print("-" * 60)
    
    total_files = 0
    total_uncompressed = 0
    total_compressed = 0
    
    with open(zip_path, "rb") as zf:
        while True:
            sig = zf.read(4)
            if not sig:
                break
                
            if sig == b"PK\x03\x04":  # Local file header
                zf.read(18)  # Skip to CRC32
                crc32 = struct.unpack("<L", zf.read(4))[0]
                comp_size = struct.unpack("<L", zf.read(4))[0]
                uncomp_size = struct.unpack("<L", zf.read(4))[0]
                name_len = struct.unpack("<H", zf.read(2))[0]
                extra_len = struct.unpack("<H", zf.read(2))[0]
                
                fname = zf.read(name_len).decode('utf-8')
                zf.read(extra_len)  # Skip extra data
                zf.read(comp_size)  # Skip file data
                
                # Determine compression method from earlier read
                zf.seek(zf.tell() - comp_size - extra_len - name_len - 26)
                zf.read(8)  # Skip to compression method
                comp_method = struct.unpack("<H", zf.read(2))[0]
                zf.seek(zf.tell() + 16 + name_len + extra_len + comp_size)  # Skip to next entry
                
                method_name = "Store" if comp_method == ZIP_STORED else "Deflate" if comp_method == ZIP_DEFLATED else f"Unknown({comp_method})"
                
                print(f"{fname:<30} {uncomp_size:<10} {comp_size:<10} {method_name}")
                
                total_files += 1
                total_uncompressed += uncomp_size
                total_compressed += comp_size
                
            elif sig in [b"PK\x01\x02", b"PK\x05\x06"]:
                break
    
    print("-" * 60)
    print(f"Total files: {total_files}")
    print(f"Total uncompressed: {total_uncompressed} bytes")
    print(f"Total compressed: {total_compressed} bytes")
    if total_uncompressed > 0:
        ratio = total_compressed / total_uncompressed
        print(f"Compression ratio: {ratio:.1%}")

# Example usage and testing
if __name__ == "__main__":
    print("Zipper Library - Enhanced Version")
    print("=" * 40)
    
    # Show compression status
    comp_info = get_compression_info()
    print(f"Compression support: {comp_info}")
    print()
    
    # Run tests
    if test_zipper():
        print("\n🎉 Zipper library is ready for use!")
    else:
        print("\n❌ Zipper library tests failed")
    
    # Example usage (commented out)
    # zip_files("my_archive.zip", ["file1.txt", "file2.py"], mode="deflate")
    # unzip("my_archive.zip", "extracted/")
    # list_zip_contents("my_archive.zip")
