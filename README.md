# fstab-parser

A Python 3.10+ module for parsing and reconstructing `/etc/fstab` with formatting-preserving round trips.

## Usage

```python
from fstab_parser import parse_fstab, dump_fstab

text = "UUID=abc / ext4 defaults 0 1\n"
fstab = parse_fstab(text)
entry = fstab.find_by_mountpoint("/")
entry.set_option("noauto")
print(dump_fstab(fstab))
```

### Pythonic mountpoint filtering with path normalization

```python
from fstab_parser import parse_fstab

text = """\
UUID=root / ext4 defaults 0 1
UUID=usr /usr/ ext4 defaults,nosuid 0 2
UUID=var /var// ext4 defaults 0 2
UUID=tmp /tmp ext4 rw,nodev 0 2
UUID=home /home/./ ext4 rw 0 2
"""

fstab = parse_fstab(text)
entries = fstab.find_entries_without_option(
    "nosuid",
    exclude_mountpoints=("/", "/usr", "/var"),
)

# ['/tmp', '/home/./']
print([entry.fs_file for entry in entries])
```

## Guarantees

- Preserves comments, blank lines, spacing, inline comments, and trailing whitespace.
- `dump_fstab(parse_fstab(text)) == text` when no modifications are made.
- Provides strict and non-strict parsing modes.
