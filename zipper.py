import struct
import os

# Try to import standard zlib first, fall back to our implementation
try:
    import zlib
except ImportError:
    try:
        import zlib_compat as zlib
        print("Using zlib_compat for compression")
    except ImportError:
        zlib = None  # No compression available

# --- ZIP constants ---
ZIP_STORED = 0  # No compression
ZIP_DEFLATED = 8  # Deflate compression

def zip_files(zip_path, file_list, mode="store"):
    """
    Create a ZIP archive from file_list.
    mode: "store" (no compression) or "deflate" (light compression, if zlib available)
    """
    if mode not in ("store", "deflate"):
        raise ValueError("mode must be 'store' or 'deflate'")
    if mode == "deflate" and not zlib:
        raise RuntimeError("zlib module not available for deflate mode")

    central_dir = []
    offset = 0

    with open(zip_path, "wb") as zf:
        for fname in file_list:
            with open(fname, "rb") as f:
                data = f.read()
            
            if mode == "deflate":
                # Use raw deflate (no zlib header), level 1 for memory efficiency
                try:
                    compressor = zlib.compressobj(level=1, wbits=-15)
                    compressed = compressor.compress(data)
                    compressed += compressor.flush()
                    data_to_write = compressed
                    compress_type = ZIP_DEFLATED
                    comp_size = len(compressed)
                except Exception as e:
                    print(f"Compression failed, falling back to store mode: {e}")
                    data_to_write = data
                    compress_type = ZIP_STORED
                    comp_size = len(data)
            else:
                data_to_write = data
                compress_type = ZIP_STORED
                comp_size = len(data)
            
            # Calculate CRC32 (simple implementation)
            crc32 = _calculate_crc32(data)
            
            # Local file header
            local_header = struct.pack(
                "<4s2B4HL2L2H",
                b"PK\x03\x04",  # signature
                20, 0,          # version, flags
                compress_type,  # compression
                0, 0,           # mod time/date
                crc32, 0,       # crc32 (low, high)
                comp_size, len(data),  # compressed, uncompressed sizes
                len(fname), 0   # name len, extra len
            )
            zf.write(local_header)
            zf.write(fname.encode())
            zf.write(data_to_write)
            
            # Central directory entry
            central_dir.append((
                fname, offset, comp_size, len(data), compress_type, crc32
            ))
            offset += len(local_header) + len(fname) + comp_size
        
        # Write central directory
        cd_start = offset
        for fname, file_offset, comp_size, uncomp_size, compress_type, crc32 in central_dir:
            cd_header = struct.pack(
                "<4s4B4HL3L5H2L",
                b"PK\x01\x02",  # signature
                20, 20, 0, 0,   # version, version needed, flags, compression
                0, 0,           # mod time/date
                crc32, 0,       # crc32
                comp_size, uncomp_size,  # sizes
                len(fname), 0, 0, 0, 0,  # name, extra, comment, disk, attr
                0, file_offset
            )
            zf.write(cd_header)
            zf.write(fname.encode())
            offset += len(cd_header) + len(fname)
        
        # End of central directory
        eocd = struct.pack(
            "<4s4H2LH",
            b"PK\x05\x06",
            0, 0, len(central_dir), len(central_dir),
            offset - cd_start, cd_start, 0
        )
        zf.write(eocd)
    print(f"Created zip: {zip_path}")

def unzip(zip_path, out_dir="."):
    """Extract all files from a ZIP archive (store or deflate mode)."""
    with open(zip_path, "rb") as zf:
        while True:
            sig = zf.read(4)
            if sig == b"PK\x03\x04":
                zf.read(2)  # version
                zf.read(2)  # flags
                comp = struct.unpack("<H", zf.read(2))[0]
                zf.read(2)  # mod time
                zf.read(2)  # mod date
                crc32_stored = struct.unpack("<L", zf.read(4))[0]
                comp_size = struct.unpack("<L", zf.read(4))[0]
                uncomp_size = struct.unpack("<L", zf.read(4))[0]
                name_len = struct.unpack("<H", zf.read(2))[0]
                extra_len = struct.unpack("<H", zf.read(2))[0]
                fname = zf.read(name_len).decode()
                zf.read(extra_len)
                data = zf.read(comp_size)
                
                if comp == ZIP_STORED:
                    out_data = data
                elif comp == ZIP_DEFLATED:
                    if not zlib:
                        raise RuntimeError("zlib module not available for deflate decompression")
                    try:
                        # Use raw inflate (no zlib header)
                        decompressor = zlib.decompressobj(wbits=-15)
                        out_data = decompressor.decompress(data)
                    except Exception as e:
                        raise RuntimeError(f"Decompression failed: {e}")
                else:
                    raise NotImplementedError(f"Compression type {comp} not supported")
                
                # Verify CRC32 if available
                if crc32_stored != 0:
                    calculated_crc32 = _calculate_crc32(out_data)
                    if calculated_crc32 != crc32_stored:
                        print(f"Warning: CRC32 mismatch for {fname}")
                
                # Create output directory if needed
                out_path = os.path.join(out_dir, fname)
                out_dir_path = os.path.dirname(out_path)
                if out_dir_path and out_dir_path != ".":
                    _makedirs(out_dir_path)
                
                with open(out_path, "wb") as out:
                    out.write(out_data)
                    
            elif sig == b"PK\x01\x02" or sig == b"PK\x05\x06" or not sig:
                break
            else:
                break
    print(f"Extracted zip: {zip_path}")

def _makedirs(path):
    """Create directories recursively (simple implementation)"""
    try:
        os.makedirs(path)
    except OSError:
        pass  # Directory might already exist

def _calculate_crc32(data):
    """Simple CRC32 calculation for ZIP files"""
    # CRC32 polynomial (IEEE 802.3)
    crc_table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
        crc_table.append(crc)
    
    crc = 0xFFFFFFFF
    for byte in data:
        crc = crc_table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    
    return crc ^ 0xFFFFFFFF

# Test function to verify zlib compatibility
def test_compression():
    """Test compression functionality"""
    test_data = b"Hello, World! This is a test of the compression system. " * 10
    
    print("Testing compression...")
    
    if zlib:
        try:
            # Test compression
            compressed = zlib.compress(test_data)
            print(f"Original size: {len(test_data)}")
            print(f"Compressed size: {len(compressed)}")
            print(f"Compression ratio: {len(compressed)/len(test_data):.2%}")
            
            # Test decompression
            decompressed = zlib.decompress(compressed)
            
            if decompressed == test_data:
                print("✅ Compression test passed!")
                return True
            else:
                print("❌ Compression test failed - data mismatch")
                return False
                
        except Exception as e:
            print(f"❌ Compression test failed: {e}")
            return False
    else:
        print("⚠️ No compression library available")
        return False

# Example usage:
if __name__ == "__main__":
    # Test compression
    test_compression()
    
    # To create a zip:
    # zip_files("test.zip", ["boot.py", "code.py"], mode="deflate")
    # To extract:
    # unzip("test.zip", ".")
    pass
