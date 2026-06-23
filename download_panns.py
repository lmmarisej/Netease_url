"""PANNs CNN14 checkpoint + labels concurrent downloader using Python threads."""
import os, sys, time, threading, requests

# panns_inference 默认路径: ~/panns_data/
PANNS_DIR = os.path.join(os.path.expanduser("~"), "panns_data")
URL = "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1"
LABELS_URL = "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv"
OUT = os.path.join(PANNS_DIR, "Cnn14_mAP=0.431.pth")
LABELS_OUT = os.path.join(PANNS_DIR, "class_labels_indices.csv")
THREADS = 8
CHUNK = 256 * 1024  # 256KB per read

os.makedirs(PANNS_DIR, exist_ok=True)

# Get content-length
r = requests.head(URL, timeout=60)
total = int(r.headers.get("content-length", 0))
if total == 0:
    print("ERROR: Cannot determine file size (server may not support HEAD)")
    sys.exit(1)

print(f"Downloading {total / 1024 / 1024:.0f} MB with {THREADS} threads...")

part_size = total // THREADS
results = [None] * THREADS
lock = threading.Lock()
downloaded = [0] * THREADS


def download_part(tid: int):
    start = tid * part_size
    end = start + part_size - 1 if tid < THREADS - 1 else total - 1
    headers = {"Range": f"bytes={start}-{end}"}
    data = bytearray()
    try:
        resp = requests.get(URL, headers=headers, stream=True, timeout=600)
        resp.raise_for_status()
        for chunk in resp.iter_content(CHUNK):
            if chunk:
                data.extend(chunk)
                downloaded[tid] += len(chunk)
    except Exception as e:
        print(f"\n  Thread {tid} failed: {e}")
        results[tid] = None
        return
    results[tid] = (start, data)


def progress():
    while any(t.is_alive() for t in threads):
        done = sum(downloaded)
        pct = done / total * 100
        mb = done / 1024 / 1024
        print(f"\r  {pct:.0f}%  {mb:.0f}/{total/1024/1024:.0f} MB", end="")
        time.sleep(1)
    done = sum(downloaded)
    print(f"\r  100%  {done/1024/1024:.0f}/{total/1024/1024:.0f} MB")


threads = [threading.Thread(target=download_part, args=(i,)) for i in range(THREADS)]
progress_thread = threading.Thread(target=progress)

for t in threads:
    t.start()
progress_thread.start()

for t in threads:
    t.join()
progress_thread.join()

# Reassemble
if any(r is None for r in results):
    print("ERROR: Some parts failed to download")
    sys.exit(1)

with open(OUT, "wb") as f:
    for start, data in sorted(results, key=lambda x: x[0]):
        f.seek(start)
        f.write(data)

size_mb = os.path.getsize(OUT) / 1024 / 1024
print(f"\nDone: {size_mb:.0f} MB saved to {OUT}")

# 下载 labels CSV
if not os.path.exists(LABELS_OUT):
    print(f"\nDownloading labels CSV...")
    r = requests.get(LABELS_URL, timeout=60)
    r.raise_for_status()
    with open(LABELS_OUT, "wb") as f:
        f.write(r.content)
    print(f"Labels saved to {LABELS_OUT}")
else:
    print(f"\nLabels already exist: {LABELS_OUT}")
