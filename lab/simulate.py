from mininet.net import Mininet
from mininet.node import Controller, OVSKernelSwitch, Host
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time
import os
import subprocess

def setup_network():
    net = Mininet(controller=Controller, link=TCLink, switch=OVSKernelSwitch)

    info("*** Adding controller\n")
    net.addController('c0')

    info("*** Adding hosts and switch\n")
    server = net.addHost('server', ip='10.0.0.1')
    client = net.addHost('client', ip='10.0.0.2')
    switch = net.addSwitch('s1')

    info("*** Creating links\n")
    net.addLink(server, switch, bw=10, delay='50ms', loss=10, max_queue_size=1000)
    net.addLink(client, switch, bw=10, delay='50ms', loss=10, max_queue_size=1000)

    info("*** Starting network\n")
    net.start()

    return net, server, client

def simulate_protocol(net, server, client, protocol):
    info(f"\n*** Starting simulation for: {protocol} ***\n")
    delay = -1
    data_rate = -1

    if protocol == "HLS":
        info("*** Starting HTTP server for HLS\n")
        server.cmd('cd test_video/hls && python3 -m http.server 8080 &')
        time.sleep(2)

        client_output = client.cmd('curl -o downloaded_hls.m3u8 -s -w "%{time_total}\\n" http://10.0.0.1:8080/output.m3u8')
        delay = float(client_output.strip())
        size_bytes = os.path.getsize("downloaded_hls.m3u8")
        data_rate = (size_bytes / 1024) / delay  # KB/s

    elif protocol == "MPEG-DASH":
        info("*** Starting HTTP server for MPEG-DASH\n")
        server.cmd('cd test_video/mpeg-dash && python3 -m http.server 8080 &')
        time.sleep(2)

        client_output = client.cmd('curl -o downloaded_dash.mpd -s -w "%{time_total}\\n" http://10.0.0.1:8080/manifest.mpd')
        delay = float(client_output.strip())
        size_bytes = os.path.getsize("downloaded_dash.mpd")
        data_rate = (size_bytes / 1024) / delay  # KB/s

    elif protocol == "QUIC":
        info("*** Starting QUIC server\n")
        server.cmd('python3 quic_server.py &')
        time.sleep(2)

        client_output = client.cmd('python3 quic_client.py 10.0.0.1 4433')
        print(client_output)

        delay_line = [line for line in client_output.splitlines() if "Delay:" in line]
        if delay_line:
            parts = delay_line[0].split(",")
            delay = float(parts[0].split(":")[1].replace("s", "").strip())
            bytes_downloaded = int(parts[1].split(":")[1].strip())
            data_rate = (bytes_downloaded / 1024) / delay  # KB/s

    info(f"{protocol} => Delay: {delay:.2f}s | Data Rate: {data_rate:.2f} KB/s\n")

    # Save results
    with open("results.csv", "a") as f:
        f.write(f"{protocol},{delay:.2f},{data_rate:.2f}\n")


def cleanup(net):
    info("*** Stopping network\n")
    net.stop()
    os.system("pkill -f http.server")
    os.system("pkill -f quic_server.py")

def main():
    setLogLevel('info')
    net, server, client = setup_network()

    with open("results.csv", "w") as f:
        f.write("Protocol,Delay (s),Data Rate (KB/s)\n")

    for proto in ["HLS", "MPEG-DASH", "QUIC"]:
        simulate_protocol(net, server, client, proto)
        time.sleep(3)

    cleanup(net)

if __name__ == '__main__':
    main()
