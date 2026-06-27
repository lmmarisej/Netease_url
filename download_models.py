"""通用多线程分片模型下载器 — PANNs + Demucs。

用法:
    python3 download_models.py              # 下载全部模型
    python3 download_models.py --panns       # 仅 PANNs
    python3 download_models.py --demucs      # 仅 Demucs
    python3 download_models.py --all         # 全部
"""
import os, sys, time, threading, argparse
import requests

THREADS = 8
CHUNK = 256 * 1024  # 256KB

# ── PANNs ──────────────────────────────────────────────────────
PANNS_DIR = os.path.join(os.path.expanduser("~"), "panns_data")
PANNS_URL = "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1"
PANNS_OUT = os.path.join(PANNS_DIR, "Cnn14_mAP=0.431.pth")
PANNS_LABELS_URL = "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv"
PANNS_LABELS_OUT = os.path.join(PANNS_DIR, "class_labels_indices.csv")

# ── Demucs (htdemucs) ──────────────────────────────────────────
DEMUCS_DIR = os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "checkpoints")
DEMUCS_URL = "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th"
DEMUCS_OUT = os.path.join(DEMUCS_DIR, "955717e8-8726e21a.th")


def download_file(url: str, dest: str, label: str = "", threads: int = THREADS) -> bool:
    """多线程分片下载单个文件，支持断点语义（Range 请求）。

    Returns:
        True 表示成功，False 表示失败。
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    # 先获取文件大小
    try:
        r = requests.head(url, timeout=60, allow_redirects=True)
        total = int(r.headers.get("content-length", 0))
    except Exception as e:
        print(f"[{label}] HEAD 请求失败: {e}")
        return False

    if total == 0:
        print(f"[{label}] 无法获取文件大小，回退单线程下载...")
        return _download_single(url, dest, label)

    size_mb = total / 1024 / 1024
    print(f"[{label}] 下载 {size_mb:.0f} MB ({threads} 线程分片)...")

    part_size = total // threads
    results: list = [None] * threads
    downloaded = [0] * threads

    def _download_part(tid: int):
        start = tid * part_size
        end = start + part_size - 1 if tid < threads - 1 else total - 1
        headers = {"Range": f"bytes={start}-{end}"}
        data = bytearray()
        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=600)
            resp.raise_for_status()
            for chunk in resp.iter_content(CHUNK):
                if chunk:
                    data.extend(chunk)
                    downloaded[tid] += len(chunk)
        except Exception as e:
            print(f"\n  [{label}] 线程 {tid} 失败: {e}", flush=True)
            results[tid] = None
            return
        results[tid] = (start, data)

    def _progress():
        while any(t.is_alive() for t in thread_list):
            done = sum(downloaded)
            pct = done / total * 100
            mb = done / 1024 / 1024
            print(f"\r  [{label}] {pct:.0f}%  {mb:.0f}/{total / 1024 / 1024:.0f} MB", end="", flush=True)
            time.sleep(1)
        done = sum(downloaded)
        print(f"\r  [{label}] 100%  {done / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB", flush=True)

    thread_list = [threading.Thread(target=_download_part, args=(i,)) for i in range(threads)]
    progress_thread = threading.Thread(target=_progress)

    for t in thread_list:
        t.start()
    progress_thread.start()

    for t in thread_list:
        t.join()
    progress_thread.join()

    if any(r is None for r in results):
        print(f"\n[{label}] 部分分片下载失败")
        return False

    with open(dest, "wb") as f:
        for start, data in sorted(results, key=lambda x: x[0]):
            f.seek(start)
            f.write(data)

    size_mb = os.path.getsize(dest) / 1024 / 1024
    print(f"\n[{label}] 完成: {size_mb:.0f} MB → {dest}")
    return True


def _download_single(url: str, dest: str, label: str) -> bool:
    """单线程回退下载。"""
    try:
        r = requests.get(url, stream=True, timeout=600)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(CHUNK):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        mb = downloaded / 1024 / 1024
                        print(f"\r  [{label}] {pct:.0f}%  {mb:.0f}/{total / 1024 / 1024:.0f} MB", end="", flush=True)
        print(f"\n[{label}] 完成: {os.path.getsize(dest) / 1024 / 1024:.0f} MB → {dest}")
        return True
    except Exception as e:
        print(f"\n[{label}] 下载失败: {e}")
        return False


def download_panns() -> bool:
    """下载 PANNs CNN14 模型 + labels CSV。"""
    ok = True
    if not os.path.exists(PANNS_OUT) or os.path.getsize(PANNS_OUT) < 300_000_000:
        ok = download_file(PANNS_URL, PANNS_OUT, "PANNs CNN14")
    else:
        print(f"[PANNs] 模型已存在 ({os.path.getsize(PANNS_OUT) / 1024 / 1024:.0f} MB)，跳过")

    if not os.path.exists(PANNS_LABELS_OUT):
        print(f"[PANNs] 下载 labels CSV...")
        try:
            r = requests.get(PANNS_LABELS_URL, timeout=60)
            r.raise_for_status()
            with open(PANNS_LABELS_OUT, "wb") as f:
                f.write(r.content)
            print(f"[PANNs] labels 已保存: {PANNS_LABELS_OUT}")
        except Exception as e:
            print(f"[PANNs] labels 下载失败: {e}")
            ok = False
    else:
        print(f"[PANNs] labels 已存在，跳过")
    return ok


def download_demucs() -> bool:
    """下载 Demucs htdemucs 模型权重。"""
    if not os.path.exists(DEMUCS_OUT) or os.path.getsize(DEMUCS_OUT) < 100_000_000:
        return download_file(DEMUCS_URL, DEMUCS_OUT, "Demucs htdemucs")
    else:
        print(f"[Demucs] 模型已存在 ({os.path.getsize(DEMUCS_OUT) / 1024 / 1024:.0f} MB)，跳过")
        return True


def main():
    parser = argparse.ArgumentParser(description="多线程分片下载 AI 模型")
    parser.add_argument("--panns", action="store_true", help="仅下载 PANNs")
    parser.add_argument("--demucs", action="store_true", help="仅下载 Demucs")
    parser.add_argument("--all", action="store_true", help="下载全部（默认）")
    args = parser.parse_args()

    # 默认行为：全部下载
    do_panns = args.panns or args.all or (not args.panns and not args.demucs and not args.all)
    do_demucs = args.demucs or args.all or (not args.panns and not args.demucs and not args.all)

    print("=" * 56)
    print("  模型下载器 — 多线程分片并行下载")
    print("=" * 56)

    ok = True
    if do_panns:
        print("\n▶ PANNs (音频标签识别)")
        if not download_panns():
            ok = False

    if do_demucs:
        print("\n▶ Demucs htdemucs (人声/伴奏分离)")
        if not download_demucs():
            ok = False

    print("\n" + "=" * 56)
    if ok:
        print("  全部模型就绪 ✓")
    else:
        print("  部分模型下载失败，服务仍可启动（对应功能将跳过）")
    print("=" * 56)
    sys.exit(0 if ok else 0)  # 不阻塞启动


if __name__ == "__main__":
    main()
