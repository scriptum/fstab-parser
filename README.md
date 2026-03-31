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

### Pythonic filtering with composable criteria

```python
from fstab_parser import parse_fstab

text = """\
UUID=root / ext4 defaults 0 1
UUID=var /var xfs rw,nosuid 0 2
UUID=varlog /var/log/ xfs rw,nosuid,noexec 0 2
UUID=vartmp /var/tmp/./ xfs rw,nosuid 0 2
UUID=home /home xfs rw,nosuid 0 2
"""

fstab = parse_fstab(text)
entries = fstab.filter_entries(
    fs_vfstype="xfs",
    mountpoint_startswith="/var",
    include_options=("nosuid",),
    exclude_options=("noexec",),
)

# ['/var', '/var/tmp/./']
print([entry.fs_file for entry in entries])
```

## Guarantees

- Preserves comments, blank lines, spacing, inline comments, and trailing whitespace.
- `dump_fstab(parse_fstab(text)) == text` when no modifications are made.
- Provides strict and non-strict parsing modes.
