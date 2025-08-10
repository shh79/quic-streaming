import os
import asyncio
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.asyncio.server import QuicServer

class VideoStreamHandler(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_files = {
            b'sample.mp4': open('../sample.mp4', 'rb')
        }

    async def handle_stream_data(self, stream_id, data):
        print(stream_id)
        # دریافت درخواست ویدیو از کلاینت
        if data.startswith(b'GET '):
            filename = data[4:].strip()
            if filename in self.video_files:
                print(f"Sending {filename.decode()} to client...")
                video_file = self.video_files[filename]
                chunk_size = 1024 * 16  # 16KB chunks
                
                # ارسال ویدیو به صورت chunked
                video_file.seek(0)
                while True:
                    chunk = video_file.read(chunk_size)
                    if not chunk:
                        break
                    self._quic.send_stream_data(stream_id, chunk, end_stream=False)
                    await asyncio.sleep(0.001)  # کنترل سرعت ارسال
                
                self._quic.send_stream_data(stream_id, b'', end_stream=True)
                print(f"Sending {filename.decode()} is completed.")
            else:
                self._quic.send_stream_data(stream_id, b'404 Video Not Found', end_stream=True)

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            asyncio.ensure_future(self.handle_stream_data(event.stream_id, event.data))

async def run_quic_server():
    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=["video-stream"],
        max_datagram_frame_size=65536,
    )
    
    # تولید گواهی خودامضا (برای تست)
    configuration.load_cert_chain("../cert.pem", "../key.pem")
    
    server = await serve(
        host='10.0.0.1',
        port=4433,
        configuration=configuration,
        create_protocol=VideoStreamHandler,
    )
    
    print("Server running on 4433...")
    await asyncio.Future()  # اجرای بی‌نهایت

if __name__ == "__main__":
    # ایجاد گواهی خودامضا اگر وجود ندارد
    # if not os.path.exists("../cert.pem") or not os.path.exists("../key.pem"):
    #     print("ایجاد گواهی خودامضا...")
    #     os.system("openssl req -x509 -newkey rsa:4096 -keyout private.key -out certificate.pem -days 365 -nodes -subj '/CN=localhost'")
    
    asyncio.run(run_quic_server())