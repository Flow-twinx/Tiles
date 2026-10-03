import os
import pathlib

import yt_dlp

DOWNLOAD_DIR = pathlib.Path.home() / ".flow/downloads/"
BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "noplaylist": True,
    "format": "bestaudio/best",
    "skip_download": True,
    "socket_timeout": 10,
    "retries": 2,
    "extractor_retries": 2,
    "js_runtimes": {"node": {}},
    "extractor_args": {"youtube": {"player_client": ["android"]}},
}

files = os.listdir(DOWNLOAD_DIR)
print(files)

for file in files:
    if ".opus" in file:
        print(file)
        with yt_dlp.YoutubeDL(BASE_OPTS) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={file}", download=False
            )
            title = info.get("title")
            print(f"{file} : {title}")
            with open("song.txt", "a") as f:
                f.writelines(title)
                f.writelines("\n")
    else:
        pass
