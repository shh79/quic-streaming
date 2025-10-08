import subprocess
import time
import random

SERVER_IP = "10.0.0.3"
DURATION = 60
CHUNK_TIME = 5
BITRATES = [1, 2, 4, 6, 8, 10]  # Mbps levels, similar to video quality ladder

start_time = time.time()
print("Starting adaptive video streaming simulation...\n")

while (time.time() - start_time) < DURATION:
    bitrate = random.choice(BITRATES)
    print(f"Sending at {bitrate} Mbps for {CHUNK_TIME} seconds...")
    cmd = [
        "iperf3", "-c", SERVER_IP, "-u",
        "-b", f"{bitrate}M", "-t", str(CHUNK_TIME), "-i", "1"
    ]
    subprocess.run(cmd)
    time.sleep(1)

print("\nSimulation finished.")
