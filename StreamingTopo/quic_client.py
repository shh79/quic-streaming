# Save this as /tmp/quic_client.py
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, QuicEvent
import asyncio
import time
import statistics

class VideoClientProtocol:
    def __init__(self):
        self.stream_id = None
        self.latencies = []
        self.start_time = None
        self.received_bytes = 0
        self.connection_established_time = None
        self.protocol = None

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            if self.start_time:
                latency = time.time() - self.start_time
                self.latencies.append(latency)
                self.received_bytes += len(event.data)
                print(f"Received {len(event.data)} bytes in {latency:.4f}s")
            
            # Request next chunk to measure throughput
            self.start_time = time.time()
            if self.protocol and self.stream_id is not None:
                self.protocol.send_stream_data(self.stream_id, b"request")

async def measure_connection_quality(host: str, port: int) -> None:
    configuration = QuicConfiguration(is_client=True)
    configuration.verify_mode = 0  # Disable certificate verification for testing
    
    try:
        # Create the protocol instance
        client_protocol = VideoClientProtocol()
        
        # Connect to the server - returns a single object in newer versions
        connection = connect(
            host=host,
            port=port,
            configuration=configuration,
            create_protocol=lambda: client_protocol
        )
        
        # Get the protocol from the connection
        client_protocol.protocol = connection.protocol
        client_protocol.stream_id = connection.protocol.get_next_available_stream_id()
        client_protocol.connection_established_time = time.time()
        
        # Initial request
        connection.protocol.send_stream_data(client_protocol.stream_id, b"request")
        client_protocol.start_time = time.time()
        
        # Measure for 10 seconds
        await asyncio.sleep(10)
        
        # Calculate statistics
        if client_protocol.latencies:
            avg_latency = statistics.mean(client_protocol.latencies) * 1000  # in ms
            min_latency = min(client_protocol.latencies) * 1000
            max_latency = max(client_protocol.latencies) * 1000
            jitter = statistics.stdev(client_protocol.latencies) * 1000 if len(client_protocol.latencies) > 1 else 0
            
            duration = time.time() - client_protocol.connection_established_time
            throughput = (client_protocol.received_bytes * 8) / duration / 1e6  # in Mbps
            
            print("\nConnection Quality Report:")
            print(f"  - Average Latency: {avg_latency:.2f} ms")
            print(f"  - Minimum Latency: {min_latency:.2f} ms")
            print(f"  - Maximum Latency: {max_latency:.2f} ms")
            print(f"  - Jitter: {jitter:.2f} ms")
            print(f"  - Throughput: {throughput:.2f} Mbps")
            print(f"  - Total Data Received: {client_protocol.received_bytes / 1024:.2f} KB")
        else:
            print("No data received to measure connection quality")
        
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    asyncio.run(measure_connection_quality("10.0.0.1", 4433))