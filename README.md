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

## Guarantees

- Preserves comments, blank lines, spacing, inline comments, and trailing whitespace.
- `dump_fstab(parse_fstab(text)) == text` when no modifications are made.
- Provides strict and non-strict parsing modes.
