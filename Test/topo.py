from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node, Controller, OVSController
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.term import makeTerm

class StreamingTopo(Topo):
    def build(self):
        # Servers
        s1 = self.addHost('s1', ip='10.0.0.1/24')  # QUIC Server
        s2 = self.addHost('s2', ip='10.0.0.2/24')  # DASH Server
        s3 = self.addHost('s3', ip='10.0.0.3/24')  # Background Server

        # Clients
        c1 = self.addHost('c1', ip='10.0.0.100/24') # Main Client
        c2 = self.addHost('c2', ip='10.0.0.200/24') # Background Client

        # Router
        router = self.addSwitch('r1')

        # Links with bottleneck on client side
        self.addLink(s1, router, bw=100)  # High bandwidth for servers
        self.addLink(s2, router, bw=100)
        self.addLink(s3, router, bw=100)
        self.addLink(c1, router, bw=100)  # Will be shaped by netem
        self.addLink(c2, router, bw=100)

def run():
    topology = StreamingTopo()
    net = Mininet(topo=topology, link=TCLink, controller=OVSController)
    net.start()

    print("Network started. Assigning routes...")

    # Setup routes
    for node_name in ['s1', 's2', 's3', 'c1', 'c2']:
        node = net.get(node_name)
        node.cmd(f'ip route add 10.0.0.0/24 dev {node_name}-eth0')

    print("Starting terminals...")
    for node_name in ['s1', 's2', 's3', 'c1', 'c2']:
        node = net.get(node_name)
        makeTerm(node, title=node_name)

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()