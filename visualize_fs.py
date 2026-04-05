import os, struct, json, webbrowser

DISK_IMAGE = "virtual_disk.img"
HTML_FILE = "visualization.html"

BLOCK_SIZE = 256
MAX_FILES = 32
DIR_ENTRY_SIZE = 64

SUPERBLOCK_FORMAT = "<I I I"
DIR_ENTRY_FORMAT = "<32s I I I B"


def parse_disk():
    if not os.path.exists(DISK_IMAGE):
        return None

    size = os.path.getsize(DISK_IMAGE)
    num_blocks = size // BLOCK_SIZE

    with open(DISK_IMAGE, "rb") as f:
        f.read(struct.calcsize(SUPERBLOCK_FORMAT))

        bitmap_bytes = (num_blocks + 7) // 8
        bitmap = list(f.read(bitmap_bytes))

        dir_offset = struct.calcsize(SUPERBLOCK_FORMAT) + bitmap_bytes
        data_offset = dir_offset + MAX_FILES * DIR_ENTRY_SIZE

        f.seek(dir_offset)
        files = []

        for _ in range(MAX_FILES):
            raw = f.read(DIR_ENTRY_SIZE)
            if not raw.strip():
                continue

            extra = DIR_ENTRY_SIZE - struct.calcsize(DIR_ENTRY_FORMAT)
            u = struct.unpack(DIR_ENTRY_FORMAT + f"{extra}s", raw)

            if not u[4]:
                continue

            name = u[0].split(b"\x00")[0].decode()

            files.append({
                "name": name,
                "size": u[1],
                "first_block": u[2],
                "blocks": u[3]
            })

    return {
        "blocks": num_blocks,
        "bitmap": bitmap,
        "files": files
    }


def main():
    data = parse_disk()

    with open(HTML_FILE, "w") as f:
        f.write(f"<h2>File System Data</h2><pre>{json.dumps(data, indent=2)}</pre>")

    webbrowser.open(HTML_FILE)


if __name__ == "__main__":
    main()