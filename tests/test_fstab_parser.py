from pathlib import Path

import pytest

from fstab_parser import (
    EntryLine,
    FstabParseError,
    decode_escapes,
    dump_fstab,
    encode_escapes,
    load_fstab,
    parse_fstab,
    save_fstab,
)


def test_round_trip_preserves_formatting_and_comments() -> None:
    text = (
        "# Header\n"
        "UUID=abc\t/\text4\tdefaults,noauto\t0\t1  # root fs   \n"
        "\n"
        "  # indented comment\n"
        "server:/share   /mnt/nfs\tnfs\tdefaults,_netdev\t0\t0\n"
    )
    parsed = parse_fstab(text)
    assert dump_fstab(parsed) == text


def test_inline_comment_and_separators_are_parsed() -> None:
    text = "UUID=xyz  /  ext4  defaults  0  2\t# note\n"
    entry = parse_fstab(text).entries()[0]

    assert entry.fs_spec == "UUID=xyz"
    assert entry.fs_file == "/"
    assert entry.separator_tokens == ["  ", "  ", "  ", "  ", "  "]
    assert entry.pre_comment_ws == "\t"
    assert entry.inline_comment == "# note"


def test_escape_utilities_do_not_affect_parser_round_trip() -> None:
    text = "LABEL=foo\\040bar /mnt\\011tab ext4 defaults 0 0\n"
    parsed = parse_fstab(text)
    entry = parsed.entries()[0]

    assert entry.fs_spec == "LABEL=foo\\040bar"
    assert entry.fs_file == "/mnt\\011tab"
    assert decode_escapes(entry.fs_spec) == "LABEL=foo bar"
    assert encode_escapes("a b\tc") == "a\\040b\\011c"
    assert dump_fstab(parsed) == text


def test_missing_fields_raises_in_strict_mode() -> None:
    with pytest.raises(FstabParseError) as exc:
        parse_fstab("UUID=abc / ext4 defaults 0\n")

    assert exc.value.line_number == 1


def test_missing_fields_is_preserved_in_non_strict_mode() -> None:
    text = "UUID=abc / ext4 defaults 0\n"
    parsed = parse_fstab(text, strict=False)

    assert dump_fstab(parsed) == text
    assert parsed.entries() == []


def test_mutation_preserves_layout_minimally() -> None:
    text = "UUID=abc\t/\text4\tdefaults\t0\t1 # root\n"
    parsed = parse_fstab(text)
    entry = parsed.find_by_mountpoint("/")
    entry.fs_vfstype = "xfs"

    assert dump_fstab(parsed) == "UUID=abc\t/\txfs\tdefaults\t0\t1 # root\n"


def test_mount_option_manipulation() -> None:
    entry = EntryLine("UUID=abc", "/", "ext4", "defaults,noauto,x-systemd.device-timeout=10", "0", "1")

    assert entry.get_options() == {
        "defaults": None,
        "noauto": None,
        "x-systemd.device-timeout": "10",
    }

    entry.set_option("noauto", None)
    entry.set_option("rw", None)
    entry.set_option("x-systemd.device-timeout", "20")
    entry.remove_option("defaults")

    assert entry.fs_mntops == "noauto,x-systemd.device-timeout=20,rw"


def test_duplicate_ordering_and_remove_entry() -> None:
    text = (
        "UUID=one / ext4 defaults 0 1\n"
        "UUID=two / ext4 ro 0 1\n"
        "UUID=one / ext4 noauto 0 1\n"
    )
    parsed = parse_fstab(text)
    parsed.remove_entry(lambda e: e.fs_spec == "UUID=two")

    assert [e.fs_spec for e in parsed.entries()] == ["UUID=one", "UUID=one"]


def test_load_and_save(tmp_path: Path) -> None:
    source = tmp_path / "fstab"
    out = tmp_path / "fstab.out"
    text = "UUID=abc / ext4 defaults 0 1\n"
    source.write_text(text, encoding="utf-8")

    parsed = load_fstab(str(source))
    save_fstab(parsed, str(out))

    assert out.read_text(encoding="utf-8") == text




def test_load_and_save_preserves_crlf_newlines(tmp_path: Path) -> None:
    source = tmp_path / "fstab.crlf"
    out = tmp_path / "fstab.out"
    raw = b"UUID=abc / ext4 defaults 0 1\r\n#comment\r\n"
    source.write_bytes(raw)

    parsed = load_fstab(str(source))
    save_fstab(parsed, str(out))

    assert out.read_bytes() == raw

def test_large_file_parsing() -> None:
    text = "".join(f"UUID={i} /mnt/{i} ext4 defaults 0 2\n" for i in range(10000))
    parsed = parse_fstab(text)
    assert len(parsed.entries()) == 10000
    assert dump_fstab(parsed) == text
