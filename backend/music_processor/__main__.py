"""python -m music_processor 入口。"""
from . import MUSIC_FOLDER, DB_PATH, USERNAME, scan_and_process

if __name__ == "__main__":
    scan_and_process(MUSIC_FOLDER, DB_PATH, USERNAME)
