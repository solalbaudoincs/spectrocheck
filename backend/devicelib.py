"""Read the USB's own Device Library Plus database (``exportLibrary.db``).

The desktop ``master.db`` can be out of sync with what is actually on a DJ USB
(tracks added to a playlist on the stick / another machine never synced back).
The USB carries its own SQLCipher-encrypted library, ``exportLibrary.db``, whose
playlists are the real, current set that plays at the gig. Unlike the old
``export.pdb`` it is plain SQLite once decrypted, with the same fixed key for
every device (derived the same way pyrekordbox does).

Crucially, ``content.path`` here is already the on-USB path (``/Contents/...``),
so a playlist resolves to exact files with no filename/size guessing.
"""

from __future__ import annotations

import base64
import os
import zlib

from .rekordbox_source import PlaylistInfo, PlaylistTrack

try:
    from sqlcipher3 import dbapi2 as _sqlite  # type: ignore
except Exception:  # pragma: no cover - sqlcipher optional
    _sqlite = None

# Obfuscated Device Library Plus key (same constant pyrekordbox ships).
_BLOB = b"PN_1dH8$oLJY)16j_RvM6qphWw`476>;C1cWmI#se(PG`j}~xAjlufj?`#0i{;=glh(SkW)y0>n?YEiD`l%t("
_BLOB_KEY = b"657f48f84c437cc1"


def _key() -> str:
    data = base64.b85decode(_BLOB)
    xored = bytes(b ^ _BLOB_KEY[i % len(_BLOB_KEY)] for i, b in enumerate(data))
    return zlib.decompress(xored).decode("utf-8")


def export_library_path(contents_root: str | None) -> str | None:
    """Locate ``<drive>/PIONEER/rekordbox/exportLibrary.db`` for a USB Contents root."""
    if not contents_root:
        return None
    drive = os.path.splitdrive(contents_root)[0]  # e.g. "D:"
    if not drive:
        return None
    path = os.path.join(drive + os.sep, "PIONEER", "rekordbox", "exportLibrary.db")
    return path if os.path.isfile(path) else None


def _connect(db_path: str):
    con = _sqlite.connect(db_path)
    con.execute("PRAGMA key='%s'" % _key().replace("'", "''"))
    con.execute("SELECT count(*) FROM sqlite_master")  # force-decrypt / validate
    return con


def available(contents_root: str | None) -> bool:
    if _sqlite is None:
        return False
    path = export_library_path(contents_root)
    if not path:
        return False
    try:
        _connect(path).close()
        return True
    except Exception:
        return False


def list_playlists(contents_root: str) -> list[PlaylistInfo]:
    path = export_library_path(contents_root)
    if not path:
        return []
    con = _connect(path)
    try:
        rows = con.execute(
            "SELECT p.playlist_id, p.name, p.attribute, "
            "(SELECT count(*) FROM playlist_content pc WHERE pc.playlist_id = p.playlist_id) "
            "FROM playlist p ORDER BY p.sequenceNo"
        ).fetchall()
        return [PlaylistInfo(str(pid), name or "", bool(attr == 1), int(n or 0))
                for pid, name, attr, n in rows]
    finally:
        con.close()


def _find_playlist(con, name_or_id: str):
    wanted = (name_or_id or "").strip()
    rows = con.execute("SELECT playlist_id, name, attribute FROM playlist").fetchall()
    for pid, _name, attr in rows:  # exact id
        if str(pid) == wanted:
            return pid, attr
    low = wanted.lower()
    for pid, name, attr in rows:  # exact name
        if (name or "").lower() == low:
            return pid, attr
    tokens = low.split()
    for pid, name, attr in rows:  # token-contains (skip folders)
        if attr == 1:
            continue
        nm = (name or "").lower()
        if tokens and all(t in nm for t in tokens):
            return pid, attr
    return None, None


def resolve_playlist(contents_root: str, name_or_id: str) -> list[PlaylistTrack]:
    path = export_library_path(contents_root)
    if not path:
        raise KeyError("No exportLibrary.db found on the USB")
    con = _connect(path)
    try:
        pid, attr = _find_playlist(con, name_or_id)
        if pid is None:
            raise KeyError(f"Playlist {name_or_id!r} not found on the USB")
        if attr == 1:
            raise KeyError(f"{name_or_id!r} is a folder, not a playlist")

        drive = os.path.splitdrive(contents_root)[0]  # "D:"
        query = (
            "SELECT c.fileName, c.path, c.title, c.fileSize, c.bitrate, ar.name "
            "FROM playlist_content pc "
            "JOIN content c ON c.content_id = pc.content_id "
            "LEFT JOIN artist ar ON ar.artist_id = c.artist_id_artist "
            "WHERE pc.playlist_id = ? ORDER BY pc.sequenceNo"
        )
        tracks: list[PlaylistTrack] = []
        for filename, dev_path, title, size, bitrate, artist in con.execute(query, (pid,)):
            full = (drive + dev_path.replace("/", os.sep)) if dev_path else ""
            usb = full if full and os.path.isfile(full) else None
            try:
                kbps = int(bitrate) if bitrate else None
            except (TypeError, ValueError):
                kbps = None
            tracks.append(PlaylistTrack(
                title=title or "", artist=artist or "",
                original_path=full, usb_path=usb, analyze_path=usb,
                filename=filename or "", size=int(size or 0),
                declared_kbps=kbps, match="usb-db" if usb else "missing",
            ))
        return tracks
    finally:
        con.close()


if __name__ == "__main__":  # quick manual check
    root = r"D:\Contents"
    print("available:", available(root), export_library_path(root))
    ts = resolve_playlist(root, "SET FINAL")
    print(f"{len(ts)} tracks ({sum(1 for t in ts if t.usb_path)} resolved on USB)")
    for t in ts[:5]:
        print("  ", t.match, "|", t.artist, "-", t.title, "|", t.usb_path)
    print("  ...")
    for t in ts:
        if "lush" in (t.filename or "").lower():
            print("  LUSH:", t.usb_path, "exists=", bool(t.usb_path))
