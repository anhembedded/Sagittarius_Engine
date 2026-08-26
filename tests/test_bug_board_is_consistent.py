"""
The bug board must agree with the files on disk.

**Why this exists.** On 2026-08-25 two sessions each took "the next number"
from `Tasks/bug_report/README.md` at the same moment, and `BUG-008` and
`BUG-009` were each used for two different defects. Both `BUG-008`s ended up
cited from source — `style.py` meant a QSS cascade, `bootstrap.py` meant a
post-boot stranding — so a reader following either reference landed on the
wrong defect.

The second half of the failure was quieter and worse: the two colliding bugs
were never added to the board's Open table, so the board showed 2 open bugs
while 4 were open. The board's own docstring says it exists precisely because
"an **open** bug had nowhere to be listed at all" — an open bug missing from
it is the one failure that makes the board pointless.

Numbering by hand cannot be made safe, so it is checked instead.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path, PurePath, PureWindowsPath

_BOARD_DIR = Path(__file__).resolve().parents[1] / "Tasks" / "bug_report"
_README = _BOARD_DIR / "README.md"

#: `BUG-012_some_description.md` -> `BUG-012`
_FILENAME_RE = re.compile(r"^(BUG-\d+)_.+\.md$")

#: A board row links its id: `[BUG-012](incomplete/BUG-012_....md)`
_ROW_RE = re.compile(r"\[\*{0,2}(BUG-\d+)\*{0,2}\]\((incomplete|completed)/([^)]+)\)")


def _board_link(path: PurePath, board_dir: PurePath) -> str:
    """`path` as the board would write it: relative to the board directory,
    **forward slashes on every platform**.

    `str(Path)` is the platform's separator, so on Windows this produced
    `incomplete\\BUG-006_x.md` while `_board_rows()` builds
    `incomplete/BUG-006_x.md` from the README's markdown link. Every row then
    compared unequal and the board looked entirely broken — on Windows only.
    A separator is a property of the local filesystem; a link in a markdown
    file is not, so the comparison has to happen in the link's own form.
    """
    return path.relative_to(board_dir).as_posix()


def _bug_files() -> dict[str, list[Path]]:
    """Every bug file on disk, grouped by id — a list, so a collision is
    visible rather than silently overwritten by the last one read."""
    found: dict[str, list[Path]] = defaultdict(list)
    for subdir in ("incomplete", "completed"):
        for path in sorted((_BOARD_DIR / subdir).glob("BUG-*.md")):
            match = _FILENAME_RE.match(path.name)
            assert match, f"tên file không đúng quy ước `BUG-XXX_mô_tả.md`: {path.name}"
            found[match.group(1)].append(path)
    return dict(found)


def _board_rows() -> dict[str, str]:
    """Every id the board links to, mapped to the path it links at."""
    text = _README.read_text(encoding="utf-8")
    return {m.group(1): f"{m.group(2)}/{m.group(3)}" for m in _ROW_RE.finditer(text)}


def test_the_board_directories_are_where_we_think_they_are() -> None:
    """Every assertion below is vacuously true against an empty directory, so
    this is the one that stops a moved file from turning the rest green."""
    assert _README.is_file(), f"không thấy bảng bug ở {_README}"
    assert (_BOARD_DIR / "incomplete").is_dir()
    assert (_BOARD_DIR / "completed").is_dir()
    assert len(_bug_files()) >= 5, "quét ra quá ít bug — nhiều khả năng sai đường dẫn"


def test_a_windows_path_is_compared_in_the_form_the_board_writes() -> None:
    """The board's links are markdown, so they use `/` on every platform. This
    checks the comparison normalises to that — with an explicitly Windows-
    flavoured path, so the guard runs on Linux CI too rather than only on the
    platform that broke.

    Before `_board_link()` this whole file was red on `windows-latest` and
    green everywhere else: `str(Path)` gave `incomplete\\BUG-006_x.md`, the
    board gave `incomplete/BUG-006_x.md`, so *every* row read as broken. A
    guard that reports the entire board as a lie, on one platform, for a
    reason that has nothing to do with the board, is worse than no guard.
    """
    board = PureWindowsPath(r"C:\repo\Tasks\bug_report")
    path = PureWindowsPath(r"C:\repo\Tasks\bug_report\incomplete\BUG-006_x.md")

    assert _board_link(path, board) == "incomplete/BUG-006_x.md"
    assert "\\" not in _board_link(path, board)


def test_every_on_disk_link_is_in_the_boards_own_form() -> None:
    """The same rule against the real tree: whatever platform this runs on,
    nothing handed to the row comparison may carry a native separator."""
    links = [_board_link(p[0], _BOARD_DIR) for p in _bug_files().values()]

    assert links, "no bug files found — the path is wrong, not the board"
    assert all("\\" not in link for link in links)
    assert all(link.startswith(("incomplete/", "completed/")) for link in links)


def test_no_bug_number_is_used_twice() -> None:
    """The collision this file was written for."""
    duplicates = {
        bug_id: [_board_link(p, _BOARD_DIR) for p in paths]
        for bug_id, paths in _bug_files().items()
        if len(paths) > 1
    }

    assert duplicates == {}, (
        "một số hiệu bug được dùng cho nhiều lỗi khác nhau. Đổi số cái nào "
        "còn đang mở (nó vẫn phải thêm vào bảng), rồi sửa mọi chỗ tham chiếu "
        "— kể cả comment trong code.\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(duplicates.items()))
    )


def test_every_bug_file_has_a_row_on_the_board() -> None:
    """A bug with a file but no row is invisible to anyone reading the board,
    which is the whole reason the board exists."""
    missing = sorted(set(_bug_files()) - set(_board_rows()))

    assert missing == [], (
        "có file bug nhưng không có dòng nào trên bảng — người đọc bảng sẽ "
        f"không biết chúng tồn tại: {missing}"
    )


def test_every_board_row_points_at_a_file_that_exists() -> None:
    """The other direction: a row whose link 404s is a board that lies."""
    on_disk = {
        bug_id: _board_link(paths[0], _BOARD_DIR)
        for bug_id, paths in _bug_files().items()
    }

    broken = {
        bug_id: linked
        for bug_id, linked in _board_rows().items()
        if on_disk.get(bug_id) != linked
    }

    assert broken == {}, (
        "dòng trên bảng trỏ tới đường dẫn không khớp file thật (thường gặp "
        "sau khi `git mv` từ `incomplete/` sang `completed/` mà quên sửa "
        "link):\n"
        + "\n".join(
            f"  {k}: bảng ghi `{v}`, thật ra ở `{on_disk.get(k, '<không có>')}`"
            for k, v in sorted(broken.items())
        )
    )


def test_the_open_count_matches_the_files_in_incomplete() -> None:
    """The Overview table is the first thing a reader trusts, so it must not
    drift from the directory it summarises."""
    text = _README.read_text(encoding="utf-8")
    match = re.search(r"\|\s*🔴\s*\*\*Open\*\*\s*\|\s*(\d+)\s*\|", text)
    assert match, "không tìm thấy dòng đếm Open trong bảng Overview"

    stated = int(match.group(1))
    actual = len(list((_BOARD_DIR / "incomplete").glob("BUG-*.md")))

    assert stated == actual, (
        f"bảng Overview ghi {stated} bug đang mở, `incomplete/` có {actual}."
    )
