import random
import subprocess
import time

# Configuration
SERVER_IP = "10.0.0.3"
MIN_FLOWS = 1
MAX_FLOWS = 5

def run_flow(flow_id):
    """Run a single random iperf3 flow (TCP or UDP)."""
    protocol = random.choice(["TCP", "UDP"])
    duration = random.randint(10, 30)   # seconds

    if protocol == "TCP":
        parallel = random.randint(1, 4)
        cmd = [
            "iperf3",
            "-c", SERVER_IP,
            "-t", str(duration),
            "-P", str(parallel),
            "-i", "1"
        ]
        print(f"Flow {flow_id}: TCP | {duration}s | {parallel} streams")

    else:
        bandwidth = f"{random.randint(1, 100)}M"
        cmd = [
            "iperf3",
            "-c", SERVER_IP,
            "-u",
            "-b", bandwidth,
            "-t", str(duration),
            "-i", "1"
        ]
        print(f"Flow {flow_id}: UDP | {bandwidth} | {duration}s")

    # Start process (non-blocking)
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def main():
    num_flows = random.randint(MIN_FLOWS, MAX_FLOWS)
    print(f"Starting {num_flows} random iperf3 flows...\n")

    processes = []
    for i in range(1, num_flows + 1):
        p = run_flow(i)
        processes.append(p)
        time.sleep(random.uniform(0.5, 2.0))  # optional staggered start

    # Wait for all flows to finish
    for p in processes:
        p.wait()

    print("\nAll flows completed.")

if __name__ == "__main__":
    main()
