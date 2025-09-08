#!/usr/bin/env python3
"""
SNMP Agent Implementation
The server that listens for SNMP requests and responds with data

This file teaches you SERVER-SIDE network programming:
1. Socket server setup - How to create a server that listens for connections
2. Client connection handling - Managing multiple client connections
3. Request/response protocols - Processing messages and sending replies
4. Error handling - Dealing with network errors gracefully

Industry relevance: Every web server, database server, game server, and
microservice follows these same patterns. Understanding server socket
programming is essential for backend development, DevOps, and system design.

Key concepts you'll master:
- The socket lifecycle (create → bind → listen → accept → close)
- Why we need SO_REUSEADDR (the TIME_WAIT problem)
- Connection-oriented vs connectionless protocols
- Blocking vs non-blocking I/O
"""

import socket
import sys
import struct
import time
import signal
from typing import Dict, Any, List, Tuple, Optional

# Import protocol components (you'll implement these in snmp_protocol.py)
from snmp_protocol import (
    PDUType, ValueType, ErrorCode,
    GetRequest, SetRequest, GetResponse,
    unpack_message, receive_complete_message,
    encode_oid, decode_oid
)

# ============================================================================
# CONSTANTS (PROVIDED - DO NOT MODIFY)
# ============================================================================

DEFAULT_PORT = 1161  # We use 1161 instead of standard 161 (no root required)
LISTEN_BACKLOG = 5   # Maximum pending connections in the accept queue
TIMEOUT_SECONDS = 10.0  # Socket timeout to prevent hanging
TIMETICKS_PER_SECOND = 100  # SNMP timeticks are 1/100 second

# ============================================================================
# MIB DATABASE (PROVIDED - DO NOT MODIFY)
# ============================================================================

# Import the MIB database (Management Information Base)
# This contains all the data our agent can serve
from mib_database import MIB_DATABASE, MIB_PERMISSIONS

# ============================================================================
# SNMP AGENT CLASS
# ============================================================================

class SNMPAgent:
    """SNMP Agent that responds to management requests"""
    
    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.mib = dict(MIB_DATABASE)  # Create a mutable copy
        self.start_time = time.time()  # Track when agent started for uptime
        self.server_socket = None
        self.running = True
    
    # ========================================================================
    # STUDENT IMPLEMENTATION: Socket setup and server loop
    # ========================================================================
    
    def start(self):
        """
        Start the SNMP agent server and listen for connections.
        
        TODO: Implement the server socket lifecycle (BUNDLE 1 REQUIREMENT)
        Returns: None - Runs forever until interrupted
        
        ============================================================================
        WHY SERVERS NEED SPECIAL SOCKET SETUP (THE BIG PICTURE)
        ============================================================================
        
        Imagine you're running a coffee shop (your server):
        - You need a fixed address (bind to port) so customers can find you
        - You need to be "open for business" (listening state)
        - You need a waiting area for customers (listen backlog)
        - Each customer gets personal service (individual client socket)
        - The front door stays open for new customers (server socket stays listening)
        
        This is EXACTLY how web servers (Apache, Nginx), databases (PostgreSQL, 
        MongoDB), game servers (Minecraft, CS:GO), and every network service works!
        
        ============================================================================
        THE SERVER SOCKET LIFECYCLE - WHY EACH STEP MATTERS
        ============================================================================
        
        1. CREATE: socket.socket(AF_INET, SOCK_STREAM)
           WHY: Creates the communication endpoint
           - AF_INET = IPv4 addressing (like 192.168.1.1)
           - SOCK_STREAM = TCP (reliable, ordered delivery)
           
           Industry insight: TCP guarantees your data arrives intact and in order.
           That's why HTTP, SSH, and databases use it. UDP (SOCK_DGRAM) is for
           speed over reliability (gaming, video streaming).
        
        2. CONFIGURE: setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
           WHY: Prevents the dreaded "Address already in use" error
           
           The TIME_WAIT problem:
           - When a TCP connection closes, the OS keeps the port reserved for ~60s
           - This catches "late-arriving" packets from the old connection
           - But it makes development painful - you can't restart your server!
           
           SO_REUSEADDR tells the OS: "I know what I'm doing, let me reuse it"
           Every production server sets this. Without it, a server crash means
           waiting 60+ seconds before you can restart. Imagine if Google had to
           wait a minute to restart a crashed server!
        
        3. BIND: bind(('', self.port))
           WHY: Claims a specific port number as "yours"
           
           Think of ports like apartment numbers in a building:
           - The building is the IP address (the computer)
           - The apartment number is the port (1-65535)
           - bind() puts your name on the mailbox
           
           bind(('', port)) vs bind(('localhost', port)):
           - '' = Accept connections from anywhere (internet-facing)
           - 'localhost' = Only local connections (security/testing)
           
           Common ports: HTTP=80, HTTPS=443, SSH=22, PostgreSQL=5432
           We use 1161 because ports <1024 need root/admin privileges.
        
        4. LISTEN: listen(LISTEN_BACKLOG)
           WHY: Switches socket from active (client) to passive (server) mode
           
           The backlog is your "waiting room":
           - While you're serving one customer, others queue up
           - LISTEN_BACKLOG=5 means up to 5 can wait
           - If a 6th arrives, they get "connection refused"
           
           Real-world: High-traffic servers use larger backlogs (128-512).
           During Black Friday sales, e-commerce sites increase backlog to
           handle traffic spikes.
        
        5. ACCEPT LOOP: while True: accept()
           WHY: This is the heart of the server - waiting for clients
           
           accept() is special - it creates a NEW socket:
           - Server socket: The "front door" - always listening
           - Client socket: Private "meeting room" for that client
           
           This is why servers can handle multiple clients:
           - Server socket stays open, accepting new connections
           - Each client gets their own socket for communication
           
           The TCP Three-Way Handshake happens here:
           Client: "SYN" (Can we talk?)
           Server: "SYN-ACK" (Yes, let's talk!)
           Client: "ACK" (Great, here's my first message)
           
           accept() blocks (waits) until this handshake completes.
        
        ============================================================================
        IMPLEMENTATION WITH EXPLANATIONS
        ============================================================================
        
        try:
            # Step 1: Create the socket - your server's "ears"
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Step 2: Configure - prevent "Address already in use" pain
            # SOL_SOCKET = Socket-level options, SO_REUSEADDR = the reuse flag
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Step 3: Bind - claim your address (like getting a phone number)
            # '' means 0.0.0.0 - accept from any network interface
            self.server_socket.bind(('', self.port))
            
            # Step 4: Listen - open for business!
            # Kernel will queue up to LISTEN_BACKLOG pending connections
            self.server_socket.listen(LISTEN_BACKLOG)
            
            print(f"SNMP Agent listening on port {self.port}...")
            
            # Step 5: The main accept loop - the server's "heartbeat"
            while self.running:
                try:
                    # This blocks until a client connects
                    # Returns: (new_socket_for_this_client, (client_ip, client_port))
                    client_socket, client_address = self.server_socket.accept()
                    print(f"Connection from {client_address[0]}:{client_address[1]}")
                    
                    # Handle this specific client (might take a while)
                    # Server socket remains available for other connections!
                    self._handle_client(client_socket, client_address)
                    
                except KeyboardInterrupt:
                    # Ctrl+C pressed - graceful shutdown
                    print("\nShutting down...")
                    self.running = False
                    break
                    
        finally:
            # CRITICAL: Always clean up! Leaked sockets = resource exhaustion
            if self.server_socket:
                self.server_socket.close()
        
        ============================================================================
        DEBUGGING GUIDE - WHEN THINGS GO WRONG
        ============================================================================
        
        Problem: "Address already in use" (EADDRINUSE)
        Diagnosis:
        1. Check what's using the port:
           Linux/Mac: lsof -i :1161 or netstat -an | grep 1161
           Windows: netstat -an | findstr 1161
        
        2. If it's a stuck process:
           Linux/Mac: kill -9 <PID>
           Windows: taskkill /F /PID <PID>
        
        3. If you forgot SO_REUSEADDR:
           Add it! This is why every server tutorial mentions it.
        
        Problem: "Connection refused" when client connects
        Causes:
        - Server not running (did start() get called?)
        - Server on different port than client expects
        - Firewall blocking the connection
        - Server bound to 'localhost' but client connecting from network
        
        Problem: Server "hangs" and doesn't accept connections
        Causes:
        - Forgot to call listen() - socket isn't in listening state
        - Backlog full - too many pending connections
        - Blocking in _handle_client() - not returning to accept loop
        
        Debug strategy:
        1. Add print statements:
           print("About to create socket...")
           print("Socket created, about to bind...")
           print("Bound successfully, about to listen...")
           
        2. Test with telnet:
           telnet localhost 1161
           If it connects, server socket is working!
        
        3. Check from another terminal:
           ps aux | grep python  # Is your server running?
           netstat -an | grep LISTEN | grep 1161  # Is it listening?
        
        ============================================================================
        PROFESSIONAL PATTERNS YOU'RE LEARNING
        ============================================================================
        
        1. Resource Management (try/finally)
           - Always release resources, even on errors
           - Prevents resource leaks that crash servers
        
        2. Graceful Shutdown (KeyboardInterrupt handling)
           - Clean termination, not abrupt exit
           - Lets connections close properly
        
        3. Separation of Concerns
           - Server socket: accepts connections
           - Client handler: processes requests
           - Clean architecture, easy to maintain
        
        4. Error Isolation
           - One bad client doesn't crash the server
           - Each client handled independently
        
        This is the same pattern used by:
        - Web servers (Apache, Nginx)
        - Database servers (PostgreSQL, MySQL)
        - Game servers (Minecraft, Fortnite)
        - Your future microservices!
        
        Test verification: All agent tests require this to work!
        Basic test: python3 -m pytest tests/integration/test_get_operations.py::TestGetOperations::test_single_oid_get -v
        """
        # TODO: Create server socket (AF_INET, SOCK_STREAM)
        # TODO: Set SO_REUSEADDR option (CRITICAL!)
        # TODO: Bind to all interfaces on self.port
        # TODO: Start listening with LISTEN_BACKLOG
        # TODO: Print "SNMP Agent listening on port..."
        # TODO: Main loop: accept connections and handle them
        # TODO: Handle KeyboardInterrupt for clean shutdown
        # TODO: Always close server socket in finally block
        
        raise NotImplementedError("Implement start() - server socket setup")
    
    # ========================================================================
    # STUDENT IMPLEMENTATION: Client connection handling
    # ========================================================================
    
    def _handle_client(self, client_socket: socket.socket, client_address: Tuple[str, int]):
        """
        Handle a client connection - process requests and send responses.
        
        TODO: Implement client connection handling (BUNDLE 1 REQUIREMENT)
        Returns: None - Handles client until connection ends
        
        ============================================================================
        THE CLIENT HANDLER - YOUR SERVER'S CONVERSATION WITH EACH CLIENT
        ============================================================================
        
        This method is like a phone call with one customer:
        - The main server "receptionist" (accept loop) transferred them to you
        - You handle ALL their requests until they hang up
        - Meanwhile, the receptionist can answer other calls
        
        This is the "thread" of execution for one client (even though we're
        single-threaded for simplicity). Production servers would spawn a
        thread or process here.
        
        ============================================================================
        WHY TIMEOUTS ARE CRITICAL (PREVENTING ZOMBIE CONNECTIONS)
        ============================================================================
        
        Without timeouts, your server can be DOSed (Denial of Service):
        1. Attacker connects but never sends data
        2. Your server waits forever in recv()
        3. Repeat until all connections exhausted
        4. Legitimate users can't connect!
        
        settimeout(10) means: "If nothing happens for 10 seconds, give up"
        
        Real-world: HTTP servers timeout after 30-300 seconds. Database
        connections timeout after 5-30 seconds. Game servers: 1-5 seconds.
        
        ============================================================================
        THE REQUEST/RESPONSE LOOP - WHY PERSISTENT CONNECTIONS
        ============================================================================
        
        Old way (HTTP/1.0, one request per connection):
        1. Connect (3-way handshake) - 1 RTT (Round Trip Time)
        2. Send request - 0.5 RTT
        3. Get response - 0.5 RTT  
        4. Close connection - 1 RTT
        Total: 3 RTTs per request!
        
        Our way (persistent connections, like HTTP/1.1 Keep-Alive):
        1. Connect once - 1 RTT
        2. Request/Response #1 - 1 RTT
        3. Request/Response #2 - 1 RTT (no reconnect!)
        4. Request/Response #3 - 1 RTT (still connected!)
        5. Close when done - 1 RTT
        Total: 5 RTTs for 3 requests (vs 9 RTTs the old way!)
        
        For a client in Japan connecting to a US server (150ms RTT),
        this saves 1.2 seconds for just 3 requests!
        
        ============================================================================
        ERROR HANDLING PHILOSOPHY - FAIL GRACEFULLY, LOG EVERYTHING
        ============================================================================
        
        Three types of disconnection:
        
        1. ConnectionError: Client closed normally
           - This is EXPECTED behavior
           - Client finished and said goodbye
           - Like hanging up after a phone call
        
        2. socket.timeout: Client went silent
           - Network issue? Client crashed? 
           - We can't wait forever
           - Like hanging up on a silent phone call
        
        3. Exception: Something unexpected
           - Malformed data? Bug in our code?
           - Log it for debugging
           - Don't crash the whole server!
        
        ============================================================================
        IMPLEMENTATION WITH DETAILED EXPLANATIONS
        ============================================================================
        
        try:
            # CRITICAL: Set timeout to prevent hanging on dead connections
            # Without this, one bad client can freeze your handler forever!
            client_socket.settimeout(TIMEOUT_SECONDS)
            
            # Keep connection open for multiple requests (persistent connection)
            while True:
                try:
                    # Receive complete message - this is complex!
                    # TCP is stream-based, not message-based
                    # Data might arrive in pieces: "HEL" then "LO WORLD"
                    # receive_complete_message() handles reassembly
                    message_bytes = receive_complete_message(client_socket)
                    
                    # Process: bytes → objects → logic → objects → bytes
                    # This separation makes the protocol testable
                    response_bytes = self._process_message(message_bytes)
                    
                    # sendall() vs send():
                    # send() might only send part: sent 50 of 100 bytes
                    # sendall() keeps trying until all sent
                    client_socket.sendall(response_bytes)
                    
                    # Debug helper - see the conversation:
                    # print(f"Request: {len(message_bytes)} bytes, Response: {len(response_bytes)} bytes")
                    
                except ConnectionError as e:
                    # Normal disconnection - client closed their end
                    # Common errors: ConnectionResetError, BrokenPipeError
                    print(f"Client {client_address[0]} disconnected normally")
                    break
                    
                except socket.timeout:
                    # Client stopped talking - probably crashed or network died
                    # This prevents "ghost" connections from accumulating
                    print(f"Client {client_address[0]} timed out after {TIMEOUT_SECONDS}s")
                    break
                    
                except Exception as e:
                    # Unexpected error - log for debugging but don't crash!
                    # Could be: malformed packet, bug in our code, etc.
                    print(f"ERROR with client {client_address[0]}: {type(e).__name__}: {e}")
                    # In production: log to file, send to monitoring system
                    break
                    
        finally:
            # GUARANTEED CLEANUP - even if we hit an error!
            # Without this, sockets leak and eventually you run out
            client_socket.close()
            # Debug: print(f"Closed connection to {client_address[0]}")
        
        ============================================================================
        THE TCP STREAM PROBLEM (WHY receive_complete_message EXISTS)
        ============================================================================
        
        TCP doesn't preserve message boundaries! If client sends:
        - Message 1: "HELLO" (5 bytes)
        - Message 2: "WORLD" (5 bytes)
        
        You might receive:
        - recv() #1: "HELLOW" (6 bytes - parts of both!)
        - recv() #2: "ORLD" (4 bytes - rest of message 2)
        
        That's why protocols need length headers or delimiters.
        Our protocol uses a 4-byte length header (see snmp_protocol.py).
        
        receive_complete_message() handles this:
        1. Read 4-byte header to know message size
        2. Keep reading until we have all bytes
        3. Return complete message
        
        ============================================================================
        DEBUGGING STRATEGIES FOR CONNECTION ISSUES
        ============================================================================
        
        Problem: Handler seems to hang
        Debug:
        1. Add print before each operation:
           print("Waiting for message...")
           message_bytes = receive_complete_message(client_socket)
           print(f"Got {len(message_bytes)} bytes")
        
        2. Check if client is actually sending:
           Use Wireshark or tcpdump to see network traffic
        
        Problem: "Connection reset by peer"
        Cause: Client forcefully closed (crashed, killed, network died)
        Solution: This is normal - just handle the ConnectionError
        
        Problem: Clients randomly disconnect
        Possible causes:
        - Timeout too short (increase TIMEOUT_SECONDS)
        - Response takes too long (optimize _process_message)
        - Network issues (check ping times)
        
        Testing tip: Simulate problem clients:
        - Slow client: Add time.sleep() in client code
        - Crashy client: os._exit(1) mid-conversation  
        - Silent client: Connect but don't send anything
        
        ============================================================================
        WHAT YOU'RE LEARNING (INDUSTRY RELEVANCE)
        ============================================================================
        
        This pattern appears everywhere:
        
        1. Web Servers (handling HTTP requests)
           - Each request handler looks just like this
           - Parse request, process, send response
        
        2. Database Servers (handling SQL queries)
           - Receive query, execute, return results
           - Same timeout and error handling
        
        3. Game Servers (handling player actions)
           - Receive action, update game state, broadcast changes
           - Even tighter timeouts (milliseconds!)
        
        4. Microservices (handling API calls)
           - Your future REST APIs will use this pattern
           - Same connection management issues
        
        Master this, and you understand the foundation of all network services!
        
        Test verification: TestGetOperations::test_multiple_oid_get
        This test sends multiple requests on one connection!
        """
        try:
            # TODO: Set socket timeout with settimeout()
            # TODO: Loop to handle multiple requests on same connection
            # TODO: Receive message using receive_complete_message()
            # TODO: Process message with _process_message()
            # TODO: Send response with sendall()
            # TODO: Handle ConnectionError (normal disconnect)
            # TODO: Handle socket.timeout (idle too long)
            # TODO: Handle other exceptions (log error)
            
            raise NotImplementedError("Implement _handle_client")
            
        finally:
            client_socket.close()
    
    def _process_message(self, message_bytes: bytes) -> bytes:
        """
        Process a received SNMP message and return the response.
        
        TODO: Implement message processing dispatcher (BUNDLE 1 REQUIREMENT)
        Returns: bytes - The response message as bytes
        
        ============================================================================
        THE MESSAGE DISPATCHER - YOUR PROTOCOL'S BRAIN
        ============================================================================
        
        This method is like a receptionist routing calls:
        - "Sales call? Transfer to sales department"
        - "Support call? Transfer to tech support"
        - "Unknown? Sorry, we can't help"
        
        In our case:
        - GET request? Route to _handle_get_request()
        - SET request? Route to _handle_set_request()
        - Unknown? Raise error (shouldn't happen)
        
        ============================================================================
        THE BYTES → OBJECTS → BYTES PATTERN (SERIALIZATION/DESERIALIZATION)
        ============================================================================
        
        Network protocols can't send Python objects directly. They send bytes.
        This method orchestrates the transformation:
        
        1. DESERIALIZATION (bytes → objects)
           Raw bytes: 00 00 00 16 00 00 04 D2 A0 01...
                                ↓
           Python object: GetRequest(request_id=1234, oids=['1.3.6...'])
        
        2. BUSINESS LOGIC (objects → objects)
           GetRequest object → _handle_get_request() → GetResponse object
        
        3. SERIALIZATION (objects → bytes)
           GetResponse(request_id=1234, values=...)
                                ↓
           Raw bytes: 00 00 00 2A 00 00 04 D2 A2 00...
        
        This same pattern appears in:
        - JSON APIs: JSON string → dict → logic → dict → JSON string
        - Protocol Buffers: bytes → message → logic → message → bytes
        - Database drivers: SQL → query object → execute → result set → rows
        
        ============================================================================
        WHY ISINSTANCE() FOR TYPE CHECKING
        ============================================================================
        
        Python's isinstance() is like a security guard checking IDs:
        isinstance(message, GetRequest) asks: "Are you a GetRequest?"
        
        Why not use type() == GetRequest?
        - isinstance() works with inheritance (future-proof)
        - More Pythonic and readable
        - Same pattern as error handling: isinstance(e, ConnectionError)
        
        This prepares you for:
        - Polymorphism in OOP
        - Protocol handling in networking
        - Event dispatching in GUIs
        - Command pattern in game engines
        
        ============================================================================
        IMPLEMENTATION WITH DETAILED EXPLANATIONS
        ============================================================================
        
        # Step 1: Deserialize - Convert bytes to Python object
        # unpack_message() reads the PDU type byte and creates the right class
        message = unpack_message(message_bytes)
        
        # Debug: See what we received
        # print(f"Received {type(message).__name__} with ID {message.request_id}")
        
        # Step 2: Dispatch - Route to appropriate handler based on type
        if isinstance(message, GetRequest):
            # GET request - retrieve values from MIB
            response = self._handle_get_request(message)
            
        elif isinstance(message, SetRequest):
            # SET request - modify values in MIB
            response = self._handle_set_request(message)
            
        else:
            # This shouldn't happen if unpack_message() is correct
            # But defensive programming says: always have a fallback!
            raise ValueError(f"Unknown message type: {type(message).__name__}")
        
        # Step 3: Serialize - Convert response object back to bytes
        response_bytes = response.pack()
        
        # Debug: See what we're sending
        # print(f"Sending response: {len(response_bytes)} bytes")
        
        return response_bytes
        
        ============================================================================
        ERROR HANDLING PHILOSOPHY
        ============================================================================
        
        Why raise ValueError for unknown message types?
        - It's a programming error if we get here
        - unpack_message() should only create known types
        - Raising helps catch bugs during development
        - In production, you might log and return an error response instead
        
        Real-world analogy:
        - HTTP servers return 501 Not Implemented for unknown methods
        - SQL returns "syntax error" for invalid queries
        - Game servers disconnect clients sending invalid packets
        
        ============================================================================
        EXTENDING THE DISPATCHER (FUTURE ENHANCEMENTS)
        ============================================================================
        
        Adding new message types is easy:
        
        elif isinstance(message, GetNextRequest):  # SNMP walk operation
            response = self._handle_get_next_request(message)
            
        elif isinstance(message, BulkRequest):     # Efficient bulk retrieval
            response = self._handle_bulk_request(message)
            
        elif isinstance(message, TrapRequest):     # Async notifications
            response = self._handle_trap_request(message)
        
        This extensibility is why we use the dispatcher pattern!
        
        ============================================================================
        DEBUGGING STRATEGIES
        ============================================================================
        
        1. Log message types:
           print(f"Message type: {type(message).__name__}")
           print(f"Request ID: {message.request_id}")
        
        2. Verify serialization round-trip:
           # After creating response:
           test_bytes = response.pack()
           test_unpack = unpack_message(test_bytes)
           assert isinstance(test_unpack, GetResponse)
        
        3. Hex dump for debugging:
           print("Request bytes:", message_bytes.hex())
           print("Response bytes:", response_bytes.hex())
        
        4. Catch specific errors:
           try:
               message = unpack_message(message_bytes)
           except struct.error as e:
               print(f"Malformed message: {e}")
               # Could return an error response here
        
        ============================================================================
        PERFORMANCE CONSIDERATIONS
        ============================================================================
        
        This method is called for EVERY request, so efficiency matters:
        
        - unpack_message() should fail fast on bad data
        - Handlers should cache computed values
        - pack() should pre-allocate byte arrays
        
        In high-performance scenarios:
        - Use memory views instead of copying bytes
        - Cache serialized responses for common requests
        - Consider async I/O for handlers
        
        Test verification: Every integration test exercises this dispatcher
        """
        # TODO: Unpack the message using unpack_message()
        # TODO: Check type with isinstance()
        # TODO: Call appropriate handler
        # TODO: Pack and return response
        
        raise NotImplementedError("Implement _process_message")
    
    # ========================================================================
    # STUDENT IMPLEMENTATION: Protocol handlers
    # ========================================================================
    
    def _handle_get_request(self, request: GetRequest) -> GetResponse:
        """
        Process a GetRequest and return values from the MIB.
        
        TODO: Implement GET request handling (BUNDLE 1 REQUIREMENT)
        Returns: GetResponse with requested values or error
        
        ============================================================================
        THE GET REQUEST - READING DATA FROM YOUR MANAGED DEVICE
        ============================================================================
        
        In SNMP, GET is how network admins ask: "What's your status?"
        Examples:
        - "What's your hostname?" (OID 1.3.6.1.2.1.1.5.0)
        - "How long have you been running?" (OID 1.3.6.1.2.1.1.3.0)
        - "Where are you located?" (OID 1.3.6.1.2.1.1.6.0)
        
        Real-world: Monitoring tools (Nagios, Zabbix, DataDog) send thousands
        of GET requests per second to track infrastructure health.
        
        ============================================================================
        WHY REQUEST ID MATCHING IS CRITICAL
        ============================================================================
        
        The request_id is like a tracking number for packages:
        
        Without request_id matching:
        1. Client sends: "Get temperature" (request_id: 1234)
        2. Client sends: "Get humidity" (request_id: 1235)  
        3. Server responds with humidity data but wrong ID
        4. Client thinks humidity is temperature! ⚠️
        
        With proper matching:
        - Client can send multiple requests without waiting
        - Responses can arrive out of order
        - Client matches response to correct request
        - No confusion even with concurrent requests!
        
        This is the same concept as:
        - HTTP request IDs in async JavaScript
        - Database transaction IDs
        - TCP sequence numbers
        - Correlation IDs in microservices
        
        CRITICAL: response.request_id = request.request_id
        
        ============================================================================
        THE ALL-OR-NOTHING PRINCIPLE FOR GET
        ============================================================================
        
        If client asks for 3 OIDs and one doesn't exist:
        ❌ WRONG: Return 2 values and skip the missing one
        ✅ RIGHT: Return error for entire request
        
        Why? Consistency and predictability:
        - Client knows exactly what failed
        - No partial data that might be misinterpreted
        - Clear error handling path
        
        Like SQL: SELECT name, age, invalid_column FROM users
        The whole query fails, not just the bad column.
        
        ============================================================================
        IMPLEMENTATION WITH DETAILED EXPLANATIONS
        ============================================================================
        
        # Step 1: Update dynamic values FIRST
        # Some values change over time (uptime, counters)
        # Must be fresh when read!
        self._update_dynamic_values()
        
        # Step 2: Validate ALL OIDs exist before collecting any values
        # This implements the all-or-nothing principle
        for oid in request.oids:
            if oid not in self.mib:
                # Early return on first missing OID
                # Note: We still use request.request_id for tracking!
                print(f"ERROR: OID {oid} not found in MIB")
                return GetResponse(
                    request.request_id,  # CRITICAL: Match the request ID!
                    ErrorCode.NO_SUCH_OID,
                    []  # Empty bindings on error (protocol requirement)
                )
        
        # Step 3: Now collect all values (we know they all exist)
        bindings = []
        for oid in request.oids:
            # MIB structure: {oid: (type_string, value)}
            # Example: '1.3.6.1.2.1.1.5.0': ('STRING', 'router-main')
            mib_type, mib_value = self.mib[oid]
            
            # Convert string type to protocol enum
            # 'STRING' → ValueType.STRING
            value_type = self._get_value_type(mib_type)
            
            # Build binding tuple: (oid, type, value)
            bindings.append((oid, value_type, mib_value))
            
            # Debug: print(f"Retrieved: {oid} = {mib_value} (type: {value_type})")
        
        # Step 4: Return success with all values
        return GetResponse(
            request.request_id,     # Must match for client correlation!
            ErrorCode.SUCCESS,      # All good!
            bindings               # The actual data
        )
        
        ============================================================================
        COMMON MISTAKES AND HOW TO AVOID THEM
        ============================================================================
        
        Mistake 1: Forgetting to match request_id
        Symptom: Client timeouts or "unexpected response" errors
        Fix: ALWAYS copy request.request_id to response
        
        Mistake 2: Returning partial results on error
        Symptom: Client gets incomplete data, makes wrong decisions
        Fix: Return empty bindings with error code
        
        Mistake 3: Not updating dynamic values
        Symptom: Uptime never changes, always shows 0
        Fix: Call _update_dynamic_values() first
        
        Mistake 4: Wrong type conversion
        Symptom: Client expects INTEGER, gets STRING
        Fix: Use _get_value_type() for correct mapping
        
        ============================================================================
        DEBUGGING STRATEGIES
        ============================================================================
        
        1. Trace the request:
           print(f"GET request ID {request.request_id} for {len(request.oids)} OIDs")
           for oid in request.oids:
               print(f"  - {oid}")
        
        2. Verify MIB contents:
           print(f"MIB has {len(self.mib)} entries")
           if oid in self.mib:
               print(f"Found: {oid} = {self.mib[oid]}")
           else:
               print(f"NOT FOUND: {oid}")
        
        3. Check response before sending:
           print(f"Response: ID={response.request_id}, Error={response.error_code}")
           print(f"Bindings: {response.bindings}")
        
        4. Test with snmp_manager.py:
           python3 snmp_manager.py get localhost 1.3.6.1.2.1.1.5.0
           # Should return the system name
        
        ============================================================================
        WHAT YOU'RE LEARNING
        ============================================================================
        
        This pattern (request → validate → collect → respond) appears in:
        - REST APIs: GET /api/users/123
        - GraphQL: Query resolution
        - Database queries: SELECT operations
        - Cache lookups: Redis/Memcached
        - Configuration management: Reading settings
        
        The request ID matching prepares you for:
        - Async programming (JavaScript Promises)
        - Message queuing (RabbitMQ, Kafka)
        - Distributed tracing (Zipkin, Jaeger)
        - Microservice communication
        
        Test verification: TestGetOperations::test_single_oid_get
        """
        # Update dynamic values first (like uptime)
        self._update_dynamic_values()
        
        # TODO: Create empty bindings list
        # TODO: For each OID in request.oids:
        #       - Check if OID exists in self.mib
        #       - If not, return error response
        #       - If yes, get value and type, add to bindings
        # TODO: Return success response with all bindings
        
        raise NotImplementedError("Implement _handle_get_request")
    
    def _handle_set_request(self, request: SetRequest) -> GetResponse:
        """
        Process a SetRequest and update values in the MIB.
        
        TODO: Implement SET request handling (BUNDLE 2 REQUIREMENT)
        Returns: GetResponse with updated values or error
        
        ============================================================================
        THE SET REQUEST - CONFIGURING YOUR MANAGED DEVICE
        ============================================================================
        
        SET is how network admins configure devices remotely:
        - "Change hostname to 'router-backup'" 
        - "Set location to 'Data Center Row 3'"
        - "Enable interface eth0"
        
        Real-world: Network automation tools use SET to:
        - Configure hundreds of switches simultaneously
        - Update firewall rules across the network
        - Change VLAN assignments
        - Adjust QoS parameters
        
        With great power comes great responsibility - that's why we have
        permissions and strict validation!
        
        ============================================================================
        THE THREE LAYERS OF PROTECTION (VALIDATION HIERARCHY)
        ============================================================================
        
        Like a bouncer at a club, we check three things IN ORDER:
        
        1. EXISTENCE: "Is this OID even in our MIB?"
           - Can't modify what doesn't exist
           - Error: NO_SUCH_OID
           - Like trying to UPDATE a non-existent database row
        
        2. PERMISSION: "Are you allowed to change this?"
           - Some values are read-only (like uptime)
           - Check MIB_PERMISSIONS dictionary
           - Error: READ_ONLY
           - Like trying to change a const variable
        
        3. TYPE SAFETY: "Is this the right type of value?"
           - Can't set an INTEGER field to "hello"
           - Type must match what's in MIB
           - Error: BAD_VALUE  
           - Like TypeScript/Java type checking
        
        Only if ALL three pass do we proceed!
        
        ============================================================================
        WHY ALL-OR-NOTHING MATTERS (TRANSACTIONAL INTEGRITY)
        ============================================================================
        
        Imagine configuring a redundant network link:
        SET Request:
        1. primary_link_ip = "192.168.1.1"
        2. backup_link_ip = "192.168.1.999"  ← Invalid IP!
        
        Without all-or-nothing (DANGEROUS):
        - Primary IP changes ✅
        - Backup IP fails ❌
        - Result: Broken failover configuration! Network outage waiting to happen!
        
        With all-or-nothing (SAFE):
        - Validation finds the bad IP
        - NEITHER change is applied
        - Configuration stays consistent
        - Admin fixes the typo and retries
        
        This is the "A" in ACID (Atomicity):
        - All changes succeed together
        - Or all changes fail together
        - Never partial updates!
        
        Same principle as:
        - Database transactions (BEGIN...COMMIT/ROLLBACK)
        - Git commits (all files or none)
        - Kubernetes deployments (rolling updates)
        - Financial transfers (debit AND credit, never just one)
        
        ============================================================================
        THE TWO-PHASE IMPLEMENTATION PATTERN
        ============================================================================
        
        Phase 1: VALIDATE EVERYTHING (Read-only, safe)
        ┌────────────────────────────────────────────────┐
        │ for each (oid, type, value):                 │
        │     │                                        │
        │     ├─ Exists? ────» NO ──» Return ERROR    │
        │     │    ↓ YES                               │
        │     ├─ Writable? ──» NO ──» Return ERROR    │
        │     │    ↓ YES                               │
        │     └─ Type OK? ───» NO ──» Return ERROR    │
        │          ↓ YES                               │
        │         Continue                             │
        └────────────────────────────────────────────────┘
        
        Phase 2: APPLY ALL CHANGES (Writes, modifies state)
        ┌────────────────────────────────────────────────┐
        │ All validation passed! Safe to modify:       │
        │ for each (oid, type, value):                 │
        │     Update MIB[oid] = (type, value)          │
        │     Add to response                          │
        └────────────────────────────────────────────────┘
        
        ============================================================================
        IMPLEMENTATION WITH DETAILED EXPLANATIONS
        ============================================================================
        
        # PHASE 1: VALIDATE ALL BINDINGS (No changes yet!)
        for oid, value_type, value in request.bindings:
            
            # Check 1: Does this OID exist?
            if oid not in self.mib:
                print(f"SET failed: OID {oid} doesn't exist")
                return GetResponse(
                    request.request_id,  # Always match request ID!
                    ErrorCode.NO_SUCH_OID,
                    []  # Empty bindings on any error
                )
            
            # Check 2: Is this OID writable?
            # MIB_PERMISSIONS is a dict: {oid: 'read-only' or 'read-write'}
            # Default to 'read-only' for safety (fail closed, not open)
            permission = MIB_PERMISSIONS.get(oid, 'read-only')
            if permission != 'read-write':
                print(f"SET failed: OID {oid} is {permission}")
                return GetResponse(
                    request.request_id,
                    ErrorCode.READ_ONLY,
                    []
                )
            
            # Check 3: Does the type match?
            # MIB stores (type_string, current_value)
            # We need to ensure new value type matches stored type
            mib_type, _ = self.mib[oid]
            expected_type = self._get_value_type(mib_type)
            if value_type != expected_type:
                print(f"SET failed: OID {oid} expects {expected_type}, got {value_type}")
                return GetResponse(
                    request.request_id,
                    ErrorCode.BAD_VALUE,
                    []
                )
        
        # PHASE 2: APPLY ALL CHANGES (We know they're ALL valid now!)
        response_bindings = []
        for oid, value_type, value in request.bindings:
            # Get the current type (we keep this, only change value)
            mib_type, old_value = self.mib[oid]
            
            # Update the MIB with new value
            self.mib[oid] = (mib_type, value)
            print(f"SET: {oid} changed from '{old_value}' to '{value}'")
            
            # Add to response (confirms what was set)
            response_bindings.append((oid, value_type, value))
        
        # Return success with all the new values
        return GetResponse(
            request.request_id,
            ErrorCode.SUCCESS,
            response_bindings  # Echo back what we set (confirmation)
        )
        
        ============================================================================
        COMMON MISTAKES AND DEBUGGING
        ============================================================================
        
        Mistake 1: Applying changes during validation
        Symptom: Partial updates when later validation fails
        Fix: NEVER modify state in Phase 1
        Debug: Add print("VALIDATION PHASE") and print("APPLY PHASE")
        
        Mistake 2: Not checking permissions
        Symptom: Uptime gets changed (should be read-only!)
        Fix: Always check MIB_PERMISSIONS
        Debug: print(f"Permission for {oid}: {MIB_PERMISSIONS.get(oid)}")
        
        Mistake 3: Accepting wrong types
        Symptom: String stored where integer expected, breaks other code
        Fix: Strict type checking
        Debug: print(f"Type check: {value_type} vs {expected_type}")
        
        Mistake 4: Not preserving type in MIB
        Symptom: After SET, type changes from 'INTEGER' to 'STRING'
        Fix: Keep original mib_type, only change value
        Debug: print(f"Before: {self.mib[oid]}, After: {(mib_type, value)}")
        
        ============================================================================
        TESTING YOUR IMPLEMENTATION
        ============================================================================
        
        1. Test successful SET:
           python3 snmp_manager.py set localhost 1.3.6.1.2.1.1.5.0 STRING "new-name"
           # Should change system name
        
        2. Test read-only protection:
           python3 snmp_manager.py set localhost 1.3.6.1.2.1.1.3.0 TIMETICKS 999
           # Should fail - uptime is read-only!
        
        3. Test type mismatch:
           python3 snmp_manager.py set localhost 1.3.6.1.2.1.1.5.0 INTEGER 42
           # Should fail - sysName expects STRING!
        
        4. Test all-or-nothing with multiple:
           # If any fail, none should change
        
        ============================================================================
        WHAT YOU'RE LEARNING (CAREER RELEVANCE)
        ============================================================================
        
        This two-phase validation pattern appears EVERYWHERE:
        
        1. Web Forms
           - Validate all fields
           - Then save to database
        
        2. API Endpoints
           - Validate request body
           - Then execute business logic
        
        3. Database Transactions
           - Check constraints
           - Then commit changes
        
        4. CI/CD Pipelines
           - Run all tests
           - Then deploy if all pass
        
        5. Blockchain Smart Contracts
           - Validate all conditions
           - Then execute state change
        
        Master this pattern, and you'll write safer, more reliable code
        throughout your career!
        
        Test verification: TestSetOperations (all must pass for Bundle 2)
        """
        # TODO: Phase 1 - Validate ALL bindings
        #       - Check each OID exists
        #       - Check each OID is writable
        #       - Check each value type matches
        #       - Return error if any check fails
        
        # TODO: Phase 2 - Apply ALL changes
        #       - Update self.mib for each binding
        #       - Build response bindings
        
        # TODO: Return success response with new values
        
        raise NotImplementedError("Implement _handle_set_request")
    
    # ========================================================================
    # STUDENT IMPLEMENTATION: Helper methods
    # ========================================================================
    
    def _update_dynamic_values(self):
        """
        Update MIB values that change over time.
       
        Returns: None - Updates self.mib in place
        
        ============================================================================
        DYNAMIC VALUES - KEEPING YOUR DATA FRESH
        ============================================================================
        
        Some MIB values are like a clock - they change constantly:
        - Uptime: How long has the device been running?
        - Packet counters: How many packets sent/received?
        - CPU usage: Current load percentage
        - Temperature: Current sensor reading
        
        We update these "just in time" before responding to GET requests.
        This ensures clients always get current data, not stale cache.
        
        ============================================================================
        SYSTEM UPTIME - THE HEARTBEAT OF YOUR DEVICE
        ============================================================================
        
        Uptime tells you how long a device has been running without restart.
        It's crucial for:
        - Detecting recent reboots (security concern!)
        - Measuring stability (99.999% uptime = 5 minutes downtime/year)
        - Troubleshooting ("Did the problem start after last reboot?")
        
        Real-world: Network monitoring dashboards show uptime prominently.
        Amazon EC2 instances, Google Cloud VMs, your home router - all track this.
        
        ============================================================================
        WHY TIMETICKS? (THE SNMP TIME UNIT)
        ============================================================================
        
        SNMP uses "timeticks" - hundredths of a second:
        - 1 second = 100 timeticks
        - 1 minute = 6,000 timeticks  
        - 1 hour = 360,000 timeticks
        - 1 day = 8,640,000 timeticks
        
        Why not just use seconds?
        1. Precision: Can measure 10ms intervals
        2. Compatibility: SNMP v1 (1988) used 32-bit integers
        3. Range: 2^32 timeticks = ~497 days (good enough for most uses)
        
        Fun fact: After 497 days, uptime wraps around to 0!
        This is why enterprise systems also track boot time separately.
        
        ============================================================================
        IMPLEMENTATION WITH DETAILED EXPLANATIONS
        ============================================================================
        
        # Step 1: Calculate how long we've been running (in seconds)
        # time.time() returns seconds since Unix epoch (Jan 1, 1970)
        # self.start_time was set when agent started (__init__)
        uptime_seconds = time.time() - self.start_time
        
        # Debug: See the uptime in human-readable format
        # hours = int(uptime_seconds // 3600)
        # minutes = int((uptime_seconds % 3600) // 60)
        # seconds = int(uptime_seconds % 60)
        # print(f"Uptime: {hours}h {minutes}m {seconds}s")
        
        # Step 2: Convert to SNMP timeticks (100ths of second)
        # Multiply by 100 to convert seconds to timeticks
        # Use int() to truncate decimals (SNMP doesn't do fractional timeticks)
        uptime_ticks = int(uptime_seconds * TIMETICKS_PER_SECOND)
        
        # Step 3: Update the MIB with fresh value
        # OID 1.3.6.1.2.1.1.3.0 is sysUpTime (standard SNMP OID)
        # Keep the type as 'TIMETICKS', only update the value
        self.mib['1.3.6.1.2.1.1.3.0'] = ('TIMETICKS', uptime_ticks)
        
        # Debug: Verify the update
        # print(f"Updated uptime to {uptime_ticks} timeticks ({uptime_seconds:.2f} seconds)")
        
        ============================================================================
        COMMON MISTAKES AND EDGE CASES
        ============================================================================
        
        Mistake 1: Using current time instead of elapsed time
        Wrong: uptime_ticks = int(time.time() * 100)
        Right: uptime_ticks = int((time.time() - self.start_time) * 100)
        
        Mistake 2: Forgetting to multiply by 100
        Wrong: uptime_ticks = int(uptime_seconds)  # This would be seconds!
        Right: uptime_ticks = int(uptime_seconds * TIMETICKS_PER_SECOND)
        
        Mistake 3: Changing the type in MIB
        Wrong: self.mib['1.3.6.1.2.1.1.3.0'] = uptime_ticks  # Lost type info!
        Right: self.mib['1.3.6.1.2.1.1.3.0'] = ('TIMETICKS', uptime_ticks)
        
        Edge case: Very long uptime
        After ~497 days, timeticks overflow 32-bit integer
        In production, you'd handle wraparound or use 64-bit counter
        
        ============================================================================
        EXTENDING TO OTHER DYNAMIC VALUES
        ============================================================================
        
        Future enhancements could update:
        
        # Interface statistics (if tracking network I/O)
        if '1.3.6.1.2.1.2.2.1.10.1' in self.mib:  # ifInOctets
            bytes_received = get_network_stats()['rx_bytes']
            self.mib['1.3.6.1.2.1.2.2.1.10.1'] = ('COUNTER', bytes_received)
        
        # CPU usage (if monitoring system resources)
        if '1.3.6.1.4.1.2021.11.9.0' in self.mib:  # ssCpuUser
            cpu_percent = psutil.cpu_percent()
            self.mib['1.3.6.1.4.1.2021.11.9.0'] = ('INTEGER', int(cpu_percent))
        
        # Temperature sensors (if hardware monitoring)
        if '1.3.6.1.4.1.9999.1.1.0' in self.mib:  # custom temperature OID
            temp_celsius = read_temperature_sensor()
            self.mib['1.3.6.1.4.1.9999.1.1.0'] = ('INTEGER', temp_celsius)
        
        ============================================================================
        TESTING YOUR IMPLEMENTATION
        ============================================================================
        
        1. Start your agent and immediately query uptime:
           python3 snmp_manager.py get localhost 1.3.6.1.2.1.1.3.0
           # Should show small value (< 100 timeticks)
        
        2. Wait 10 seconds and query again:
           # Should show ~1000 timeticks (10 seconds * 100)
        
        3. Verify uptime increases monotonically:
           # Each query should show a larger value than before
        
        Debug output to add:
        print(f"Uptime: {uptime_ticks} timeticks ({uptime_seconds:.2f}s)")
        
        ============================================================================
        WHAT YOU'RE LEARNING
        ============================================================================
        
        This "update before read" pattern appears in:
        - Cache invalidation (update before serving)
        - Database views (refresh materialized views)
        - API rate limiting (update request counts)
        - Session management (update last activity time)
        - Game state (update positions before rendering)
        
        The timeticks concept prepares you for:
        - Working with different time units across systems
        - Understanding precision vs range tradeoffs
        - Handling counter wraparounds
        - Network protocol time representations
        
        Test verification: TestErrorHandling::test_dynamic_values_update
        """
        # Step 1: Calculate how long we've been running (in seconds)
        # time.time() returns seconds since Unix epoch (Jan 1, 1970)
        # self.start_time was set when agent started (__init__)
        uptime_seconds = time.time() - self.start_time
        
        # Debug: See the uptime in human-readable format
        # hours = int(uptime_seconds // 3600)
        # minutes = int((uptime_seconds % 3600) // 60)
        # seconds = int(uptime_seconds % 60)
        # print(f"Uptime: {hours}h {minutes}m {seconds}s")
        
        # Step 2: Convert to SNMP timeticks (100ths of second)
        # Multiply by 100 to convert seconds to timeticks
        # Use int() to truncate decimals (SNMP doesn't do fractional timeticks)
        uptime_ticks = int(uptime_seconds * TIMETICKS_PER_SECOND)
        
        # Step 3: Update the MIB with fresh value
        # OID 1.3.6.1.2.1.1.3.0 is sysUpTime (standard SNMP OID)
        # Keep the type as 'TIMETICKS', only update the value
        self.mib['1.3.6.1.2.1.1.3.0'] = ('TIMETICKS', uptime_ticks)
        
        # Debug: Verify the update
        # print(f"Updated uptime to {uptime_ticks} timeticks ({uptime_seconds:.2f} seconds)")
        # TODO: Update self.mib['1.3.6.1.2.1.1.3.0']
        raise NotImplementedError("Implement _update_dynamic_values")
    
    def _get_value_type(self, type_str: str) -> ValueType:
        """
        PROVIDED: Convert MIB type string to ValueType enum
        
        The MIB database stores type as strings ('INTEGER', 'STRING', etc.)
        This converts them to ValueType enum values for the protocol.
        """
        mapping = {
            'INTEGER': ValueType.INTEGER,
            'STRING': ValueType.STRING,
            'COUNTER': ValueType.COUNTER,
            'TIMETICKS': ValueType.TIMETICKS,
        }
        return mapping.get(type_str, ValueType.STRING)
    
# ============================================================================
# MAIN ENTRY POINT (PROVIDED)
# ============================================================================

def main():
    """
    PROVIDED: Main entry point with command-line parsing
    
    Usage: python3 snmp_agent.py [port]
    Default port: 1161
    """
    # Parse command line arguments
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
            if not 1 <= port <= 65535:
                print(f"Error: Port must be between 1 and 65535")
                sys.exit(1)
        except ValueError:
            print(f"Error: Invalid port number: {sys.argv[1]}")
            sys.exit(1)
    
    # Create and start the agent
    agent = SNMPAgent(port)
    try:
        agent.start()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()