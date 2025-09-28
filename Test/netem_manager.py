import os
import subprocess
import time
import json
from pathlib import Path

class NetworkEmulator:
    def __init__(self, interface='c1-eth0'):
        self.interface = interface
    
    def clear_rules(self):
        """Clear existing tc rules"""
        try:
            subprocess.run(['sudo', 'tc', 'qdisc', 'del', 'dev', self.interface, 'root'], 
                          capture_output=True, timeout=10)
            time.sleep(1)
        except subprocess.TimeoutExpired:
            print("Warning: Timeout clearing tc rules")
        except Exception as e:
            print(f"Error clearing rules: {e}")
    
    def setup_netem(self, bandwidth='10mbit', delay='0ms', jitter='0ms', loss='0%', 
                   queue_size=1000, queue_algorithm='fq_codel'):
        """Setup network emulation using netem and tbf"""
        
        print(f"Setting up network emulation: {bandwidth}, {delay} delay, {jitter} jitter, {loss} loss, {queue_algorithm} queue")
        
        # Clear existing rules
        self.clear_rules()
        
        try:
            # Setup token bucket filter for bandwidth shaping
            tbf_cmd = [
                'sudo', 'tc', 'qdisc', 'add', 'dev', self.interface, 'root', 
                'handle', '1:', 'tbf', 
                'rate', bandwidth,
                'burst', '32k',
                'latency', '400ms'
            ]
            subprocess.run(tbf_cmd, check=True, timeout=30)
            
            # Setup netem for delay, jitter, loss
            if jitter == '0ms':
                delay_param = delay
            else:
                delay_param = f'{delay} {jitter}'
            
            netem_cmd = [
                'sudo', 'tc', 'qdisc', 'add', 'dev', self.interface, 
                'parent', '1:1', 'handle', '10:', 'netem',
                'delay', delay_param,
                'loss', loss
            ]
            
            if queue_algorithm == 'fq_codel':
                netem_cmd.extend(['fq_codel', 'limit', str(queue_size), 'target', '5ms', 'interval', '100ms'])
            else:
                netem_cmd.extend(['pfifo', 'limit', str(queue_size)])
            
            subprocess.run(netem_cmd, check=True, timeout=30)
            
            print("Network emulation setup completed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error setting up network emulation: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("Timeout setting up network emulation")
            return False
    
    def create_background_traffic(self, protocol='tcp', duration=60, bandwidth='5mbit', flows=1):
        """Create background traffic using iperf3"""
        print(f"Creating {flows} {protocol} background flow(s) at {bandwidth} for {duration}s")
        
        try:
            # Start iperf3 server on background server (s3)
            server_cmd = ['iperf3', '-s', '-D', '-p', '5201']
            subprocess.Popen(server_cmd)
            time.sleep(2)
            
            # Start iperf3 clients
            client_procs = []
            for i in range(flows):
                if protocol == 'tcp':
                    client_cmd = [
                        'iperf3', '-c', '10.0.0.3', '-p', '5201', '-t', str(duration), 
                        '-b', bandwidth, '--logfile', f'background_tcp_flow_{i}.log'
                    ]
                else:  # udp
                    client_cmd = [
                        'iperf3', '-c', '10.0.0.3', '-p', '5201', '-u', '-t', str(duration),
                        '-b', bandwidth, '--logfile', f'background_udp_flow_{i}.log'
                    ]
                
                proc = subprocess.Popen(client_cmd)
                client_procs.append(proc)
                time.sleep(0.5)  # Stagger start times
            
            return client_procs
            
        except Exception as e:
            print(f"Error creating background traffic: {e}")
            return []
    
    def get_current_config(self):
        """Get current network configuration"""
        try:
            result = subprocess.run(['sudo', 'tc', 'qdisc', 'show', 'dev', self.interface], 
                                  capture_output=True, text=True, timeout=10)
            return result.stdout
        except Exception as e:
            print(f"Error getting current config: {e}")
            return ""

# Test scenario definitions
SCENARIOS = {
    # Bandwidth variations
    'bw_2mbit': {'bandwidth': '2mbit', 'delay': '10ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    'bw_5mbit': {'bandwidth': '5mbit', 'delay': '10ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    'bw_10mbit': {'bandwidth': '10mbit', 'delay': '10ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    'bw_20mbit': {'bandwidth': '20mbit', 'delay': '10ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    
    # Delay variations
    'delay_10ms': {'bandwidth': '10mbit', 'delay': '10ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    'delay_40ms': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    'delay_80ms': {'bandwidth': '10mbit', 'delay': '80ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    
    # Jitter variations
    'jitter_0ms': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '0ms', 'loss': '0%', 'queue': 'fq_codel'},
    'jitter_10ms': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '0%', 'queue': 'fq_codel'},
    'jitter_30ms': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '30ms', 'loss': '0%', 'queue': 'fq_codel'},
    
    # Loss variations
    'loss_0p': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '0%', 'queue': 'fq_codel'},
    'loss_0.1p': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '0.1%', 'queue': 'fq_codel'},
    'loss_1p': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '1%', 'queue': 'fq_codel'},
    'loss_3p': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '3%', 'queue': 'fq_codel'},
    
    # Queue variations
    'queue_fq_codel': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '1%', 'queue': 'fq_codel'},
    'queue_pfifo_small': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '1%', 'queue': 'pfifo', 'queue_size': 100},
    'queue_pfifo_large': {'bandwidth': '10mbit', 'delay': '40ms', 'jitter': '10ms', 'loss': '1%', 'queue': 'pfifo', 'queue_size': 1000},
}

def test_netem():
    """Test network emulation setup"""
    netem = NetworkEmulator()
    
    for scenario_name, params in list(SCENARIOS.items())[:2]:  # Test first 2 scenarios
        print(f"\n=== Testing {scenario_name} ===")
        success = netem.setup_netem(**params)
        if success:
            current_config = netem.get_current_config()
            print(f"Current config:\n{current_config}")
        time.sleep(2)

if __name__ == "__main__":
    test_netem()