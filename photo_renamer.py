#!/usr/bin/env python3
"""
Photo Renaming CLI Tool
Renames photos using EXIF date, sequential numbers, and custom prefix/suffix.
"""

import os
import sys
import argparse
import struct
import re
from datetime import datetime
from pathlib import Path

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.heic', '.webp', '.bmp', '.gif', '.raw', '.cr2', '.nef', '.arw', '.dng'}


def read_exif_date(filepath: Path) -> datetime | None:
    """Extract DateTimeOriginal from JPEG EXIF data without external dependencies."""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()

        # Only attempt EXIF parsing on JPEG files
        if not data.startswith(b'\xff\xd8'):
            return None

        i = 2
        while i < len(data) - 1:
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if marker == 0xE1:  # APP1 - EXIF
                length = struct.unpack('>H', data[i + 2:i + 4])[0]
                segment = data[i + 4:i + 2 + length]
                if segment[:6] == b'Exif\x00\x00':
                    return _parse_exif_segment(segment[6:])
            if marker in (0xD8, 0xD9):
                break
            if i + 3 >= len(data):
                break
            length = struct.unpack('>H', data[i + 2:i + 4])[0]
            i += 2 + length

    except (OSError, struct.error):
        pass
    return None


def _parse_exif_segment(exif: bytes) -> datetime | None:
    """Parse EXIF IFD to find DateTimeOriginal (tag 0x9003) or DateTime (tag 0x0132)."""
    try:
        if exif[:2] == b'II':
            endian = '<'
        elif exif[:2] == b'MM':
            endian = '>'
        else:
            return None

        ifd_offset = struct.unpack(endian + 'I', exif[4:8])[0]
        date = _read_ifd_date(exif, ifd_offset, endian, target_tags={0x9003, 0x0132, 0x9004})
        return date
    except (struct.error, IndexError):
        return None


def _read_ifd_date(exif: bytes, offset: int, endian: str, target_tags: set, depth: int = 0) -> datetime | None:
    if depth > 3 or offset + 2 > len(exif):
        return None
    try:
        count = struct.unpack(endian + 'H', exif[offset:offset + 2])[0]
    except struct.error:
        return None

    best = None
    sub_ifd_offset = None

    for i in range(count):
        entry_offset = offset + 2 + i * 12
        if entry_offset + 12 > len(exif):
            break
        tag, type_, components = struct.unpack(endian + 'HHI', exif[entry_offset:entry_offset + 8])
        value_or_offset = struct.unpack(endian + 'I', exif[entry_offset + 8:entry_offset + 12])[0]

        if tag in target_tags and type_ == 2:  # ASCII string
            if components <= 4:
                raw = exif[entry_offset + 8:entry_offset + 8 + components]
            else:
                raw = exif[value_or_offset:value_or_offset + components]
            date = _parse_exif_datetime(raw)
            if date and (best is None or tag == 0x9003):
                best = date

        # SubIFD (Exif IFD pointer)
        if tag == 0x8769 and type_ == 4:
            sub_ifd_offset = value_or_offset

    if best:
        return best
    if sub_ifd_offset:
        return _read_ifd_date(exif, sub_ifd_offset, endian, target_tags, depth + 1)
    return None


def _parse_exif_datetime(raw: bytes) -> datetime | None:
    try:
        s = raw.rstrip(b'\x00').decode('ascii', errors='ignore').strip()
        return datetime.strptime(s, '%Y:%m:%d %H:%M:%S')
    except (ValueError, UnicodeDecodeError):
        return None


def get_photo_files(directory: Path) -> list[Path]:
    files = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS
    )
    return files


def build_new_name(
    photo: Path,
    index: int,
    total: int,
    prefix: str,
    suffix: str,
    use_date: bool,
    use_sequence: bool,
) -> str:
    parts = []

    if prefix:
        parts.append(prefix)

    if use_date:
        dt = read_exif_date(photo)
        if dt:
            parts.append(dt.strftime('%Y%m%d_%H%M%S'))
        else:
            # Fall back to file modification time
            mtime = datetime.fromtimestamp(photo.stat().st_mtime)
            parts.append(mtime.strftime('%Y%m%d_%H%M%S') + '_noexif')

    if use_sequence:
        pad = len(str(total))
        parts.append(str(index).zfill(pad))

    if suffix:
        parts.append(suffix)

    if not parts:
        parts.append(photo.stem)

    name = '_'.join(parts)
    # Sanitize: remove characters unsafe in filenames
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name + photo.suffix.lower()


def preview_renames(photos: list[Path], new_names: list[str]) -> None:
    max_old = max(len(p.name) for p in photos)
    max_new = max(len(n) for n in new_names)
    col_old = max(max_old, 12)
    col_new = max(max_new, 12)

    header = f"{'CURRENT NAME':<{col_old}}  {'NEW NAME':<{col_new}}"
    print()
    print(header)
    print('-' * len(header))
    for photo, new_name in zip(photos, new_names):
        changed = photo.name != new_name
        marker = '  ->  ' if changed else '  ==  '
        print(f"{photo.name:<{col_old}}{marker}{new_name:<{col_new}}")
    print()


def apply_renames(photos: list[Path], new_names: list[str], dry_run: bool) -> tuple[int, int]:
    skipped = 0
    renamed = 0

    # Two-pass rename to avoid collisions (e.g. a->b, b->c)
    temp_map: list[tuple[Path, Path, Path]] = []

    for photo, new_name in zip(photos, new_names):
        if photo.name == new_name:
            skipped += 1
            continue
        dest = photo.parent / new_name
        temp = photo.parent / (photo.stem + '__renaming_tmp' + photo.suffix)
        temp_map.append((photo, temp, dest))

    if dry_run:
        print(f"Dry run: {len(temp_map)} file(s) would be renamed, {skipped} unchanged.")
        return len(temp_map), skipped

    # Stage to temp names first
    for src, tmp, _ in temp_map:
        src.rename(tmp)

    # Then rename from temp to final
    errors = []
    for _, tmp, dest in temp_map:
        if dest.exists():
            errors.append(f"  Skipped (destination exists): {dest.name}")
            tmp.rename(tmp.parent / tmp.name.replace('__renaming_tmp', ''))  # restore
        else:
            tmp.rename(dest)
            renamed += 1

    for e in errors:
        print(e)

    return renamed, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='photo_renamer',
        description='Rename photos using EXIF date, sequence numbers, and custom prefix/suffix.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview renaming by EXIF date with a prefix
  python photo_renamer.py ./photos --date --prefix "holiday" --preview

  # Rename sequentially with prefix and suffix
  python photo_renamer.py ./photos --sequence --prefix "trip" --suffix "2024"

  # EXIF date + sequence number, apply immediately
  python photo_renamer.py ./photos --date --sequence --prefix "vacation"

  # Dry run (show what would happen without renaming)
  python photo_renamer.py ./photos --date --dry-run
""",
    )
    parser.add_argument('directory', type=Path, help='Directory containing photos')
    parser.add_argument('--date', action='store_true', help='Include EXIF date in filename (falls back to file mtime)')
    parser.add_argument('--sequence', action='store_true', help='Include sequential number in filename')
    parser.add_argument('--prefix', default='', metavar='TEXT', help='Prefix to add to each filename')
    parser.add_argument('--suffix', default='', metavar='TEXT', help='Suffix to add before file extension')
    parser.add_argument('--preview', action='store_true', help='Show before/after preview and confirm before renaming')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be renamed without actually renaming')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation prompt (implies --preview is shown but auto-confirmed)')

    args = parser.parse_args()

    directory: Path = args.directory.resolve()

    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    if not args.date and not args.sequence and not args.prefix and not args.suffix:
        print("Error: Specify at least one of --date, --sequence, --prefix, or --suffix.", file=sys.stderr)
        print("Run with --help for usage examples.", file=sys.stderr)
        sys.exit(1)

    photos = get_photo_files(directory)

    if not photos:
        print(f"No photo files found in '{directory}'.")
        sys.exit(0)

    print(f"Found {len(photos)} photo(s) in '{directory}'.")

    new_names = [
        build_new_name(
            photo=p,
            index=i + 1,
            total=len(photos),
            prefix=args.prefix,
            suffix=args.suffix,
            use_date=args.date,
            use_sequence=args.sequence,
        )
        for i, p in enumerate(photos)
    ]

    # Always show preview when --preview or --dry-run is used
    if args.preview or args.dry_run:
        preview_renames(photos, new_names)

    if args.dry_run:
        apply_renames(photos, new_names, dry_run=True)
        return

    # If not preview mode, still show the preview before confirming
    if not args.preview:
        preview_renames(photos, new_names)

    if not args.no_confirm:
        changes = sum(1 for p, n in zip(photos, new_names) if p.name != n)
        if changes == 0:
            print("No files need renaming.")
            return
        answer = input(f"Rename {changes} file(s)? [y/N] ").strip().lower()
        if answer not in ('y', 'yes'):
            print("Aborted.")
            return

    renamed, skipped = apply_renames(photos, new_names, dry_run=False)
    print(f"Done: {renamed} file(s) renamed, {skipped} unchanged.")


if __name__ == '__main__':
    main()
