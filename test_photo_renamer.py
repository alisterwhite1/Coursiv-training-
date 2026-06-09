"""Tests for photo_renamer.py"""

import struct
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from photo_renamer import (
    _parse_exif_datetime,
    build_new_name,
    get_photo_files,
    preview_renames,
    apply_renames,
    read_exif_date,
)


# --- _parse_exif_datetime ---

def test_parse_exif_datetime_valid():
    raw = b'2023:07:15 14:30:00\x00'
    result = _parse_exif_datetime(raw)
    assert result == datetime(2023, 7, 15, 14, 30, 0)


def test_parse_exif_datetime_invalid():
    assert _parse_exif_datetime(b'not a date') is None
    assert _parse_exif_datetime(b'') is None


# --- get_photo_files ---

def test_get_photo_files_filters_extensions(tmp_path):
    (tmp_path / 'a.jpg').write_bytes(b'')
    (tmp_path / 'b.PNG').write_bytes(b'')
    (tmp_path / 'c.txt').write_bytes(b'')
    (tmp_path / 'd.mp4').write_bytes(b'')
    files = get_photo_files(tmp_path)
    names = {f.name for f in files}
    assert 'a.jpg' in names
    assert 'b.PNG' in names
    assert 'c.txt' not in names
    assert 'd.mp4' not in names


def test_get_photo_files_empty(tmp_path):
    assert get_photo_files(tmp_path) == []


# --- build_new_name ---

def make_photo(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b'fake')
    return p


def test_build_new_name_prefix_only(tmp_path):
    p = make_photo(tmp_path, 'img.jpg')
    result = build_new_name(p, 1, 3, prefix='holiday', suffix='', use_date=False, use_sequence=False)
    assert result == 'holiday.jpg'


def test_build_new_name_suffix_only(tmp_path):
    p = make_photo(tmp_path, 'img.jpg')
    result = build_new_name(p, 1, 3, prefix='', suffix='trip', use_date=False, use_sequence=False)
    assert result == 'trip.jpg'


def test_build_new_name_prefix_and_suffix(tmp_path):
    p = make_photo(tmp_path, 'img.jpg')
    result = build_new_name(p, 1, 3, prefix='start', suffix='end', use_date=False, use_sequence=False)
    assert result == 'start_end.jpg'


def test_build_new_name_sequence_padding(tmp_path):
    p = make_photo(tmp_path, 'img.jpg')
    result = build_new_name(p, 3, 100, prefix='photo', suffix='', use_date=False, use_sequence=True)
    assert result == 'photo_003.jpg'


def test_build_new_name_sequence_no_prefix(tmp_path):
    p = make_photo(tmp_path, 'img.jpg')
    result = build_new_name(p, 1, 5, prefix='', suffix='', use_date=False, use_sequence=True)
    assert result == '1.jpg'


def test_build_new_name_extension_lowercased(tmp_path):
    p = make_photo(tmp_path, 'IMG.JPG')
    result = build_new_name(p, 1, 1, prefix='x', suffix='', use_date=False, use_sequence=False)
    assert result.endswith('.jpg')


def test_build_new_name_no_options_falls_back_to_stem(tmp_path):
    p = make_photo(tmp_path, 'myphoto.jpeg')
    result = build_new_name(p, 1, 1, prefix='', suffix='', use_date=False, use_sequence=False)
    assert result == 'myphoto.jpeg'


def test_build_new_name_sanitizes_unsafe_chars(tmp_path):
    p = make_photo(tmp_path, 'img.jpg')
    result = build_new_name(p, 1, 1, prefix='a/b:c', suffix='', use_date=False, use_sequence=False)
    assert '/' not in result
    assert ':' not in result


# --- apply_renames (dry run) ---

def test_apply_renames_dry_run(tmp_path):
    photos = [make_photo(tmp_path, 'a.jpg'), make_photo(tmp_path, 'b.jpg')]
    new_names = ['new_a.jpg', 'new_b.jpg']
    renamed, skipped = apply_renames(photos, new_names, dry_run=True)
    assert renamed == 2
    assert skipped == 0
    # Files should not have been renamed
    assert (tmp_path / 'a.jpg').exists()
    assert (tmp_path / 'b.jpg').exists()


def test_apply_renames_no_change(tmp_path):
    photos = [make_photo(tmp_path, 'a.jpg')]
    renamed, skipped = apply_renames(photos, ['a.jpg'], dry_run=False)
    assert renamed == 0
    assert skipped == 1
    assert (tmp_path / 'a.jpg').exists()


def test_apply_renames_actual(tmp_path):
    photos = [make_photo(tmp_path, 'old.jpg')]
    renamed, skipped = apply_renames(photos, ['new.jpg'], dry_run=False)
    assert renamed == 1
    assert skipped == 0
    assert (tmp_path / 'new.jpg').exists()
    assert not (tmp_path / 'old.jpg').exists()


def test_apply_renames_chain(tmp_path):
    """a->b and b->c should both succeed without collisions."""
    a = make_photo(tmp_path, 'a.jpg')
    b = make_photo(tmp_path, 'b.jpg')
    renamed, skipped = apply_renames([a, b], ['b.jpg', 'c.jpg'], dry_run=False)
    assert renamed == 2
    assert (tmp_path / 'b.jpg').exists()
    assert (tmp_path / 'c.jpg').exists()


# --- preview_renames (smoke test) ---

def test_preview_renames_runs(tmp_path, capsys):
    photos = [make_photo(tmp_path, 'photo.jpg')]
    preview_renames(photos, ['new_photo.jpg'])
    out = capsys.readouterr().out
    assert 'photo.jpg' in out
    assert 'new_photo.jpg' in out


# --- read_exif_date returns None for non-JPEG ---

def test_read_exif_date_non_jpeg(tmp_path):
    p = tmp_path / 'img.png'
    p.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
    assert read_exif_date(p) is None


def test_read_exif_date_missing_file(tmp_path):
    p = tmp_path / 'missing.jpg'
    assert read_exif_date(p) is None
