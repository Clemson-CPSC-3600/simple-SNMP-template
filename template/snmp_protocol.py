"""
SNMP Protocol Implementation
Contains message classes and encoding/decoding logic for simplified SNMP

This file teaches you about:
1. Binary protocol encoding/decoding - How data travels over networks
2. Network byte order (big-endian) - Universal format for network communication
3. Message framing and buffering - Handling partial data from sockets
4. Type-length-value (TLV) encoding - Common protocol design pattern

Industry relevance: This is how real protocols like HTTP/2, gRPC, and database
protocols work under the hood. Understanding binary protocols is crucial for
systems programming, IoT devices, and high-performance applications.
"""

import struct
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from enum import IntEnum

# Protocol Constants
MESSAGE_HEADER_SIZE = 9  # total_size(4) + request_id(4) + pdu_type(1)
RESPONSE_HEADER_SIZE = 10  # MESSAGE_HEADER_SIZE + error_code(1)
MAX_RECV_BUFFER = 4096  # Maximum bytes to receive at once
MIN_MESSAGE_SIZE = 9  # Minimum valid message size
MAX_MESSAGE_SIZE = 65536  # Maximum message size (64KB) to prevent memory exhaustion
SIZE_FIELD_LENGTH = 4  # Length of the size field in bytes
REQUEST_ID_LENGTH = 4  # Length of request ID field
PDU_TYPE_LENGTH = 1  # Length of PDU type field in bytes
ERROR_CODE_LENGTH = 1  # Length of error code field in bytes
OID_COUNT_LENGTH = 1  # Length of OID count field in bytes
OID_LENGTH_FIELD = 1  # Length of OID length field in bytes
VALUE_TYPE_LENGTH = 1  # Length of value type field in bytes
VALUE_LENGTH_FIELD = 2  # Length of value length field in bytes
MAX_REPETITIONS_LENGTH = 2  # Length of max repetitions field in bytes
OID_COUNT_MAX = 255  # Maximum OIDs in a single request
MAX_REPETITIONS_MAX = 65535  # Maximum repetitions for bulk request
PDU_TYPE_OFFSET = 8  # Offset where PDU type is located in message
REQUEST_ID_OFFSET = 4  # Offset where request ID starts in message

# Configure module logger
logger = logging.getLogger('snmp.protocol')

# PDU Types (Protocol Data Unit types - the different message types in SNMP)
class PDUType(IntEnum):
    GET_REQUEST = 0xA0
    GET_RESPONSE = 0xA1
    SET_REQUEST = 0xA3

# Value Types (Different data types that SNMP can handle)
class ValueType(IntEnum):
    INTEGER = 0x02      # Signed 32-bit integer
    STRING = 0x04       # UTF-8 text string
    COUNTER = 0x41      # Unsigned 32-bit counter (only goes up)
    TIMETICKS = 0x43    # Time in hundredths of seconds

# Error Codes (What can go wrong in SNMP operations)
class ErrorCode(IntEnum):
    SUCCESS = 0        # Everything worked!
    NO_SUCH_OID = 1    # The requested OID doesn't exist
    BAD_VALUE = 2      # Wrong type or invalid value for SET
    READ_ONLY = 3      # Tried to SET a read-only value

def encode_oid(oid_string: str) -> bytes:
    """
    Convert OID string to bytes for network transmission.
    
    TODO: Implement OID encoding (BUNDLE 1 REQUIREMENT)
    Returns: bytes - The encoded OID as bytes
    
    ============================================================================
    WHAT IS AN OID?
    ============================================================================
    An OID (Object Identifier) is like a file path for network data.
    Just as "/home/user/documents/file.txt" identifies a file,
    "1.3.6.1.2.1.1.5.0" identifies a specific piece of network information.
    
    Real example: "1.3.6.1.2.1.1.5.0" means:
    - 1.3.6.1 = ISO.org.dod.internet
    - .2.1 = mgmt.mib-2  
    - .1.5.0 = system.sysName.0 (the device's hostname)
    
    ============================================================================
    STEP-BY-STEP TRANSFORMATION
    ============================================================================
    Input:  "1.3.6.1.2.1.1.5.0" (human-readable string)
    Output: b'\x01\x03\x06\x01\x02\x01\x01\x05\x00' (9 bytes for network)
    
    Step 1: Split the string into parts
    --------
    oid_parts = oid_string.split('.')
    # Result: ["1", "3", "6", "1", "2", "1", "1", "5", "0"]
    # Debug: print(f"Split OID into {len(oid_parts)} parts: {oid_parts}")
    
    Step 2: Convert each string to an integer
    --------
    numbers = [int(part) for part in oid_parts]
    # Result: [1, 3, 6, 1, 2, 1, 1, 5, 0]
    # Debug: print(f"Converted to integers: {numbers}")
    
    Step 3: Convert integer list to bytes
    --------
    oid_bytes = bytes(numbers)
    # Result: b'\x01\x03\x06\x01\x02\x01\x01\x05\x00'
    # Debug: print(f"Encoded as {len(oid_bytes)} bytes: {oid_bytes.hex()}")
    
    ============================================================================
    COMPLETE SOLUTION PATTERN
    ============================================================================
    def encode_oid(oid_string: str) -> bytes:
        # Split → Convert → Encode
        parts = oid_string.split('.')
        numbers = [int(part) for part in parts]
        return bytes(numbers)
    
    Or as a one-liner:
        return bytes(int(part) for part in oid_string.split('.'))
    
    ============================================================================
    UNDERSTANDING THE BYTES
    ============================================================================
    When you print the result, you might see: b'\x01\x03\x06\x01\x02\x01\x01\x05\x00'
    
    What does \x01 mean?
    - \x indicates hexadecimal notation
    - 01 is the hex value (equals decimal 1)
    - Each \xNN represents one byte
    
    You may also see letters and symbols mixed in with \xNN. This happens when 
    the hex value maps on to a UTF-8 character and python automatically translates 
    it for you.
    
    To see the raw hexadecimal more clearly, use .hex():
        oid_bytes.hex() → "010306010201010500"
        ' '.join(f'{b:02x}' for b in oid_bytes) → "01 03 06 01 02 01 01 05 00"
    
    ============================================================================
    COMMON MISTAKES AND FIXES
    ============================================================================
    
    Mistake 1: Forgetting to convert strings to ints
    --------
    Wrong: bytes(["1", "3", "6"])  # Error: strings aren't 0-255 integers!
    Right: bytes([1, 3, 6])        # Works: integers in valid range
    
    Mistake 2: Trying to encode the string directly
    --------
    Wrong: oid_string.encode()      # Gives b'1.3.6.1...' (wrong!)
    Right: Use the algorithm above  # Gives b'\x01\x03\x06...' (correct!)
    
    Mistake 3: Numbers outside 0-255 range
    --------
    If you get "bytes must be in range(0, 256)":
    - Check your OID doesn't have numbers > 255
    - Standard OIDs shouldn't have this issue
    
    ============================================================================
    TESTING YOUR IMPLEMENTATION
    ============================================================================
    
    Quick test in Python:
        >>> encode_oid("1.3.6.1.2.1.1.5.0")
        b'\x01\x03\x06\x01\x02\x01\x01\x05\x00'
        
        >>> encode_oid("1.3.6.1.2.1.1.5.0").hex()
        '010306010201010500'
    
    Run the test suite:
        python3 -m pytest tests/integration/test_protocol_structure.py::TestOIDEncoding::test_simple_oid_encoding -v
    
    See README section 3.2.4 for complete OID format specification.
    """
    # TODO: Split the OID string by '.' into a list of string numbers
    # TODO: Convert each string number to an integer
    # TODO: Convert the list of integers to bytes using bytes()
    # Debugging: Add print statements to verify each step!
    raise NotImplementedError("Implement encode_oid")

def decode_oid(oid_bytes: bytes) -> str:
    """
    Convert OID bytes back to human-readable string format.
    
    TODO: Implement OID decoding (BUNDLE 1 REQUIREMENT)
    Returns: str - The decoded OID as a dotted string
    
    ============================================================================
    THE REVERSE OPERATION
    ============================================================================
    This reverses encode_oid(), converting network bytes back to readable format.
    When your program receives bytes from the network, you need to understand
    what they mean - that's what decoding does!
    
    Input:  b'\x01\x03\x06\x01\x02\x01\x01\x05\x00' (9 bytes from network)
    Output: "1.3.6.1.2.1.1.5.0" (human-readable string)
    
    ============================================================================
    KEY INSIGHT: BYTES ARE ALREADY INTEGERS!
    ============================================================================
    In Python, when you iterate over bytes, you get integers automatically:
    
    >>> data = b'\x01\x03\x06'
    >>> for byte in data:
    ...     print(f"Type: {type(byte)}, Value: {byte}")
    Type: <class 'int'>, Value: 1
    Type: <class 'int'>, Value: 3  
    Type: <class 'int'>, Value: 6
    
    This means bytes are easier to work with than you might think! You do NOT
    have to unpack **individual** bytes to convert them into integers.
    
    ============================================================================
    STEP-BY-STEP ALGORITHM
    ============================================================================
    
    Step 1: Understand what you have
    --------
    # Let's say oid_bytes = b'\x01\x03\x06\x01\x02\x01\x01\x05\x00'
    # Debug: print(f"Decoding {len(oid_bytes)} bytes: {oid_bytes.hex()}")
    # Shows: "Decoding 9 bytes: 010306010201010500"
    
    Step 2: Extract the integer values
    --------
    # Method 1: Using list comprehension
    numbers = [byte for byte in oid_bytes]
    # Result: [1, 3, 6, 1, 2, 1, 1, 5, 0]
    # Debug: print(f"Integer values: {numbers}")
    
    # Method 2: Direct conversion (bytes are iterable!)
    numbers = list(oid_bytes)  # Same result!
    
    Step 3: Convert integers to strings
    --------
    string_parts = [str(num) for num in numbers]
    # Result: ["1", "3", "6", "1", "2", "1", "1", "5", "0"]
    # Debug: print(f"String parts: {string_parts}")
    
    Step 4: Join with dots
    --------
    oid_string = '.'.join(string_parts)
    # Result: "1.3.6.1.2.1.1.5.0"
    # Debug: print(f"Final OID: {oid_string}")
    
    ============================================================================
    COMPLETE SOLUTION PATTERNS
    ============================================================================
    
    Pattern 1: Step by step (easiest to understand)
    --------
    def decode_oid(oid_bytes: bytes) -> str:
        numbers = list(oid_bytes)           # Get integers
        strings = [str(n) for n in numbers] # Convert to strings
        return '.'.join(strings)             # Join with dots
    
    Pattern 2: One-liner (more Pythonic)
    --------
    def decode_oid(oid_bytes: bytes) -> str:
        return '.'.join(str(byte) for byte in oid_bytes)
    
    Both work! Choose the one that makes most sense to you.
    
    ============================================================================
    DEBUGGING YOUR IMPLEMENTATION
    ============================================================================
    
    Add these debug prints to understand what's happening:
    
    def decode_oid(oid_bytes: bytes) -> str:
        print(f"Input bytes (hex): {oid_bytes.hex()}")
        print(f"Input bytes (repr): {oid_bytes!r}")
        
        # See the integer values
        print(f"As integers: {list(oid_bytes)}")
        
        # Build the result
        result = '.'.join(str(byte) for byte in oid_bytes)
        print(f"Output string: {result}")
        
        return result
    
    ============================================================================
    COMMON MISTAKES TO AVOID
    ============================================================================
    
    Mistake 1: Trying to decode as UTF-8
    --------
    Wrong: oid_bytes.decode('utf-8')   # Error! These aren't text bytes
    Right: Use the algorithm above     # Treats bytes as numbers
    
    Mistake 2: Forgetting to convert to strings before joining
    --------
    Wrong: '.'.join(oid_bytes)         # Error! Can't join integers
    Wrong: '.'.join(list(oid_bytes))   # Still integers!
    Right: '.'.join(str(b) for b in oid_bytes)  # Converts to strings first
    
    Mistake 3: Using hex values instead of decimal
    --------
    Wrong: '.'.join(f'{b:02x}' for b in oid_bytes)  # Gives "01.03.06..." (hex)
    Right: '.'.join(str(b) for b in oid_bytes)      # Gives "1.3.6..." (decimal)
    
    ============================================================================
    TESTING YOUR IMPLEMENTATION  
    ============================================================================
    
    Quick test in Python REPL:
        >>> decode_oid(b'\x01\x03\x06\x01\x02\x01\x01\x05\x00')
        '1.3.6.1.2.1.1.5.0'
        
        >>> decode_oid(b'\x01\x03')
        '1.3'
    
    Verify it reverses encode_oid:
        >>> oid = "1.3.6.1.2.1.1.5.0"
        >>> decode_oid(encode_oid(oid)) == oid
        True
    
    Run the test:
        python3 -m pytest tests/integration/test_protocol_structure.py::TestOIDEncoding::test_oid_decoding -v
    
    See README section 3.2.4 for complete OID format details.
    """
    # TODO: Method 1 - Step by step:
    #   - Convert bytes to list of integers (hint: list(oid_bytes))
    #   - Convert each integer to string (hint: [str(n) for n in ...])
    #   - Join strings with '.' (hint: '.'.join(...))
    
    # TODO: Method 2 - One line:
    #   - Join the string conversion of each byte: '.'.join(str(byte) for byte in oid_bytes)
    
    # Debugging: Print intermediate values to verify your logic!
    raise NotImplementedError("Implement decode_oid")

def encode_value(value: Any, value_type: ValueType) -> bytes:
    """
    Encode a Python value into network bytes based on its SNMP type.
    
    TODO: Implement value encoding (BUNDLE 1 REQUIREMENT)
    Returns: bytes - The encoded value ready for network transmission
    
    This function is THE HEART of protocol implementation - it converts Python
    data into the exact byte format the network expects. Get this wrong, and
    nothing works!
    
    ============================================================================
    UNDERSTANDING NETWORK BYTE ORDER (BIG-ENDIAN)
    ============================================================================
    Networks use "big-endian" byte order - most significant byte first.
    Think of it like writing numbers: we write 1234 with the "big" digit (1) first.
    
    Example: The number 1234 (0x04D2 in hex)
    - In memory (little-endian): D2 04        (least significant first)
    - On network (big-endian):   04 D2        (most significant first)
    - struct.pack('!H', 1234) →  b'\x04\xd2'  (! means network/big-endian)
    
    ============================================================================
    ValueType.INTEGER (0x02) - Signed 32-bit integers
    ============================================================================
    Range: -2,147,483,648 to 2,147,483,647
    Format: 4 bytes, network byte order, SIGNED (can be negative)
    
    Implementation:
        if value_type == ValueType.INTEGER:
            return struct.pack('!i', value)
            #                   ^  ^
            #        network order  signed 32-bit int
    
    Examples with hex breakdown:
        encode_value(42, ValueType.INTEGER)
        → b'\x00\x00\x00\x2a'
        → Hex: 00 00 00 2a (42 in hex is 0x2a)
        
        encode_value(-1, ValueType.INTEGER)  
        → b'\xff\xff\xff\xff'
        → -1 in two's complement = all bits set
        
        encode_value(1234, ValueType.INTEGER)
        → b'\x00\x00\x04\xd2'
        → 1234 = 0x04d2, padded to 4 bytes
    
    Debug check: len(result) == 4  # Always 4 bytes!
    
    ============================================================================
    ValueType.STRING (0x04) - UTF-8 text strings
    ============================================================================
    Format: Variable length UTF-8 bytes
    
    Implementation:
        if value_type == ValueType.STRING:
            if isinstance(value, bytes):
                return value  # Already bytes, return as-is
            return value.encode('utf-8')  # Convert string to UTF-8 bytes
    
    Examples:
        encode_value("test", ValueType.STRING)
        → b'test'
        → Hex: 74 65 73 74 (ASCII values)
        
        encode_value("", ValueType.STRING)
        → b''  # Empty bytes for empty string
        
        encode_value("Hello 🌍", ValueType.STRING)
        → b'Hello \xf0\x9f\x8c\x8d'
        → "Hello " in ASCII + emoji in UTF-8 (4 bytes)
    
    Edge case to handle:
        # Sometimes value might already be bytes
        encode_value(b'already bytes', ValueType.STRING)
        → b'already bytes'  # Return unchanged
    
    Debug: print(f"String '{value}' → {result.hex()} ({len(result)} bytes)")
    
    ============================================================================
    ValueType.COUNTER (0x41) - Unsigned 32-bit counters
    ============================================================================
    Range: 0 to 4,294,967,295
    Format: 4 bytes, network byte order, UNSIGNED (never negative)
    Note: Counters represent things that only go up (packets sent, errors, etc.)
    
    Implementation:
        if value_type == ValueType.COUNTER:
            return struct.pack('!I', value)
            #                   ^  ^
            #        network order  UNSIGNED 32-bit int
    
    Examples:
        encode_value(1000000, ValueType.COUNTER)
        → b'\x00\x0f\x42\x40'
        → 1000000 = 0x0F4240 in hex
        
        encode_value(4294967295, ValueType.COUNTER)  # Max value
        → b'\xff\xff\xff\xff'
        → All bits set for maximum unsigned value
    
    IMPORTANT: 'I' (capital) = unsigned, 'i' (lowercase) = signed!
    
    ============================================================================
    ValueType.TIMETICKS (0x43) - Time in hundredths of seconds
    ============================================================================
    Range: 0 to 4,294,967,295 (about 497 days)
    Format: Same as COUNTER - 4 bytes unsigned
    
    Implementation:
        if value_type == ValueType.TIMETICKS:
            return struct.pack('!I', value)  # Same as COUNTER
    
    Example:
        encode_value(360000, ValueType.TIMETICKS)
        → b'\x00\x05\x7e\x40'
        → 360000 ticks = 3600 seconds = 1 hour
        → 360000 = 0x057E40 in hex
    
    Real usage: System uptime is often measured in timeticks
    
    ============================================================================
    COMPLETE IMPLEMENTATION PATTERN
    ============================================================================
    def encode_value(value: Any, value_type: ValueType) -> bytes:
        if value_type == ValueType.INTEGER:
            return struct.pack('!i', value)  # Signed
        elif value_type == ValueType.STRING:
            if isinstance(value, bytes):
                return value
            return value.encode('utf-8')
        elif value_type == ValueType.COUNTER:
            return struct.pack('!I', value)  # Unsigned
        elif value_type == ValueType.TIMETICKS:
            return struct.pack('!I', value)  # Unsigned
        else:
            raise ValueError(f"Unknown value type: {value_type}")
    
    ============================================================================
    DEBUGGING YOUR IMPLEMENTATION
    ============================================================================
    
    Add debug prints:
        result = encode_value(value, value_type)
        print(f"Encoded {value} as {value_type.name}:")
        print(f"  Bytes: {result!r}")
        print(f"  Hex: {result.hex()}")
        print(f"  Length: {len(result)}")
    
    Common errors and fixes:
    1. "struct.error: argument out of range"
       → Integer too large for format (check signed vs unsigned)
    
    2. "AttributeError: 'bytes' object has no attribute 'encode'"
       → You're trying to encode bytes - check for bytes first!
    
    3. Wrong byte order (getting weird values)
       → Make sure you use '!' for network byte order
    
    Test: python3 -m pytest tests/integration/test_protocol_structure.py::TestValueTypeEncoding -v
    """
    # TODO: Use if/elif/else to check value_type
    # TODO: For INTEGER: struct.pack('!i', value) - lowercase 'i' for signed!
    # TODO: For STRING: Check if bytes first, then encode('utf-8')
    # TODO: For COUNTER: struct.pack('!I', value) - capital 'I' for unsigned!
    # TODO: For TIMETICKS: struct.pack('!I', value) - same as COUNTER
    # TODO: Don't forget the else clause to raise ValueError!
    raise NotImplementedError("Implement encode_value")

def decode_value(value_bytes: bytes, value_type: ValueType) -> Any:
    """
    Decode network bytes back to Python values based on SNMP type.
    
    TODO: Implement value decoding (BUNDLE 1 REQUIREMENT)
    Returns: int or str - The decoded Python value
    
    This reverses encode_value() - when you receive bytes from the network,
    you need to convert them back to usable Python values!
    
    ============================================================================
    THE TUPLE TRAP - MOST COMMON MISTAKE!
    ============================================================================
    struct.unpack() returns a TUPLE, not a single value!
    
    >>> struct.unpack('!i', b'\x00\x00\x00\x2a')
    (42,)  # <-- This is a tuple with one element!
    
    >>> struct.unpack('!i', b'\x00\x00\x00\x2a')[0]
    42     # <-- This extracts the actual value!
    
    ALWAYS use [0] to extract the value from the tuple!
    
    ============================================================================
    ValueType.INTEGER (0x02) - Decode to signed int
    ============================================================================
    Input: Exactly 4 bytes in network byte order
    Output: Python int (can be negative)
    
    Implementation:
        if value_type == ValueType.INTEGER:
            return struct.unpack('!i', value_bytes)[0]
            #                     ^  ^              ^
            #          network order  |              |
            #                   signed int      EXTRACT FROM TUPLE!
    
    Examples with explanation:
        decode_value(b'\x00\x00\x00\x2a', ValueType.INTEGER)
        → Hex: 00 00 00 2a
        → Decimal: 42
        
        decode_value(b'\xff\xff\xff\xff', ValueType.INTEGER)
        → All bits set = -1 in two's complement
        → Returns: -1
        
        decode_value(b'\x80\x00\x00\x00', ValueType.INTEGER)
        → Most significant bit set = negative
        → Returns: -2147483648 (minimum int32)
    
    Debug visualization:
        data = b'\x00\x00\x04\xd2'
        print(f"Hex: {data.hex()}")  # "000004d2"
        print(f"As int: {struct.unpack('!i', data)[0]}")  # 1234
    
    ============================================================================
    ValueType.STRING (0x04) - Decode to str
    ============================================================================
    Input: UTF-8 encoded bytes (variable length)
    Output: Python string
    
    Implementation:
        if value_type == ValueType.STRING:
            return value_bytes.decode('utf-8')
            # No [0] needed - decode returns string directly!
    
    Examples:
        decode_value(b'test', ValueType.STRING)
        → "test"
        
        decode_value(b'', ValueType.STRING)
        → ""  # Empty string from empty bytes
        
        decode_value(b'Hello \xf0\x9f\x8c\x8d', ValueType.STRING)
        → "Hello 🌍"  # UTF-8 can handle emojis!
        
        decode_value(b'Router-1', ValueType.STRING)
        → "Router-1"
    
    Note: decode() returns a string directly, NOT a tuple!
    
    ============================================================================
    ValueType.COUNTER (0x41) - Decode to unsigned int
    ============================================================================
    Input: Exactly 4 bytes in network byte order
    Output: Python int (always positive, 0 to 4,294,967,295)
    
    Implementation:
        if value_type == ValueType.COUNTER:
            return struct.unpack('!I', value_bytes)[0]
            #                     ^  ^              ^
            #          network order  |              |
            #                 UNSIGNED int      DON'T FORGET!
    
    Examples:
        decode_value(b'\x00\x0f\x42\x40', ValueType.COUNTER)
        → Hex: 00 0f 42 40
        → Decimal: 1000000
        
        decode_value(b'\xff\xff\xff\xff', ValueType.COUNTER)
        → All bits set for unsigned = maximum value
        → Returns: 4294967295
    
    CRITICAL: Use 'I' (capital) for unsigned, not 'i' (lowercase)!
    Wrong: struct.unpack('!i', b'\xff\xff\xff\xff')[0] → -1
    Right: struct.unpack('!I', b'\xff\xff\xff\xff')[0] → 4294967295
    
    ============================================================================
    ValueType.TIMETICKS (0x43) - Decode to unsigned int  
    ============================================================================
    Same format as COUNTER - 4 bytes unsigned
    Represents time in 1/100ths of a second
    
    Implementation:
        if value_type == ValueType.TIMETICKS:
            return struct.unpack('!I', value_bytes)[0]  # Same as COUNTER
    
    Example:
        decode_value(b'\x00\x05\x7e\x40', ValueType.TIMETICKS)
        → 360000 ticks
        → 360000 / 100 = 3600 seconds = 1 hour uptime
    
    ============================================================================
    COMPLETE IMPLEMENTATION PATTERN
    ============================================================================
    def decode_value(value_bytes: bytes, value_type: ValueType) -> Any:
        if value_type == ValueType.INTEGER:
            return struct.unpack('!i', value_bytes)[0]  # signed + [0]
        elif value_type == ValueType.STRING:
            return value_bytes.decode('utf-8')          # no [0] needed!
        elif value_type == ValueType.COUNTER:
            return struct.unpack('!I', value_bytes)[0]  # unsigned + [0]
        elif value_type == ValueType.TIMETICKS:
            return struct.unpack('!I', value_bytes)[0]  # unsigned + [0]
        else:
            raise ValueError(f"Unknown value type: {value_type}")
    
    ============================================================================
    DEBUGGING STRATEGY
    ============================================================================
    
    Add these debug prints:
        print(f"Decoding {value_type.name}:")
        print(f"  Input bytes: {value_bytes!r}")
        print(f"  Hex: {value_bytes.hex()}")
        print(f"  Length: {len(value_bytes)} bytes")
        
        # Try decoding
        result = decode_value(value_bytes, value_type)
        print(f"  Result: {result} (type: {type(result).__name__})")
    
    Common errors:
    1. "struct.error: unpack requires a buffer of 4 bytes"
       → Wrong number of bytes for integer types (must be exactly 4)
    
    2. Getting tuple instead of value: (42,)
       → You forgot [0] after struct.unpack()!
    
    3. Negative value when expecting positive
       → Using 'i' instead of 'I' for unsigned types
    
    4. "UnicodeDecodeError" for STRING
       → The bytes aren't valid UTF-8 (shouldn't happen with valid SNMP)
    
    ============================================================================
    TESTING YOUR WORK
    ============================================================================
    
    Verify encode/decode round-trip:
        >>> value = 42
        >>> encoded = encode_value(value, ValueType.INTEGER)
        >>> decoded = decode_value(encoded, ValueType.INTEGER)
        >>> assert decoded == value  # Should work!
    
    Test: python3 -m pytest tests/integration/test_protocol_structure.py::TestValueTypeEncoding -v
    """
    # TODO: Use if/elif/else to check value_type
    # TODO: For INTEGER: struct.unpack('!i', value_bytes)[0] - don't forget [0]!
    # TODO: For STRING: value_bytes.decode('utf-8') - no [0] needed!
    # TODO: For COUNTER: struct.unpack('!I', value_bytes)[0] - capital 'I'!
    # TODO: For TIMETICKS: struct.unpack('!I', value_bytes)[0] - same as COUNTER!
    # TODO: else: raise ValueError(f"Unknown value type: {value_type}")
    raise NotImplementedError("Implement decode_value")

class SNMPMessage(ABC):
    """Base class for all SNMP messages"""
    
    def __init__(self, request_id: int, pdu_type: PDUType):
        self.request_id = request_id
        self.pdu_type = pdu_type
    
    @abstractmethod
    def pack(self) -> bytes:
        """Convert message to bytes for transmission"""
        pass
    
    @classmethod
    @abstractmethod
    def unpack(cls, data: bytes) -> 'SNMPMessage':
        """Create message instance from received bytes"""
        pass

class GetRequest(SNMPMessage):
    """SNMP GetRequest message - Requests values from the agent"""
    
    def __init__(self, request_id: int, oids: List[str]):
        super().__init__(request_id, PDUType.GET_REQUEST)
        self.oids = oids
    
    def pack(self) -> bytes:
        """
        Pack this GetRequest into bytes for network transmission.
        
        TODO: Implement GetRequest packing (BUNDLE 1 REQUIREMENT)
        Returns: bytes - The complete message ready to send over the network
        
        You're creating the actual bytes that will travel across the network!
        This must EXACTLY match the format in README section 3.3.1.
        
        ============================================================================
        MESSAGE STRUCTURE (See README Section 3.3.1 for full details)
        ============================================================================
        ┌──────────────┬──────────────┬───────────┬─────────────────────────┐
        │ total_size   │ request_id   │ pdu_type  │ payload                 │
        │ (4 bytes)    │ (4 bytes)    │ (1 byte)  │ (variable)              │
        └──────────────┴──────────────┴───────────┴─────────────────────────┘
        
        Payload for GetRequest:
        ┌────────────┬──────────────────────────────────────────────┐
        │ oid_count  │ OID list (each with length prefix)          │
        │ (1 byte)   │ (variable)                                   │
        └────────────┴──────────────────────────────────────────────┘
        
        ============================================================================
        STEP-BY-STEP IMPLEMENTATION
        ============================================================================
        
        Step 1: Build the payload (the OID data)
        -----------------------------------------
        The payload contains the OID count and all OIDs with their lengths.
        
        # Start with the number of OIDs (1 byte)
        payload = struct.pack('!B', len(self.oids))
        # Debug: print(f"OID count: {len(self.oids)}")
        
        # Add each OID with its length prefix
        for oid in self.oids:
            # Convert OID string to bytes using YOUR encode_oid function!
            oid_bytes = encode_oid(oid)
            # Debug: print(f"  OID '{oid}' -> {len(oid_bytes)} bytes: {oid_bytes.hex()}")
            
            # Add length prefix (1 byte) then the OID bytes
            payload += struct.pack('!B', len(oid_bytes))
            payload += oid_bytes
        
        # Debug: print(f"Total payload: {len(payload)} bytes")
        
        Step 2: Calculate the total message size
        -----------------------------------------
        CRITICAL: total_size includes EVERYTHING, including itself!
        
        total_size = 4 + 4 + 1 + len(payload)
                     ↑   ↑   ↑   ↑
           size field itself   │   │
                   request_id ──┘   │
                          pdu_type ──┘
                                 payload
        
        # Debug: print(f"Message size calculation: 4+4+1+{len(payload)} = {total_size}")
        
        Step 3: Assemble the complete message
        --------------------------------------
        Build the message in order: size, request_id, pdu_type, payload
        
        message = b''  # Start with empty bytes
        message += struct.pack('!I', total_size)       # 4 bytes: total size
        message += struct.pack('!I', self.request_id)  # 4 bytes: request ID
        message += struct.pack('!B', self.pdu_type)    # 1 byte: PDU type (0xA0)
        message += payload                             # Variable: the OID data
        
        # CRITICAL VERIFICATION - the size field must match actual length!
        assert len(message) == total_size, f"Size mismatch! Header says {total_size}, actual {len(message)}"
        
        return message
        
        ============================================================================
        COMPLETE EXAMPLE WALKTHROUGH
        ============================================================================
        Creating GetRequest(request_id=1234, oids=["1.3.6.1.2.1.1.5.0"])
        
        Step 1: Build payload
        - OID count: 1 -> b'\\x01'
        - encode_oid("1.3.6.1.2.1.1.5.0") -> b'\\x01\\x03\\x06\\x01\\x02\\x01\\x01\\x05\\x00' (9 bytes)
        - OID length: 9 -> b'\\x09'
        - Payload = b'\\x01' + b'\\x09' + b'\\x01\\x03\\x06\\x01\\x02\\x01\\x01\\x05\\x00'
        - Total payload: 11 bytes
        
        Step 2: Calculate size
        - total_size = 4 + 4 + 1 + 11 = 20 bytes
        
        Step 3: Build message
        - Size field: struct.pack('!I', 20) -> b'\\x00\\x00\\x00\\x14'
        - Request ID: struct.pack('!I', 1234) -> b'\\x00\\x00\\x04\\xd2'
        - PDU type: struct.pack('!B', 0xA0) -> b'\\xa0'
        - Complete: 20 bytes total
        
        Final bytes (hex view):
        00 00 00 14  # Total size: 20 (0x14 in hex)
        00 00 04 d2  # Request ID: 1234 (0x4d2 in hex)
        a0           # PDU type: GET_REQUEST
        01           # OID count: 1
        09           # OID length: 9
        01 03 06 01 02 01 01 05 00  # The OID bytes
        
        ============================================================================
        DEBUGGING CHECKLIST
        ============================================================================
        
        ✓ Does encode_oid() work? Test it separately first!
        ✓ Is total_size correct? It should equal len(message)
        ✓ Are you using network byte order ('!') for all struct.pack calls?
        ✓ Did you include the size field itself in total_size?
        ✓ Print the hex to verify: print(message.hex())
        
        Common bugs and fixes:
        1. "Message too short" error
           -> You forgot to include header size in total_size
        
        2. Wrong request ID on receiver side
           -> Check byte order - must use '!I' not 'I'
        
        3. "Unknown PDU type" error
           -> Make sure self.pdu_type is PDUType.GET_REQUEST (0xA0)
        
        Test: python3 -m pytest tests/integration/test_protocol_structure.py::TestMessageSizeCalculation::test_single_oid_size -v
        
        See README Section 3.3.1 for the complete GetRequest specification.
        See README Section 6 for Mermaid diagrams showing message structure.
        """
        # TODO: Step 1 - Build payload with OID count and encoded OIDs
        # TODO: Step 2 - Calculate total_size (remember to include the header!)
        # TODO: Step 3 - Pack all fields in order: size, request_id, pdu_type, payload
        # Debug tip: Add print statements to verify each step!
        raise NotImplementedError("Implement GetRequest.pack()")
    
    @classmethod
    def unpack(cls, data: bytes) -> 'GetRequest':
        """
        Create GetRequest from received network bytes.
        
        TODO: Implement GetRequest unpacking (BUNDLE 2 REQUIREMENT)
        Returns: GetRequest - A new GetRequest object with the unpacked data
        
        This reverses the pack() operation - you receive bytes from the network
        and need to extract the information to create a GetRequest object.
        
        The header has already been validated, so you know:
        - data[0:4] = total_size
        - data[4:8] = request_id 
        - data[8] = pdu_type (already checked to be GET_REQUEST)
        - data[9:] = payload
        
        Algorithm:
        1. Extract request_id from bytes 4-8
           request_id = struct.unpack('!I', data[4:8])[0]
        
        2. Start parsing payload at byte 9
           oid_count = struct.unpack('!B', data[9:10])[0]
        
        3. Parse each OID from the payload
           offset = 10  # Start after oid_count
           oids = []
           for _ in range(oid_count):
               oid_length = struct.unpack('!B', data[offset:offset+1])[0]
               offset += 1
               oid_bytes = data[offset:offset+oid_length]
               offset += oid_length
               oid_string = decode_oid(oid_bytes)  # Use your decode_oid!
               oids.append(oid_string)
        
        4. Create and return the GetRequest object
           return cls(request_id, oids)
        
        Debugging approach:
        - Print what you're unpacking: print(f"Request ID: {request_id}, OID count: {oid_count}")
        - Track your offset: print(f"Current offset: {offset}, remaining: {len(data)-offset}")
        
        Test verification: Works with test_single_oid_get when agent is complete
        Run: python3 -m pytest tests/integration/test_get_operations.py::TestGetOperations::test_single_oid_get -v
        """
        # TODO: Extract request_id from bytes 4-8
        # TODO: Extract oid_count from byte 9
        # TODO: Loop through and decode each OID
        # TODO: Return new GetRequest with extracted data
        raise NotImplementedError("Implement GetRequest.unpack()")

class SetRequest(SNMPMessage):
    """SNMP SetRequest message - Updates values on the agent"""
    
    def __init__(self, request_id: int, bindings: List[Tuple[str, ValueType, Any]]):
        super().__init__(request_id, PDUType.SET_REQUEST)
        self.bindings = bindings  # List of (oid, value_type, value) tuples
    
    def pack(self) -> bytes:
        """
        Pack this SetRequest into bytes for network transmission.
        
        TODO: Implement SetRequest packing (BUNDLE 2 REQUIREMENT)
        Returns: bytes - The complete message ready to send
        
        Similar to GetRequest, but includes values with each OID.
        See README section 3.3.2 for the complete format.
        
        ============================================================================
        MESSAGE FORMAT (SetRequest)
        ============================================================================
        Header (same as GetRequest):
        ┌──────────────┬──────────────┬───────────┬─────────────────────────┐
        │ total_size   │ request_id   │ pdu_type  │ payload                 │
        │ (4 bytes)    │ (4 bytes)    │ (1 byte)  │ (variable)              │
        └──────────────┴──────────────┴───────────┴─────────────────────────┘
        
        Payload contains OID-value bindings:
        ┌────────────┬──────────────────────────────────────────────┐
        │ oid_count  │ Binding list                                 │
        │ (1 byte)   │ (variable)                                   │
        └────────────┴──────────────────────────────────────────────┘
        
        Each binding in the list:
        ┌────────────┬────────────┬────────────┬──────────────┬──────────────┐
        │ oid_length │ oid_bytes  │ value_type │ value_length │ value_data   │
        │ (1 byte)   │ (variable) │ (1 byte)   │ (2 bytes)    │ (variable)   │
        └────────────┴────────────┴────────────┴──────────────┴──────────────┘
        
        ============================================================================
        IMPLEMENTATION
        ============================================================================
        
        Build payload with OID-value bindings:
        
        payload = struct.pack('!B', len(self.bindings))  # Binding count
        
        for oid, value_type, value in self.bindings:
            # Encode the OID
            oid_bytes = encode_oid(oid)
            payload += struct.pack('!B', len(oid_bytes))
            payload += oid_bytes
            
            # Encode the value
            value_bytes = encode_value(value, value_type)  # Use your function!
            payload += struct.pack('!B', value_type)       # Value type (1 byte)
            payload += struct.pack('!H', len(value_bytes)) # Value length (2 bytes!)
            payload += value_bytes                         # The actual value
        
        Note: value_length is 2 bytes (!H) to support larger string values!
        
        Example for setting sysName to "router1":
        - OID: "1.3.6.1.2.1.1.5.0" 
        - Type: ValueType.STRING
        - Value: "router1"
        
        Results in payload containing:
        01                    # 1 binding
        09                    # OID length
        01 03 06 01 02 01 01 05 00  # OID bytes
        04                    # ValueType.STRING
        00 07                 # Value length (7 bytes)
        72 6f 75 74 65 72 31  # "router1" in UTF-8
        
        Test verification: TestMessageSizeCalculation::test_set_request_size
        Quick test: python3 -m pytest tests/integration/test_protocol_structure.py::TestMessageSizeCalculation::test_set_request_size -v
        """
        # TODO: Build payload with bindings
        # TODO: Remember value_length is 2 bytes (!H not !B)
        # TODO: Calculate total_size and build complete message
        raise NotImplementedError("Implement SetRequest.pack()")
    
    @classmethod
    def unpack(cls, data: bytes) -> 'SetRequest':
        """
        Create SetRequest from received network bytes.
        
        TODO: Implement SetRequest unpacking (BUNDLE 2 REQUIREMENT)
        Returns: SetRequest - A new SetRequest object with the unpacked data
        
        Parse both OIDs and their associated values.
        
        Algorithm:
        1. Extract request_id (bytes 4-8)
        2. Get binding count from byte 9
        3. For each binding, extract:
           - OID length and bytes → decode to string
           - Value type (1 byte)
           - Value length (2 bytes! Use !H)
           - Value data → decode using decode_value()
        4. Create SetRequest with all bindings
        
        Watch out for the 2-byte value length field!
        value_length = struct.unpack('!H', data[offset:offset+2])[0]
        offset += 2
        
        Test verification: Works with test_set_string_value when agent is complete
        Run: python3 -m pytest tests/integration/test_set_operations.py::TestSetOperations::test_set_string_value -v
        """
        # TODO: Extract request_id and binding count
        # TODO: Loop through bindings, extracting OID, type, and value
        # TODO: Use decode_oid() and decode_value() appropriately
        # TODO: Return new SetRequest with all bindings
        raise NotImplementedError("Implement SetRequest.unpack()")

class GetResponse(SNMPMessage):
    """SNMP GetResponse message - Agent's response to requests"""
    
    def __init__(self, request_id: int, error_code: ErrorCode, 
                 bindings: List[Tuple[str, ValueType, Any]]):
        super().__init__(request_id, PDUType.GET_RESPONSE)
        self.error_code = error_code
        self.bindings = bindings  # List of (oid, value_type, value) tuples
    
    def pack(self) -> bytes:
        """
        Pack this GetResponse into bytes for network transmission.
        
        TODO: Implement GetResponse packing (BUNDLE 1 REQUIREMENT)
        Returns: bytes - The complete response message
        
        CRITICAL DIFFERENCE: GetResponse has an EXTRA error_code field!
        This is how the agent tells the manager if something went wrong.
        
        ============================================================================
        MESSAGE FORMAT - NOTE THE EXTRA FIELD! (See README Section 3.3.3)
        ============================================================================
        ┌──────────────┬──────────────┬───────────┬────────────┬───────────────┐
        │ total_size   │ request_id   │ pdu_type  │ error_code │ payload       │
        │ (4 bytes)    │ (4 bytes)    │ (1 byte)  │ (1 byte)   │ (variable)    │
        └──────────────┴──────────────┴───────────┴────────────┴───────────────┘
                                                    ↑
                                            THIS EXTRA FIELD!
                                            
        Compare to GetRequest (no error_code):
        ┌──────────────┬──────────────┬───────────┬─────────────────────────┐
        │ total_size   │ request_id   │ pdu_type  │ payload                 │
        │ (4 bytes)    │ (4 bytes)    │ (1 byte)  │ (variable)              │
        └──────────────┴──────────────┴───────────┴─────────────────────────┘
        
        The payload contains OID-value bindings (like SetRequest):
        ┌────────────┬──────────────────────────────────────────────┐
        │ oid_count  │ Binding list (OID + type + value each)      │
        │ (1 byte)   │ (variable)                                   │
        └────────────┴──────────────────────────────────────────────┘
        
        ============================================================================
        IMPLEMENTATION STEPS
        ============================================================================
        
        Step 1: Build the payload with OID-value bindings
        --------------------------------------------------
        This is EXACTLY like SetRequest - include values with OIDs!
        
        payload = struct.pack('!B', len(self.bindings))  # Binding count
        # Debug: print(f"Response has {len(self.bindings)} bindings")
        
        for oid, value_type, value in self.bindings:
            # Encode the OID
            oid_bytes = encode_oid(oid)
            payload += struct.pack('!B', len(oid_bytes))
            payload += oid_bytes
            # Debug: print(f"  OID: {oid}")
            
            # Encode the value with its type
            value_bytes = encode_value(value, value_type)
            payload += struct.pack('!B', value_type)       # Type (1 byte)
            payload += struct.pack('!H', len(value_bytes)) # Length (2 bytes!)
            payload += value_bytes                         # The actual value
            # Debug: print(f"    Type: {value_type.name}, Value: {value}")
        
        Note: Even for errors, we might have empty bindings (count = 0)
        
        Step 2: Calculate total_size (includes extra error_code byte!)
        ---------------------------------------------------------------
        CRITICAL: GetResponse header is 10 bytes, not 9!
        
        total_size = 4 + 4 + 1 + 1 + len(payload)
                     ↑   ↑   ↑   ↑   ↑
           size field ──┘   │   │   │   │
                request_id ──┘   │   │   │
                     pdu_type ──┘   │   │
                    error_code ──┘   │  <-- EXTRA BYTE!
                             payload ──┘
        
        # Debug: print(f"Total size: 4+4+1+1+{len(payload)} = {total_size}")
        
        Step 3: Build the message WITH error_code
        ------------------------------------------
        message = b''
        message += struct.pack('!I', total_size)       # 4 bytes: size
        message += struct.pack('!I', self.request_id)  # 4 bytes: request ID
        message += struct.pack('!B', self.pdu_type)    # 1 byte: GET_RESPONSE
        message += struct.pack('!B', self.error_code)  # 1 byte: ERROR CODE!
        message += payload                             # Variable: bindings
        
        # Verify we got the size right
        assert len(message) == total_size
        
        ============================================================================
        ERROR CODE MEANINGS (ErrorCode enum)
        ============================================================================
        - SUCCESS (0): Everything worked, bindings contain requested values
        - NO_SUCH_OID (1): OID doesn't exist, bindings might be empty
        - BAD_VALUE (2): Invalid value in SET request
        - READ_ONLY (3): Tried to SET a read-only OID
        
        Example success response:
            error_code = ErrorCode.SUCCESS (0)
            bindings = [("1.3.6.1.2.1.1.5.0", ValueType.STRING, "router1")]
        
        Example error response:
            error_code = ErrorCode.NO_SUCH_OID (1)
            bindings = []  # Empty list for errors
        
        ============================================================================
        COMPLETE EXAMPLE
        ============================================================================
        GetResponse(request_id=1234, error_code=SUCCESS, 
                   bindings=[("1.3.6.1.2.1.1.5.0", ValueType.STRING, "test")])
        
        Step 1: Build payload
        - Binding count: 1 -> b'\\x01'
        - OID encoded: b'\\x01\\x03\\x06\\x01\\x02\\x01\\x01\\x05\\x00' (9 bytes)
        - OID length: 9 -> b'\\x09'
        - Value type: STRING (0x04) -> b'\\x04'
        - Value encoded: b'test' (4 bytes)
        - Value length: 4 -> b'\\x00\\x04' (2 bytes!)
        - Payload total: 1 + 1 + 9 + 1 + 2 + 4 = 18 bytes
        
        Step 2: Calculate size
        - total_size = 4 + 4 + 1 + 1 + 18 = 28 bytes
        
        Step 3: Final message (hex):
        00 00 00 1c  # Total size: 28 (0x1c)
        00 00 04 d2  # Request ID: 1234
        a1           # PDU type: GET_RESPONSE (0xa1)
        00           # Error code: SUCCESS (0)
        01           # Binding count: 1
        09           # OID length: 9
        01 03 06 01 02 01 01 05 00  # OID bytes
        04           # Value type: STRING
        00 04        # Value length: 4 (two bytes!)
        74 65 73 74  # "test" in ASCII
        
        ============================================================================
        COMMON MISTAKES
        ============================================================================
        
        1. Forgetting the error_code field
           Wrong: 9-byte header like GetRequest
           Right: 10-byte header with error_code
        
        2. Wrong total_size calculation
           Wrong: 4 + 4 + 1 + len(payload)  # Missing error_code byte!
           Right: 4 + 4 + 1 + 1 + len(payload)
        
        3. Not including bindings for successful responses
           Wrong: Only include payload for errors
           Right: Always include payload (might be empty for errors)
        
        4. Using 1-byte value length (like GetRequest has for OID length)
           Wrong: struct.pack('!B', len(value_bytes))
           Right: struct.pack('!H', len(value_bytes))  # 2 bytes!
        
        Test: python3 -m pytest tests/integration/test_protocol_structure.py::TestValueTypeEncoding::test_value_type_in_message -v
        
        See README Section 3.3.3 for complete GetResponse specification.
        """
        # TODO: Step 1 - Build payload with bindings (like SetRequest)
        # TODO: Step 2 - Calculate total_size (10 bytes header + payload)
        # TODO: Step 3 - Pack header WITH error_code field, then add payload
        # Remember: error_code comes AFTER pdu_type, BEFORE payload!
        raise NotImplementedError("Implement GetResponse.pack()")
    
    @classmethod
    def unpack(cls, data: bytes) -> 'GetResponse':
        """
        Create GetResponse from received network bytes.
        
        TODO: Implement GetResponse unpacking (BUNDLE 2 REQUIREMENT)
        Returns: GetResponse - A new GetResponse object with the unpacked data
        
        Remember to extract the error_code field at byte 9!
        
        Structure:
        - data[4:8] = request_id
        - data[8] = pdu_type (already verified)
        - data[9] = error_code  ← Don't forget this!
        - data[10:] = payload (bindings)
        
        The payload parsing is identical to SetRequest.
        
        Test verification: All tests pass when complete implementation works
        Run all: python3 -m pytest tests/integration/test_protocol_structure.py -v
        """
        # TODO: Extract request_id and error_code
        # TODO: Parse bindings from payload (starts at byte 10!)
        # TODO: Return GetResponse with error_code and bindings
        raise NotImplementedError("Implement GetResponse.unpack()")

def unpack_message(data: bytes) -> SNMPMessage:
    """Unpack any SNMP message based on PDU type"""
    if len(data) < MIN_MESSAGE_SIZE:
        logger.error("Message too short: %d bytes, minimum %d", len(data), MIN_MESSAGE_SIZE)
        raise ValueError(f"Message too short: {len(data)} bytes, minimum {MIN_MESSAGE_SIZE}")
    
    pdu_type = struct.unpack('!B', data[PDU_TYPE_OFFSET:PDU_TYPE_OFFSET+PDU_TYPE_LENGTH])[0]
    logger.debug("Unpacking message with PDU type 0x%02X", pdu_type)
    
    if pdu_type == PDUType.GET_REQUEST:
        return GetRequest.unpack(data)
    elif pdu_type == PDUType.SET_REQUEST:
        return SetRequest.unpack(data)
    elif pdu_type == PDUType.GET_RESPONSE:
        return GetResponse.unpack(data)
    else:
        logger.error("Unknown PDU type: 0x%02X", pdu_type)
        raise ValueError(f"Unknown PDU type: {pdu_type}")

def receive_complete_message(sock) -> bytes:
    """
    Receive a complete SNMP message from a socket, handling partial data.
    
    TODO: Implement proper network buffering (BUNDLE 1 REQUIREMENT - CRITICAL!)
    Returns: bytes - The complete SNMP message
    
    THIS IS THE MOST IMPORTANT FUNCTION IN THE ENTIRE PROJECT!
    Without correct buffering, nothing else will work reliably.
    
    ============================================================================
    THE FUNDAMENTAL PROBLEM OF NETWORK PROGRAMMING
    ============================================================================
    
    When you call sock.recv(1000), the network doesn't guarantee you get 1000 bytes!
    You might get:
    - 1000 bytes (complete data - rare!)
    - 500 bytes (partial data - common!)
    - 50 bytes (very partial - happens under load)
    - 0 bytes (connection closed)
    
    Real scenario that WILL happen during testing:
    1. Server sends a 100-byte message
    2. Network delivers it in 3 chunks: 40 bytes, 35 bytes, 25 bytes
    3. Your code must reassemble these into the complete 100-byte message
    
    If you just call recv() once, you'll get incomplete data and everything breaks!
    
    ============================================================================
    HOW OUR PROTOCOL SOLVES THIS (See README Section 6 - Mermaid Diagrams)
    ============================================================================
    
    Every SNMP message starts with its total size:
    ┌──────────────┬─────────────────────────────────────┐
    │ total_size   │ rest of message                     │
    │ (4 bytes)    │ (total_size - 4 bytes)             │
    └──────────────┴─────────────────────────────────────┘
    
    This size field tells us EXACTLY how many bytes to expect!
    
    ============================================================================
    THE TWO-PHASE ALGORITHM (Follow README Section 6 Flowchart)
    ============================================================================
    
    PHASE 1: Read the size field (first 4 bytes)
    ----------------------------------------------
    Why separate phase? We can't know how much to read until we know the size!
    
    received = b''  # Start with empty buffer
    
    # Keep reading until we have exactly 4 bytes
    while len(received) < 4:
        # Calculate how many more bytes we need
        bytes_needed = 4 - len(received)
        # Debug: print(f"Phase 1: Need {bytes_needed} more bytes for size field")
        
        # Try to receive the bytes we need
        chunk = sock.recv(bytes_needed)
        
        # CRITICAL: Check if connection closed
        if not chunk:  # recv returns b'' when connection closes
            # Debug: print("Connection closed while reading size!")
            raise ConnectionError("Connection closed while reading size")
        
        # Add the chunk to our buffer
        received += chunk
        # Debug: print(f"Phase 1: Got {len(chunk)} bytes, total: {len(received)}/4")
    
    # Now we have exactly 4 bytes - decode the size
    message_size = struct.unpack('!I', received[0:4])[0]
    # Debug: print(f"Message size decoded: {message_size} bytes")
    
    # SECURITY: Validate the size to prevent memory exhaustion attacks
    if message_size < MIN_MESSAGE_SIZE:
        raise ValueError(f"Message too small: {message_size} bytes (minimum: {MIN_MESSAGE_SIZE})")
    if message_size > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message too large: {message_size} bytes (maximum: {MAX_MESSAGE_SIZE})")
    
    PHASE 2: Read the rest of the message
    --------------------------------------
    Now we know the total size, read until we have exactly that many bytes.
    
    # Continue reading until we have the complete message
    while len(received) < message_size:
        # Calculate how many bytes are still missing
        remaining = message_size - len(received)
        # Debug: print(f"Phase 2: Need {remaining} more bytes")
        
        # CRITICAL: Don't read more than we need (might get next message!)
        # Also don't request huge amounts at once (be nice to the network)
        chunk_size = min(remaining, MAX_RECV_BUFFER)
        
        # Try to receive up to chunk_size bytes
        chunk = sock.recv(chunk_size)
        
        # Check if connection closed
        if not chunk:
            # Debug: print(f"Connection closed! Had {len(received)}/{message_size} bytes")
            raise ConnectionError(f"Connection closed while reading message (got {len(received)}/{message_size} bytes)")
        
        # Add to our buffer
        received += chunk
        # Debug: print(f"Phase 2: Got {len(chunk)} bytes, total: {len(received)}/{message_size}")
    
    # Debug: print(f"Complete message received: {len(received)} bytes")
    # Debug: print(f"Message hex: {received.hex()}")
    
    return received  # Exactly message_size bytes!
    
    ============================================================================
    COMPLETE IMPLEMENTATION TEMPLATE
    ============================================================================
    def receive_complete_message(sock) -> bytes:
        received = b''
        
        # Phase 1: Get size (4 bytes)
        while len(received) < 4:
            chunk = sock.recv(4 - len(received))
            if not chunk:
                raise ConnectionError("Connection closed while reading size")
            received += chunk
        
        # Decode and validate size
        message_size = struct.unpack('!I', received[0:4])[0]
        if message_size < MIN_MESSAGE_SIZE or message_size > MAX_MESSAGE_SIZE:
            raise ValueError(f"Invalid message size: {message_size}")
        
        # Phase 2: Get remaining bytes
        while len(received) < message_size:
            remaining = message_size - len(received)
            chunk = sock.recv(min(remaining, MAX_RECV_BUFFER))
            if not chunk:
                raise ConnectionError("Connection closed while reading message")
            received += chunk
        
        return received
    
    ============================================================================
    CRITICAL MISTAKES TO AVOID
    ============================================================================
    
    1. Reading too much (getting part of next message)
       Wrong: sock.recv(4096)  # Might include next message!
       Right: sock.recv(min(remaining, 4096))  # Never exceed what we need
    
    2. Not checking for connection closure
       Wrong: received += sock.recv(1000)  # What if it returns b''?
       Right: chunk = sock.recv(1000)
              if not chunk: raise ConnectionError(...)
    
    3. Infinite loop on closed connection
       Wrong: while len(received) < size: received += sock.recv(100)
       Right: Add the if not chunk check!
    
    4. Wrong size decoding
       Wrong: message_size = int.from_bytes(received[0:4], 'little')
       Right: message_size = struct.unpack('!I', received[0:4])[0]
    
    ============================================================================
    DEBUGGING STRATEGY
    ============================================================================
    
    1. Add prints to track progress:
       print(f"Phase 1: {len(received)}/4 bytes")
       print(f"Phase 2: {len(received)}/{message_size} bytes")
    
    2. Print the size field when decoded:
       print(f"Size field: {received[0:4].hex()} = {message_size} bytes")
    
    3. Verify final message:
       print(f"Complete: {len(received)} bytes, hex: {received.hex()}")
    
    4. Common error patterns:
       - Hangs forever: Not checking for closed connection
       - "struct.error": Size field not complete (less than 4 bytes)
       - Wrong message content: Read too much (into next message)
    
    ============================================================================
    WHY THIS MATTERS IN INDUSTRY
    ============================================================================
    
    This EXACT pattern is used in:
    - HTTP/2 and HTTP/3 (frame handling)
    - WebSocket (message framing)
    - Database protocols (MySQL, PostgreSQL packet handling)
    - Video streaming (reassembling video frames)
    - Gaming (receiving game state updates)
    - IoT protocols (MQTT, CoAP)
    
    Master this pattern - you'll use it your entire career!
    
    ============================================================================
    TESTING YOUR IMPLEMENTATION
    ============================================================================
    
    The test suite simulates real network conditions:
    - Partial sends (data arrives in chunks)
    - Multiple messages back-to-back
    - Large messages that span many chunks
    - Connection failures mid-message
    
    Run tests: python3 -m pytest tests/integration/test_message_buffering.py -v
    
    Key tests:
    - test_single_small_message - Basic functionality
    - test_partial_sends - Data arrives in chunks
    - test_consecutive_messages_no_delay - Multiple messages
    - test_large_string_value - Big messages
    
    See README Section 6 for visual Mermaid diagrams showing:
    - The two-phase reading process
    - How buffering handles partial data
    - The complete message flow
    """
    # TODO: Initialize empty buffer: received = b''
    # TODO: Phase 1 - Loop until you have 4 bytes for size
    # TODO: Decode size with struct.unpack('!I', ...) and validate
    # TODO: Phase 2 - Loop until you have message_size total bytes
    # TODO: Always check if chunk is empty (connection closed)
    # TODO: Return the complete message
    
    # Debugging: Add print statements to track your progress!
    raise NotImplementedError("Implement receive_complete_message - Critical for all network operations!")