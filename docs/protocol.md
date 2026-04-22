# Protocol Reference

Deep-dive reference for the simplified SNMP wire format used in this assignment.
Code comments link here; the quick overview lives in the README.

---

## OID Encoding

An **OID** (Object Identifier) is a dotted-decimal path that names a piece of
data in the device's MIB — much like a filesystem path names a file.

```
1.3.6.1.2.1.1.5.0   →   b'\x01\x03\x06\x01\x02\x01\x01\x05\x00'
```

### Encoding rules

In our simplified protocol, each component in the OID is encoded as **one byte**:

- Each component must be in range `0`–`255`.
- The byte length of the encoded OID equals the number of components.
- Empty OIDs are invalid and should raise `ValueError`.
- Components outside `0`–`255` should raise `ValueError`.

Real SNMP uses a variable-length encoding (BER) where components can be larger
than a byte. We're skipping that complexity to focus on message framing.

### Worked example

| Step | Value |
|------|-------|
| Input string | `"1.3.6.1.2.1.1.5.0"` |
| Split by `.` | `["1", "3", "6", "1", "2", "1", "1", "5", "0"]` |
| Parse as int | `[1, 3, 6, 1, 2, 1, 1, 5, 0]` |
| Pack as bytes | `b'\x01\x03\x06\x01\x02\x01\x01\x05\x00'` |
| `.hex()` view | `"010306010201010500"` |

A reference implementation is three lines:

```python
def encode_oid(oid_string: str) -> bytes:
    return bytes(int(part) for part in oid_string.split("."))
```

### Common mistakes

- **`bytes(["1", "3", "6"])`** — fails; `bytes()` needs integers, not strings.
- **`oid_string.encode()`** — produces the ASCII bytes of the dotted string
  (`b'1.3.6.1...'`), not the encoded OID. UTF-8 encoding is never the right
  tool for OIDs.
- **Components > 255** — Python raises `ValueError: bytes must be in range(0, 256)`.
  Check your input; standard MIB-2 OIDs stay well under 255.

### Decoding

Decoding is the inverse. Python bytes iterate as integers, so the whole
function fits in one expression:

```python
def decode_oid(oid_bytes: bytes) -> str:
    return ".".join(str(b) for b in oid_bytes)
```

### Verifying your implementation

```python
>>> encode_oid("1.3.6.1.2.1.1.5.0").hex()
'010306010201010500'

>>> decode_oid(bytes.fromhex("010306010201010500"))
'1.3.6.1.2.1.1.5.0'

>>> decode_oid(encode_oid("1.3.6.1")) == "1.3.6.1"
True
```

Targeted test run:

```bash
python -m pytest tests/test_public_snmp_protocol.py -v -k "test_oid"
```
