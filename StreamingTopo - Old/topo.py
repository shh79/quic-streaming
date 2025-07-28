from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.term import makeTerm  # 📌 برای باز کردن ترمینال

class StreamingTopo(Topo):
    def build(self):
        # Router
        router = self.addSwitch('r1')

        # Servers
        s1 = self.addHost('s1', ip='10.0.0.1/24')  # QUIC
        s2 = self.addHost('s2', ip='10.0.0.2/24')  # MPEG-DASH
        s3 = self.addHost('s3', ip='10.0.0.3/24')  # HLS

        # Client
        c1 = self.addHost('c1', ip='10.0.0.100/24')

        # Links
        self.addLink(s1, router, bw=10, delay='10ms')
        self.addLink(s2, router, bw=10, delay='10ms')
        self.addLink(s3, router, bw=10, delay='10ms')
        self.addLink(c1, router, bw=10, delay='10ms')


def run():
    topo = StreamingTopo()
    net = Mininet(topo=topo, link=TCLink)
    net.start()

    print("✅ Network started. Assigning routes...")

    client = net.get('c1')
    client.cmd('ip route add 10.0.0.0/24 dev c1-eth0')

    # باز کردن کنسول برای تمام نودها
    for node_name in ['s1', 's2', 's3', 'c1', 'r1']:
        node = net.get(node_name)
        makeTerm(node, title=node_name)

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
