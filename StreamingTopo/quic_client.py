import asyncio
import time
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol

class VideoStreamProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_data = b''
        self.start_time = time.time()
        self.first_chunk_time = 0
        self.connection_time = 0
        self.current_stream_id = None
        self.video_name = None
        self.transfer_complete = asyncio.Event()

    def get_next_stream_id(self) -> int:
        """Get the next available client-initiated stream ID"""
        return self._quic.get_next_available_stream_id()

    async def request_video(self, video_name: bytes) -> None:
        """Initiate video request on a new stream"""
        self.video_name = video_name
        self.current_stream_id = self.get_next_stream_id()
        
        self._quic.send_stream_data(
            stream_id=self.current_stream_id,
            data=f"GET {video_name.decode()}".encode(),
            end_stream=False
        )
        
        await self.transfer_complete.wait()

    def quic_event_received(self, event):
        """Handle incoming QUIC events"""
        if isinstance(event, StreamDataReceived) and event.stream_id == self.current_stream_id:
            if not self.video_data:  # First chunk
                self.first_chunk_time = time.time() - self.start_time
                self.connection_time = self.first_chunk_time  # Time until first data
                print(f"Connection established, time: {self.connection_time:.3f}s")
                print(f"First packet received on stream {self.current_stream_id}")
            
            self.video_data += event.data
            
            if event.end_stream:
                self._handle_transfer_complete()

    def _handle_transfer_complete(self):
        """Finalize transfer and print statistics"""
        total_time = time.time() - self.start_time
        transfer_time = total_time - self.first_chunk_time
        
        print(f"\nTransfer complete for {self.video_name.decode()}")
        print(f"Total time: {total_time:.3f} seconds")
        print(f"Video size: {len(self.video_data)/1024:.2f} KB")
        print(f"Transfer rate: {(len(self.video_data)/1024)/transfer_time:.2f} KB/s")
        
        self._save_video()
        self.transfer_complete.set()

    def _save_video(self):
        """Save video data to file"""
        filename = f"received_{self.video_name.decode()}"
        with open(filename, 'wb') as f:
            f.write(self.video_data)
        print(f"Video saved as {filename}")

class VideoStreamClient:
    def __init__(self):
        self.configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["video-stream"],
            max_datagram_frame_size=65536,
            verify_mode=False
        )

    async def run(self, host: str, port: int, video_name: bytes):
        print(f"Connecting to {host}:{port}...")
        
        async with connect(
            host=host,
            port=port,
            configuration=self.configuration,
            create_protocol=VideoStreamProtocol
        ) as protocol:
            print("Connected, requesting video...")
            await protocol.request_video(video_name)

async def main():
    client = VideoStreamClient()
    await client.run("10.0.0.1", 4433, b"sample.mp4")

if __name__ == "__main__":
    asyncio.run(main())