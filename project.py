#!/usr/bin/env python3

import os
import struct
import subprocess

DISK_IMAGE = "virtual_disk.img"
DISK_SIZE = 1024 * 64
BLOCK_SIZE = 256
NUM_BLOCKS = DISK_SIZE // BLOCK_SIZE
MAX_FILES = 32
DIR_ENTRY_SIZE = 64

SUPERBLOCK_FORMAT = "<I I I"
MAGIC = 0xF5F5F5F5

SUPERBLOCK_OFFSET = 0
BITMAP_OFFSET = SUPERBLOCK_OFFSET + struct.calcsize(SUPERBLOCK_FORMAT)
BITMAP_BYTES = (NUM_BLOCKS + 7) // 8
DIR_OFFSET = BITMAP_OFFSET + BITMAP_BYTES
DIR_BYTES = MAX_FILES * DIR_ENTRY_SIZE
DATA_OFFSET = DIR_OFFSET + DIR_BYTES

DIR_ENTRY_FORMAT = "<32s I I I B"
DIR_ENTRY_MIN_SIZE = struct.calcsize(DIR_ENTRY_FORMAT)


def reset_disk():
    if os.path.exists(DISK_IMAGE):
        os.remove(DISK_IMAGE)
        print("[FS] Old disk removed")


def ensure_disk():
    if not os.path.exists(DISK_IMAGE):
        with open(DISK_IMAGE, "wb") as f:
            f.write(b"\x00" * DISK_SIZE)


class SimpleFS:
    def __init__(self):
        ensure_disk()
        self.f = open(DISK_IMAGE, "r+b")

    def close(self):
        self.f.close()

    def format(self):
        self.f.seek(SUPERBLOCK_OFFSET)
        self.f.write(struct.pack(SUPERBLOCK_FORMAT, MAGIC, BLOCK_SIZE, NUM_BLOCKS))

        bitmap = bytearray(BITMAP_BYTES)

        reserved = (DATA_OFFSET + BLOCK_SIZE - 1) // BLOCK_SIZE
        for b in range(reserved):
            bitmap[b // 8] |= (1 << (b % 8))

        self.f.seek(BITMAP_OFFSET)
        self.f.write(bitmap)

        self.f.seek(DIR_OFFSET)
        self.f.write(b"\x00" * DIR_BYTES)

        self.f.flush()
        print("[FS] Disk formatted")

    def read_bitmap(self):
        self.f.seek(BITMAP_OFFSET)
        return bytearray(self.f.read(BITMAP_BYTES))

    def write_bitmap(self, bitmap):
        self.f.seek(BITMAP_OFFSET)
        self.f.write(bitmap)
        self.f.flush()

    def read_dir(self):
        self.f.seek(DIR_OFFSET)
        entries = []

        for i in range(MAX_FILES):
            raw = self.f.read(DIR_ENTRY_SIZE)
            if not raw.strip():
                continue

            extra = DIR_ENTRY_SIZE - DIR_ENTRY_MIN_SIZE
            u = struct.unpack(DIR_ENTRY_FORMAT + f"{extra}s", raw)

            entries.append({
                "name": u[0].split(b"\x00")[0].decode(),
                "size": u[1],
                "first_block": u[2],
                "blocks": u[3],
                "in_use": bool(u[4]),
                "index": i
            })

        return entries

    def find_free_blocks(self, count):
        bitmap = self.read_bitmap()
        free = []

        for i in range(NUM_BLOCKS):
            if (bitmap[i // 8] >> (i % 8)) & 1 == 0:
                free.append(i)
                if len(free) == count:
                    return free

        return None

    def create_file(self, name, data):
        blocks = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE
        free = self.find_free_blocks(blocks)

        if not free:
            print("[FS] Not enough space")
            return

        bitmap = self.read_bitmap()
        for b in free:
            bitmap[b // 8] |= (1 << (b % 8))

        self.write_bitmap(bitmap)

        for i, blk in enumerate(free):
            self.f.seek(DATA_OFFSET + blk * BLOCK_SIZE)
            self.f.write(
                data[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE].ljust(BLOCK_SIZE, b"\x00")
            )

        slot = len([e for e in self.read_dir() if e["in_use"]])

        name_bytes = name.encode()[:32].ljust(32, b"\x00")
        entry = struct.pack(DIR_ENTRY_FORMAT, name_bytes, len(data), free[0], blocks, 1)
        entry += b"\x00" * (DIR_ENTRY_SIZE - len(entry))

        self.f.seek(DIR_OFFSET + slot * DIR_ENTRY_SIZE)
        self.f.write(entry)
        self.f.flush()

        print(f"[FS] File '{name}' created")

    def delete_file(self, filename):
        entries = self.read_dir()
        bitmap = self.read_bitmap()

        for e in entries:
            if e["in_use"] and e["name"] == filename:
                for i in range(e["blocks"]):
                    blk = e["first_block"] + i
                    bitmap[blk // 8] &= ~(1 << (blk % 8))

                self.write_bitmap(bitmap)

                self.f.seek(DIR_OFFSET + e["index"] * DIR_ENTRY_SIZE)
                self.f.write(b"\x00" * DIR_ENTRY_SIZE)
                self.f.flush()

                print(f"[FS] File '{filename}' deleted")
                return

        print("[FS] File not found")


def menu():
    fs = SimpleFS()

    while True:
        print("\n=== FILE SYSTEM MENU ===")
        print("0. Reset & Format Disk")
        print("1. Create File")
        print("2. Delete File")
        print("3. List Files")
        print("4. Exit")

        ch = input("Choice: ")

        if ch == "0":
            fs.close()
            reset_disk()
            fs = SimpleFS()
            fs.format()

        elif ch == "1":
            name = input("File name: ")
            content = input("File content: ").encode()
            fs.create_file(name, content)

        elif ch == "2":
            name = input("File name to delete: ")
            fs.delete_file(name)

        elif ch == "3":
            for e in fs.read_dir():
                if e["in_use"]:
                    print(e)

        elif ch == "4":
            fs.close()
            break


if __name__ == "__main__":
    menu()