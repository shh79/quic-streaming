import subprocess
import time
import json
from pathlib import Path

class NetworkEmulator:
    def __init__(self, interface='c1-eth0'):
        self.interface = interface
    
    def clear_rules(self):
        """Clear existing tc rules safely"""
        print("Clearing existing tc rules...")
        commands = [
            ['sudo', 'tc', 'qdisc', 'del', 'dev', self.interface, 'root'],
            ['sudo', 'tc', 'qdisc', 'del', 'dev', self.interface, 'ingress'],
        ]
        
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"  Cleared: {' '.join(cmd)}")
            except:
                pass
        
        time.sleep(1)
    
    def setup_netem(self, bandwidth='10mbit', delay='0ms', jitter='0ms', loss='0%', **kwargs):
        """Simple and reliable network emulation setup"""
        
        print(f"Setting up network emulation:")
        print(f"  Bandwidth: {bandwidth}")
        print(f"  Delay: {delay}")
        print(f"  Jitter: {jitter}") 
        print(f"  Loss: {loss}")
        
        # Clear existing rules first
        self.clear_rules()
        time.sleep(2)
        
        try:
            # Build delay parameter
            if jitter != '0ms':
                delay_param = f'{delay} {jitter} distribution normal'
            else:
                delay_param = delay
            
            # Method 1: Simple netem with all parameters
            netem_cmd = [
                'sudo', 'tc', 'qdisc', 'add', 'dev', self.interface, 'root',
                'netem', 'rate', bandwidth, 'delay', delay_param, 'loss', loss
            ]
            
            print(f"Running: {' '.join(netem_cmd)}")
            result = subprocess.run(netem_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✓ Network emulation setup successful")
                self.show_current_rules()
                return True
            else:
                print(f"Method 1 failed: {result.stderr}")
                
                # Method 2: Try without rate limiting
                netem_cmd2 = [
                    'sudo', 'tc', 'qdisc', 'add', 'dev', self.interface, 'root',
                    'netem', 'delay', delay_param, 'loss', loss
                ]
                
                print(f"Trying method 2: {' '.join(netem_cmd2)}")
                result2 = subprocess.run(netem_cmd2, capture_output=True, text=True, timeout=30)
                
                if result2.returncode == 0:
                    print("✓ Network emulation setup successful (without rate limiting)")
                    self.show_current_rules()
                    return True
            
            print("✗ Network emulation setup failed")
            return False
            
        except Exception as e:
            print(f"Error setting up network emulation: {e}")
            return False
    
    def show_current_rules(self):
        """Show current tc rules"""
        try:
            result = subprocess.run(
                ['sudo', 'tc', 'qdisc', 'show', 'dev', self.interface],
                capture_output=True, text=True, timeout=10
            )
            print("Current network rules:")
            print(result.stdout)
            return result.stdout
        except Exception as e:
            print(f"Error showing rules: {e}")
            return ""

# Network scenarios
SCENARIOS = {
    'good': {
        'bandwidth': '10mbit',
        'delay': '10ms', 
        'jitter': '0ms',
        'loss': '0%'
    },
    'medium': {
        'bandwidth': '5mbit',
        'delay': '40ms',
        'jitter': '10ms', 
        'loss': '0.1%'
    },
    'poor': {
        'bandwidth': '2mbit',
        'delay': '80ms',
        'jitter': '20ms',
        'loss': '1%'
    },
    'very_poor': {
        'bandwidth': '1mbit', 
        'delay': '100ms',
        'jitter': '30ms',
        'loss': '3%'
    }
}

def test_netem():
    """Test network emulation"""
    netem = NetworkEmulator()
    
    print("Testing network emulation setup...")
    success = netem.setup_netem(**SCENARIOS['good'])
    
    if success:
        print("✓ Network emulation test passed")
    else:
        print("✗ Network emulation test failed")
    
    netem.clear_rules()

if __name__ == "__main__":
    test_netem()