import struct
import os

# --- ZIP constants ---
ZIP_STORED = 0  # No compression

def zip_files(zip_path, file_list):
    """Create a ZIP archive (store mode, no compression) from file_list."""
    central_dir = []
    offset = 0

    with open(zip_path, "wb") as zf:
        for fname in file_list:
            with open(fname, "rb") as f:
                data = f.read()
            # Local file header
            local_header = struct.pack(
                "<4s2B4HL2L2H",
                b"PK\x03\x04",  # signature
                20, 0,          # version, flags
                ZIP_STORED,     # compression
                0, 0,           # mod time/date
                0, 0,           # crc32 (set to 0 for simplicity)
                len(data), len(data),  # sizes
                len(fname), 0   # name len, extra len
            )
            zf.write(local_header)
            zf.write(fname.encode())
            zf.write(data)
            # Central directory entry
            central_dir.append((
                fname, offset, len(data)
            ))
            offset += len(local_header) + len(fname) + len(data)
        # Write central directory
        cd_start = offset
        for fname, file_offset, file_size in central_dir:
            cd_header = struct.pack(
                "<4s4B4HL3L5H2L",
                b"PK\x01\x02",  # signature
                20, 20, 0, 0,   # version, version needed, flags, compression
                0, 0,           # mod time/date
                0, 0,           # crc32, crc32
                file_size, file_size,  # sizes
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
    """Extract all files from a ZIP archive (store mode only)."""
    with open(zip_path, "rb") as zf:
        while True:
            sig = zf.read(4)
            if sig == b"PK\x03\x04":
                zf.read(2)  # version
                zf.read(2)  # flags
                comp = struct.unpack("<H", zf.read(2))[0]
                zf.read(2)  # mod time
                zf.read(2)  # mod date
                zf.read(4)  # crc32
                size = struct.unpack("<L", zf.read(4))[0]
                zf.read(4)  # uncompressed size
                name_len = struct.unpack("<H", zf.read(2))[0]
                extra_len = struct.unpack("<H", zf.read(2))[0]
                fname = zf.read(name_len).decode()
                zf.read(extra_len)
                if comp != ZIP_STORED:
                    raise NotImplementedError("Only store mode supported")
                data = zf.read(size)
                out_path = os.path.join(out_dir, fname)
                with open(out_path, "wb") as out:
                    out.write(data)
            elif sig == b"PK\x01\x02" or sig == b"PK\x05\x06" or not sig:
                break
            else:
                break
    print(f"Extracted zip: {zip_path}")

# Example usage:
if __name__ == "__main__":
    # To create a zip:
    # zip_files("test.zip", ["boot.py", "code.py"])
    # To extract:
    # unzip("test.zip", ".")
    pass