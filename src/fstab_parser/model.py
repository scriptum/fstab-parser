from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from posixpath import normpath
from typing import Callable, Iterator, Optional


class FstabParseError(Exception):
    def __init__(self, line_number: int, line_content: str, message: str) -> None:
        self.line_number = line_number
        self.line_content = line_content
        self.message = message
        super().__init__(f"Line {line_number}: {message}: {line_content!r}")


@dataclass(slots=True)
class BlankLine:
    raw: str = ""

    def serialize(self) -> str:
        return self.raw


@dataclass(slots=True)
class CommentLine:
    content: str

    def serialize(self) -> str:
        return self.content


@dataclass(slots=True)
class EntryLine:
    fs_spec: str
    fs_file: str
    fs_vfstype: str
    fs_mntops: str
    fs_freq: str
    fs_passno: str
    raw: str = ""
    separator_tokens: list[str] = field(default_factory=lambda: [" "] * 5)
    inline_comment: Optional[str] = None
    leading_ws: str = ""
    pre_comment_ws: str = ""
    trailing_ws_after_comment: str = ""
    line_ending: str = ""

    def _fields(self) -> list[str]:
        return [
            self.fs_spec,
            self.fs_file,
            self.fs_vfstype,
            self.fs_mntops,
            self.fs_freq,
            self.fs_passno,
        ]

    def serialize(self) -> str:
        fields = self._fields()
        core = self.leading_ws + fields[0]
        for sep, field_value in zip(self.separator_tokens, fields[1:]):
            core += sep + field_value
        core += self.pre_comment_ws
        if self.inline_comment is not None:
            core += self.inline_comment
            core += self.trailing_ws_after_comment
        return core + self.line_ending

    def get_options(self) -> dict[str, Optional[str]]:
        options: dict[str, Optional[str]] = {}
        for token in self.fs_mntops.split(","):
            if not token:
                continue
            if "=" in token:
                key, value = token.split("=", 1)
                options[key] = value
            else:
                options[token] = None
        return options

    def set_option(self, key: str, value: Optional[str] = None) -> None:
        tokens = [t for t in self.fs_mntops.split(",") if t]
        rendered = key if value is None else f"{key}={value}"
        for idx, token in enumerate(tokens):
            existing_key = token.split("=", 1)[0]
            if existing_key == key:
                tokens[idx] = rendered
                self.fs_mntops = ",".join(tokens)
                return
        tokens.append(rendered)
        self.fs_mntops = ",".join(tokens)

    def remove_option(self, key: str) -> None:
        tokens = [t for t in self.fs_mntops.split(",") if t]
        self.fs_mntops = ",".join(t for t in tokens if t.split("=", 1)[0] != key)

    def has_option(self, key: str) -> bool:
        return key in self.get_options()

    def normalized_mountpoint(self) -> str:
        return normalize_mountpoint(self.fs_file)

    def matches_mountpoint(self, path: str) -> bool:
        return self.normalized_mountpoint() == normalize_mountpoint(path)


def normalize_mountpoint(path: str) -> str:
    normalized = normpath(path)
    return "/" if normalized == "." else normalized


FstabLine = EntryLine | CommentLine | BlankLine


@dataclass(slots=True)
class Fstab:
    lines: list[FstabLine]

    def iter_entries(self) -> Iterator[EntryLine]:
        for line in self.lines:
            if isinstance(line, EntryLine):
                yield line

    def entries(self) -> list[EntryLine]:
        return list(self.iter_entries())

    def find_by_mountpoint(self, path: str) -> EntryLine:
        for entry in self.iter_entries():
            if entry.matches_mountpoint(path):
                return entry
        raise KeyError(f"No mountpoint found for {path}")

    def add_entry(self, entry: EntryLine) -> None:
        self.lines.append(entry)

    def remove_entry(self, predicate: Callable[[EntryLine], bool]) -> None:
        retained: list[FstabLine] = []
        for line in self.lines:
            if isinstance(line, EntryLine) and predicate(line):
                continue
            retained.append(line)
        self.lines = retained


def _split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _parse_entry_line(content: str, line_ending: str, line_number: int, strict: bool) -> FstabLine:
    idx = 0
    length = len(content)
    while idx < length and content[idx] in " \t":
        idx += 1
    leading_ws = content[:idx]

    fields: list[str] = []
    separators: list[str] = []

    while len(fields) < 6:
        if idx >= length:
            if strict:
                raise FstabParseError(line_number, content, "expected 6 fields")
            return CommentLine(content + line_ending)

        start = idx
        while idx < length and content[idx] not in " \t":
            idx += 1
        fields.append(content[start:idx])

        if len(fields) < 6:
            sep_start = idx
            while idx < length and content[idx] in " \t":
                idx += 1
            separator = content[sep_start:idx]
            if not separator:
                if strict:
                    raise FstabParseError(line_number, content, "missing separator between fields")
                return CommentLine(content + line_ending)
            separators.append(separator)

    remainder = content[idx:]
    pre_comment_ws = ""
    inline_comment: Optional[str] = None
    trailing_ws_after_comment = ""

    if remainder:
        ws_end = 0
        while ws_end < len(remainder) and remainder[ws_end] in " \t":
            ws_end += 1
        pre_comment_ws = remainder[:ws_end]
        suffix = remainder[ws_end:]
        if suffix.startswith("#"):
            comment = suffix
            trailing_idx = len(comment)
            while trailing_idx > 0 and comment[trailing_idx - 1] in " \t":
                trailing_idx -= 1
            inline_comment = comment[:trailing_idx]
            trailing_ws_after_comment = comment[trailing_idx:]
        elif suffix == "":
            pass
        else:
            if strict:
                raise FstabParseError(line_number, content, "unexpected trailing tokens")
            return CommentLine(content + line_ending)

    return EntryLine(
        fs_spec=fields[0],
        fs_file=fields[1],
        fs_vfstype=fields[2],
        fs_mntops=fields[3],
        fs_freq=fields[4],
        fs_passno=fields[5],
        raw=content + line_ending,
        separator_tokens=separators,
        inline_comment=inline_comment,
        leading_ws=leading_ws,
        pre_comment_ws=pre_comment_ws,
        trailing_ws_after_comment=trailing_ws_after_comment,
        line_ending=line_ending,
    )


def parse_fstab(text: str, *, strict: bool = True) -> Fstab:
    lines: list[FstabLine] = []
    for line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        content, line_ending = _split_line_ending(raw_line)
        stripped = content.strip(" \t")

        if stripped == "":
            lines.append(BlankLine(raw=raw_line))
            continue

        if content.lstrip(" \t").startswith("#"):
            lines.append(CommentLine(content=raw_line))
            continue

        lines.append(_parse_entry_line(content, line_ending, line_number, strict))

    if text and not text.endswith("\n") and not text.endswith("\r\n"):
        pass

    return Fstab(lines=lines)


def load_fstab(path: str) -> Fstab:
    with Path(path).open("r", encoding="utf-8", newline="") as fstab_file:
        return parse_fstab(fstab_file.read())


def dump_fstab(fstab: Fstab) -> str:
    return "".join(line.serialize() for line in fstab.lines)


def save_fstab(fstab: Fstab, path: str) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as fstab_file:
        fstab_file.write(dump_fstab(fstab))


def decode_escapes(value: str) -> str:
    return value.replace("\\040", " ").replace("\\011", "\t")


def encode_escapes(value: str) -> str:
    return value.replace("\t", "\\011").replace(" ", "\\040")
