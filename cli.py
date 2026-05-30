"""Command-line transcode scan — same engine as the web UI, no browser needed.

Examples
  python cli.py --playlist "SET FINAL"
  python cli.py --folder "D:\\Contents"
  python cli.py --playlist "SET FINAL" --contents "D:\\Contents"
"""

from __future__ import annotations

import argparse

from backend.ffmpeg_tools import check_binaries
from backend.rekordbox_source import (
    find_usb_contents_roots,
    open_database,
    resolve_playlist,
)
from backend.scanner import analyze_file, iter_audio_files


def main() -> None:
    ap = argparse.ArgumentParser(description="Flag lossy audio re-encoded as a high bitrate.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--playlist", help="Rekordbox playlist name or id")
    group.add_argument("--folder", help="Folder to scan recursively")
    ap.add_argument("--contents", help="USB Contents root to map playlist tracks onto")
    args = ap.parse_args()

    check_binaries()

    if args.playlist:
        db = open_database()
        contents = args.contents or (find_usb_contents_roots() or [None])[0]
        tracks = resolve_playlist(db, args.playlist, contents)
        items = [(t.analyze_path, t.filename or t.title) for t in tracks]
    else:
        items = [(p, None) for p in iter_audio_files(args.folder)]

    print(f"{len(items)} tracks\n")
    print(f"{'VERDICT':<13}{'conf':>5} {'decl':>5} {'cutoff':>7} {'shelf':>6}  file")
    print("-" * 78)

    tally: dict[str, int] = {}
    for path, label in items:
        if not path:
            print(f"{'MISSING':<13}{'':>5} {'':>5} {'':>7} {'':>6}  {label}")
            tally["MISSING"] = tally.get("MISSING", 0) + 1
            continue
        rec = analyze_file(path)
        tally[rec["verdict"]] = tally.get(rec["verdict"], 0) + 1
        decl = rec["declaredKbps"] if rec["declaredKbps"] is not None else "-"
        shelf = "YES" if rec["shelfDetected"] else "no"
        print(f"{rec['verdict']:<13}{rec['confidence']:>5.2f} {str(decl):>5} "
              f"{rec['cutoffKhz']:>6.1f}k {shelf:>6}  {rec['name']}")

    print("\n" + "  ".join(f"{k}: {v}" for k, v in sorted(tally.items())))


if __name__ == "__main__":
    main()
