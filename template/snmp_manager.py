#!/usr/bin/env python3
"""
SNMP Manager Implementation
The client that sends requests to SNMP agents

This file teaches CLIENT-SIDE network programming patterns:
1. Creating outbound connections (client connects TO server)
2. Managing request-response correlation with IDs
3. Handling network timeouts to avoid hanging
4. Proper socket lifecycle management
5. Error recovery strategies

Key Concept: Client vs Server Socket Lifecycle
- CLIENTS: Create socket → Connect → Send → Receive → Close
- SERVERS: Create socket → Bind → Listen → Accept → (handle clients)

IMPORTANT: Command-line parsing and display formatting are PROVIDED
"""

import socket
import sys
import struct
import random
import time
from typing import List, Tuple, Optional, Any

# Import protocol components (you'll implement these in snmp_protocol.py)
from snmp_protocol import (
    PDUType, ValueType, ErrorCode,
    GetRequest, SetRequest, GetResponse,
    receive_complete_message, unpack_message
)

# ============================================================================
# CONSTANTS (PROVIDED - DO NOT MODIFY)
# ============================================================================

DEFAULT_TIMEOUT = 10.0  # Socket timeout in seconds
TIMETICKS_PER_SECOND = 100  # SNMP timeticks are 1/100 second

# Why timeouts matter for clients:
# Without a timeout, your client could wait FOREVER for a response that
# may never come (server down, network issue, firewall blocking).
# This is called "hanging" and makes programs appear frozen.
# Always set timeouts on client sockets!

# ============================================================================
# PROVIDED: Display formatting functions
# ============================================================================

def format_timeticks(ticks: int) -> str:
    """
    PROVIDED: Convert timeticks to human readable format
    
    This handles the display of uptime values in a user-friendly way
    """
    total_seconds = ticks / TIMETICKS_PER_SECOND
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days} days")
    if hours > 0:
        parts.append(f"{hours} hours")
    if minutes > 0:
        parts.append(f"{minutes} minutes")
    if seconds > 0 or len(parts) == 0:
        parts.append(f"{seconds:.2f} seconds")
    
    return f"{ticks} ({', '.join(parts)})"

def format_value(value_type: ValueType, value: Any) -> str:
    """
    PROVIDED: Format any value for display based on its type
    """
    if value_type == ValueType.TIMETICKS:
        return format_timeticks(value)
    elif value_type == ValueType.COUNTER:
        # Add thousands separators for readability
        return f"{value:,}"
    else:
        return str(value)

def format_error(error_code: ErrorCode) -> str:
    """
    PROVIDED: Convert error codes to human-readable messages
    """
    error_messages = {
        ErrorCode.NO_SUCH_OID: "No such OID exists",
        ErrorCode.BAD_VALUE: "Bad value for OID type",
        ErrorCode.READ_ONLY: "OID is read-only"
    }
    return error_messages.get(error_code, f"Unknown error ({error_code})")

# ============================================================================
# SNMP MANAGER CLASS
# ============================================================================

class SNMPManager:
    """
    SNMP Manager for sending requests to agents
    
    This class demonstrates client-side network programming where we:
    - Initiate connections (we're the "active opener")
    - Send requests and wait for responses
    - Handle correlation between requests and responses
    """
    
    def __init__(self):
        # Generate random starting request ID
        # Why random? Helps avoid ID collisions if manager restarts quickly
        self.request_id = random.randint(1, 10000)
    
    def _get_next_request_id(self) -> int:
        """
        PROVIDED: Generate unique request IDs for matching responses
        
        Request IDs are like tracking numbers for packages:
        - You send request #1234
        - Server sends back response #1234
        - You know they match!
        
        This is critical when:
        - Multiple clients talk to same server
        - Responses arrive out of order
        - You need to detect lost/duplicate messages
        
        Real-world analogy: Like order numbers at a restaurant
        """
        self.request_id += 1
        return self.request_id
    
    # ========================================================================
    # STUDENT IMPLEMENTATION: Core operations
    # ========================================================================
    
    def get(self, host: str, port: int, oids: List[str]) -> None:
        """
        Send GetRequest and display response
        This demonstrates a complete client-side request-response cycle.
        
        CLIENT SOCKET LIFECYCLE in this method:
        1. CREATE: socket.socket() - Birth of connection
        2. CONFIGURE: settimeout() - Prevent eternal waiting
        3. CONNECT: connect() - Establish path to server
        4. SEND: send() - Transmit our request
        5. RECEIVE: recv() - Wait for response
        6. CLOSE: close() - Clean shutdown
        
        IMPLEMENTATION STEPS:
        1. Create a TCP socket (socket.AF_INET, socket.SOCK_STREAM)
           - AF_INET = IPv4, SOCK_STREAM = TCP (reliable, ordered)
        
        2. Set timeout IMMEDIATELY after creation
           - sock.settimeout(DEFAULT_TIMEOUT)
           - Without this, recv() could block forever!
        
        3. Connect to the agent at (host, port)
           - This is where client differs from server
           - Client CONNECTS TO a specific address
           - Server BINDS and LISTENS on an address
        
        4. Generate a unique request ID
           - request_id = self._get_next_request_id()
           - This ID must match in the response
        
        5. Create GetRequest object
           - GetRequest(request_id, oids)
           - This is your protocol message
        
        6. Pack request to bytes and send
           - data = request.pack()  # Convert to bytes
           - sock.send(data)  # Transmit over network
        
        7. Receive complete response
           - response_data = receive_complete_message(sock)
           - This handles the size prefix for you
        
        8. Unpack and validate response
           - response = unpack_message(response_data)
           - Check: Is it a GetResponse?
           - Check: Does request_id match?
           - If not, something went wrong!
        
        9. Display results based on response type
           - Success: Print each OID and its value
           - Error: Print error message
        
        DISPLAY FORMAT:
        Success (for each OID in response):
            1.3.6.1.2.1.1.1.0 = Linux server 5.4.0
            1.3.6.1.2.1.1.5.0 = router-42
        
        Error:
            Error: No such OID exists
        
        COMMON MISTAKES TO AVOID:
        - Forgetting to set timeout (program hangs)
        - Not checking request ID match (wrong response)
        - Not handling connection refused (server not running)
        - Forgetting to close socket (resource leak)
        
        DEBUGGING STRATEGIES:
        1. Connection failures:
           - Is the server running? (check with netstat)
           - Correct host and port?
           - Firewall blocking connection?
        
        2. No response:
           - Did you send the complete message?
           - Is the request properly formatted?
           - Add print statements to see what was sent
        
        3. Wrong response:
           - Print request_id sent vs received
           - Check PDU type of response
        
        Test: python3 -m pytest tests/integration/test_get_operations.py -v
        """
        sock = None
        try:
            # TODO: Follow the lifecycle steps above
            # Remember: Client creates, connects, communicates, closes
            
            raise NotImplementedError("Implement get operation")
            
        except socket.timeout:
            # Specific handling for timeout
            print(f"Error: Request timed out after {DEFAULT_TIMEOUT} seconds")
        except ConnectionRefusedError:
            # Server not running or wrong port
            print(f"Error: Cannot connect to {host}:{port} - is the agent running?")
        except Exception as e:
            # Catch-all for other errors
            print(f"Error: {e}")
        finally:
            # CRITICAL: Always close the socket, even if errors occur
            # This prevents resource leaks
            if sock:
                sock.close()
    
    def set(self, host: str, port: int, oid: str, value_type: str, value: str) -> None:
        """
        Send SetRequest and display response
        Similar to get() but demonstrates sending data TO the server.
        
        SET vs GET - Key Differences:
        - GET: Retrieves information (read operation)
        - SET: Modifies information (write operation)
        - SET: May fail with READ_ONLY error
        - SET: Requires type conversion of input values
        
        IMPLEMENTATION STEPS:
        1. Parse and validate value type (PROVIDED)
           - Maps string like "integer" to ValueType.INTEGER
        
        2. Convert value string to correct Python type
           - "integer" -> int(value)
           - "string" -> value (no conversion)
           - "counter" -> int(value) with validation >= 0
           - "timeticks" -> int(value) with validation >= 0
           
           Handle conversion errors gracefully!
        
        3. Follow same socket lifecycle as get():
           - Create TCP socket
           - Set timeout (CRITICAL!)
           - Connect to (host, port)
        
        4. Create SetRequest with converted value
           - request_id = self._get_next_request_id()
           - SetRequest(request_id, oid, vtype, converted_value)
        
        5. Send and receive (same pattern as get)
           - Pack, send, receive, unpack
           - Verify response type and ID match
        
        6. Display based on response
           - Success: Show what was set
           - Error: Explain why it failed
        
        DISPLAY FORMAT:
        Success:
            Set operation successful:
            1.3.6.1.2.1.1.5.0 = new-router-name
        
        Error (various types):
            Error: No such OID exists
            Error: OID is read-only
            Error: Bad value for OID type
        
        VALUE CONVERSION EXAMPLES:
        Input: "integer" "42" -> Python: 42 (int)
        Input: "string" "hello" -> Python: "hello" (str)
        Input: "counter" "1000" -> Python: 1000 (int, must be >= 0)
        Input: "timeticks" "500" -> Python: 500 (int, must be >= 0)
        
        COMMON SET FAILURES:
        - READ_ONLY: Trying to change system uptime
        - BAD_VALUE: Wrong type for OID (string where int expected)
        - NO_SUCH_OID: OID doesn't exist in MIB
        
        DEBUGGING TIP:
        If set fails, try get first to see current value and type!
        
        Test: python3 -m pytest tests/integration/test_set_operations.py -v
        """
        # PROVIDED: Parse value type
        type_map = {
            'integer': ValueType.INTEGER,
            'string': ValueType.STRING,
            'counter': ValueType.COUNTER,
            'timeticks': ValueType.TIMETICKS
        }
        
        if value_type.lower() not in type_map:
            print(f"Error: Invalid value type '{value_type}'. Must be one of: {', '.join(type_map.keys())}")
            return
        
        vtype = type_map[value_type.lower()]
        
        # TODO: Convert value to appropriate type
        # Hint: Use try/except for int() conversion
        # Hint: Validate counter/timeticks >= 0
        
        # TODO: Same socket pattern as get()
        # Create → Configure → Connect → Send → Receive → Close
        
        raise NotImplementedError("Implement set operation")
    
    # ========================================================================
    # STUDENT IMPLEMENTATION: Helper methods
    # ========================================================================
    
    def _connect_to_agent(self, host: str, port: int) -> socket.socket:
        """
        Create a socket and connect to the SNMP agent
        This helper demonstrates proper client connection setup.
        
        WHY A HELPER METHOD?
        - Both get() and set() need the same connection logic
        - DRY principle: Don't Repeat Yourself
        - Single place to handle connection errors
        
        CLIENT CONNECTION PROCESS:
        1. Create socket - Your endpoint for communication
           sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
           - AF_INET: Use IPv4 addressing
           - SOCK_STREAM: Use TCP (reliable, ordered delivery)
        
        2. Configure socket - Set behavior BEFORE connecting
           sock.settimeout(DEFAULT_TIMEOUT)
           - Must be done BEFORE connect()
           - Affects both connect() and recv() operations
           - Without this, operations could block forever
        
        3. Connect to server - Establish the communication channel
           sock.connect((host, port))
           - Note the double parentheses: (host, port) is a tuple
           - This is the "active open" in TCP
           - May raise ConnectionRefusedError if server not listening
           - May raise socket.timeout if server doesn't respond
        
        4. Return connected socket - Ready for send/recv
           return sock
        
        CONNECTION FAILURE SCENARIOS:
        
        1. ConnectionRefusedError:
           - Server not running
           - Wrong port number
           - Server crashed
           Solution: Check if agent is running
        
        2. socket.timeout:
           - Network issues
           - Firewall blocking
           - Server overloaded
           Solution: Check network connectivity
        
        3. socket.gaierror:
           - Invalid hostname
           - DNS resolution failed
           Solution: Check hostname spelling
        
        4. OSError (various):
           - No route to host
           - Network unreachable
           Solution: Check network configuration
        
        DEBUGGING CONNECTION ISSUES:
        
        Step 1: Is the server running?
           # On Linux/Mac:
           netstat -an | grep LISTEN | grep <port>
           # or
           lsof -i :<port>
        
        Step 2: Can you reach the host?
           ping <hostname>
        
        Step 3: Is the port open?
           telnet <host> <port>
           # or
           nc -zv <host> <port>
        
        Step 4: Add debug prints
           print(f"Connecting to {host}:{port}...")
           sock.connect((host, port))
           print("Connected successfully!")
        
        COMMON MISTAKES:
        - Forgetting timeout (hangs on connection attempt)
        - Wrong tuple format: connect(host, port) vs connect((host, port))
        - Not handling connection errors
        - Reusing closed sockets
        
        Real-world tip: Production code often retries connections
        with exponential backoff (1s, 2s, 4s, 8s...)
        """
        # TODO: Implement the 4 steps above
        # Remember to handle errors appropriately
        
        raise NotImplementedError("Implement _connect_to_agent")

# ============================================================================
# PROVIDED: Command-line interface
# ============================================================================

def print_usage():
    """PROVIDED: Print usage information"""
    print("Usage:")
    print("  snmp_manager.py get <host:port> <oid> [<oid> ...]")
    print("  snmp_manager.py set <host:port> <oid> <type> <value>")
    print("  snmp_manager.py bulk <host:port> <start_oid> <max_repetitions>")
    print()
    print("Examples:")
    print("  snmp_manager.py get localhost:1161 1.3.6.1.2.1.1.1.0")
    print("  snmp_manager.py get localhost:1161 1.3.6.1.2.1.1.1.0 1.3.6.1.2.1.1.5.0")
    print("  snmp_manager.py set localhost:1161 1.3.6.1.2.1.1.5.0 string 'new-router-name'")
    print("  snmp_manager.py bulk localhost:1161 1.3.6.1.2.1.2.2.1 50")
    print()
    print("Types: integer, string, counter, timeticks")

def parse_host_port(host_port: str) -> Tuple[str, int]:
    """PROVIDED: Parse host:port string"""
    parts = host_port.split(':')
    if len(parts) != 2:
        raise ValueError("Invalid host:port format. Use 'hostname:port' or 'ip:port'")
    
    host = parts[0]
    try:
        port = int(parts[1])
        if not 1 <= port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
    except ValueError:
        raise ValueError(f"Invalid port number: {parts[1]}")
    
    return host, port

def main():
    """
    PROVIDED: Main entry point with command-line parsing
    
    This handles all the command-line argument parsing so students
    can focus on the networking implementation.
    """
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        host, port = parse_host_port(sys.argv[2])
    except ValueError as e:
        print(f"Error: {e}")
        print_usage()
        sys.exit(1)
    
    manager = SNMPManager()
    
    if command == 'get':
        if len(sys.argv) < 4:
            print("Error: No OIDs specified")
            print_usage()
            sys.exit(1)
        
        oids = sys.argv[3:]
        manager.get(host, port, oids)
        
    elif command == 'set':
        if len(sys.argv) != 6:
            print("Error: Set requires exactly 4 arguments: host:port oid type value")
            print_usage()
            sys.exit(1)
        
        oid = sys.argv[3]
        value_type = sys.argv[4]
        value = sys.argv[5]
        manager.set(host, port, oid, value_type, value)
        
    else:
        print(f"Error: Unknown command '{command}'")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()