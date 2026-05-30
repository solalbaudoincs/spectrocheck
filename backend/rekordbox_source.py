"""Resolve a Rekordbox playlist to actual audio files on disk.

The desktop ``master.db`` is the authoritative record of what is in a playlist,
but its paths point at the *original* files. When the tracks have been exported
to a DJ USB stick we would rather analyse the copies that actually play at the
gig (``<USB>/Contents/...``). So for each track we map the library entry to its
USB copy by filename + exact byte size, falling back to size-only, then to the
original path.
"""

from __future__ import annotations

import difflib
import os
from dataclasses import asdict, dataclass


@dataclass
class PlaylistInfo:
    id: str
    name: str
    is_folder: bool
    count: int


@dataclass
class PlaylistTrack:
    title: str
    artist: str
    original_path: str
    usb_path: str | None
    analyze_path: str | None
    filename: str
    size: int
    declared_kbps: int | None
    match: str  # 'name+size' | 'size' | 'original' | 'missing'

    def to_dict(self) -> dict:
        return asdict(self)


def find_usb_contents_roots() -> list[str]:
    """Detect exported-USB ``Contents`` folders (a drive with both PIONEER and Contents)."""
    roots: list[str] = []
    if os.name == "nt":
        import string

        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            contents = os.path.join(drive, "Contents")
            pioneer = os.path.join(drive, "PIONEER")
            if os.path.isdir(contents) and os.path.isdir(pioneer):
                roots.append(contents)
    else:
        for base in ("/Volumes", "/media", "/mnt", "/run/media"):
            if not os.path.isdir(base):
                continue
            for entry in os.listdir(base):
                mount = os.path.join(base, entry)
                contents = os.path.join(mount, "Contents")
                if os.path.isdir(contents) and os.path.isdir(os.path.join(mount, "PIONEER")):
                    roots.append(contents)
    return roots


def open_database(db_dir: str | None = None, key: str | None = None):
    """Open the Rekordbox 6/7 master database (auto key unless one is given)."""
    from pyrekordbox import Rekordbox6Database

    if db_dir:
        return Rekordbox6Database(db_dir=db_dir, key=key or "")
    if key:
        return Rekordbox6Database(key=key)
    return Rekordbox6Database()


def list_playlists(db) -> list[PlaylistInfo]:
    out: list[PlaylistInfo] = []
    for p in db.get_playlist():
        is_folder = bool(getattr(p, "Attribute", 0) == 1)
        try:
            count = 0 if is_folder else len(p.Songs)
        except Exception:
            count = 0
        out.append(PlaylistInfo(str(getattr(p, "ID", "")),
                                getattr(p, "Name", "") or "", is_folder, count))
    return out


def find_playlist(db, name_or_id: str):
    """Find a playlist by exact id, then exact name, then case-insensitive contains."""
    wanted = (name_or_id or "").strip()
    playlists = list(db.get_playlist())
    for p in playlists:  # exact id
        if str(getattr(p, "ID", "")) == wanted:
            return p
    low = wanted.lower()
    for p in playlists:  # exact name (case-insensitive)
        if (getattr(p, "Name", "") or "").lower() == low:
            return p
    # token-contains: every whitespace token must appear in the name (skip folders)
    tokens = low.split()
    for p in playlists:
        if getattr(p, "Attribute", 0) == 1:
            continue
        nm = (getattr(p, "Name", "") or "").lower()
        if tokens and all(t in nm for t in tokens):
            return p
    return None


def build_usb_index(contents_root: str):
    """Index every file under ``contents_root`` by lowercase basename and by size."""
    by_name: dict[str, list[str]] = {}
    by_size: dict[int, list[str]] = {}
    for dirpath, _dirs, files in os.walk(contents_root):
        for name in files:
            fp = os.path.join(dirpath, name)
            try:
                sz = os.path.getsize(fp)
            except OSError:
                continue
            by_name.setdefault(name.lower(), []).append(fp)
            by_size.setdefault(sz, []).append(fp)
    return by_name, by_size


def _match_usb(index, filename: str, size: int) -> tuple[str | None, str]:
    by_name, by_size = index
    base = (filename or "").lower()
    name_hits = by_name.get(base, [])
    size_hits = by_size.get(size, []) if size else []

    both = [p for p in name_hits if p in set(size_hits)]
    if both:
        return both[0], "name+size"

    if size_hits:
        if len(size_hits) == 1:
            return size_hits[0], "size"
        # Several files share this exact byte size: only accept the closest
        # filename if it actually resembles the target, else treat as ambiguous
        # rather than silently analysing an unrelated track.
        best = max(size_hits, key=lambda p: difflib.SequenceMatcher(
            None, os.path.basename(p).lower(), base).ratio())
        ratio = difflib.SequenceMatcher(None, os.path.basename(best).lower(), base).ratio()
        return (best, "size") if ratio >= 0.6 else (None, "ambiguous")

    if len(name_hits) == 1:
        return name_hits[0], "name"
    if name_hits:
        # Same basename in several folders and no size to disambiguate -> ambiguous.
        return None, "ambiguous"
    return None, "missing"


def resolve_playlist(db, name_or_id: str, contents_root: str | None = None) -> list[PlaylistTrack]:
    """Return the playlist's tracks, each resolved to an analysable path."""
    pl = find_playlist(db, name_or_id)
    if pl is None:
        raise KeyError(f"Playlist {name_or_id!r} not found")
    if getattr(pl, "Attribute", 0) == 1:
        raise KeyError(f"{name_or_id!r} is a folder, not a playlist")

    songs = sorted(pl.Songs, key=lambda s: (getattr(s, "TrackNo", 0) or 0))
    index = build_usb_index(contents_root) if contents_root and os.path.isdir(contents_root) else None

    tracks: list[PlaylistTrack] = []
    for s in songs:
        c = s.Content
        filename = getattr(c, "FileNameL", "") or getattr(c, "FileNameS", "") or ""
        size = int(getattr(c, "FileSize", 0) or 0)
        original = (getattr(c, "FolderPath", "") or "").replace("/", os.sep)
        title = getattr(c, "Title", "") or ""
        artist = getattr(getattr(c, "Artist", None), "Name", "") or ""
        kbps = getattr(c, "BitRate", None) or None

        usb_path, match = (None, "original")
        if index is not None:
            usb_path, match = _match_usb(index, filename, size)

        if usb_path:
            analyze_path = usb_path
        elif original and os.path.exists(original):
            analyze_path, match = original, "original"
        else:
            analyze_path, match = None, "missing"

        tracks.append(PlaylistTrack(title, artist, original, usb_path, analyze_path,
                                    filename, size, kbps, match))
    return tracks
