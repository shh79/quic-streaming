import asyncio
import subprocess
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

async def run_quic_test():
    netem_cmd = [
        'python3', 'quic_client.py'
    ]

    result = subprocess.run(netem_cmd, capture_output=True, text=True, timeout=30)
    return (result.returncode == 0)
    
async def run_dash_test():
    netem_cmd = [
        'python3', 'dash_client.py'
    ]

    result = subprocess.run(netem_cmd, capture_output=True, text=True, timeout=30)
    return (result.returncode == 0)

async def runner(crossTraficType):
    match crossTraficType:
        case 'random':
            print("\n--- Running Random Cross Trafic ---")
            netem_cmd = [
                'python3', 'random_traffic.py'
            ]
            subprocess.Popen(netem_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        case 'worst':
            print("\n--- Running Worst Cross Trafic ---")
            netem_cmd = [
                'python3', 'worst_traffic.py'
            ]
            subprocess.Popen(netem_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print("\n--- Running QUIC Test ---")
    quic_success = await run_quic_test()
    time.sleep(3)
    
    print("\n--- Running DASH Test ---")
    dash_success = await run_dash_test()
    time.sleep(3)

    return quic_success and dash_success

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', choices=['2', '5', '10', '20'], default='20', help='Bandwidth(Mbps): 2, 5, 10, 20; default: 20Mbps')
    parser.add_argument('-d', choices=['10', '40', '80'], default='10', help='Delay(ms): 10, 40, 80; default: 10ms')
    parser.add_argument('-j', choices=['0', '10', '30'], default='0', help='Jitter(ms): 0, 10, 30; default: 0ms')
    parser.add_argument('-l', choices=['0', '0.1', '1', '3'], default='0', help='Packet-Loss(%): 0, 0.1, 1, 3; default: 0%')
    parser.add_argument('-t', choices=['none', 'random', 'worst'], default='none', help='Cross-Trafic: None, Random, Worst')
    
    args = parser.parse_args()

    netem_cmd = [
        'sudo', 'tc', 'qdisc', 'del', 'dev', 'c1-eth0', 'root'
    ]

    result = subprocess.run(netem_cmd, capture_output=True, text=True, timeout=30)
            
    if result.returncode == 0:
        print("The network emulation rules is cleared.")
    
    netem_cmd = [
        'sudo', 'tc', 'qdisc', 'add', 'dev', 'c1-eth0', 'root', 'tbf', 'rate', f'{args.b}mbit'
    ]

    result = subprocess.run(netem_cmd, capture_output=True, text=True, timeout=30)

    netem_cmd = [
        'sudo', 'tc', 'qdisc', 'add', 'dev', 'c1-eth0', 'root', 'netem', 'delay', f'{args.d}ms', f'{args.j}ms', 'loss', f'{args.l}%'
    ]

    result = subprocess.run(netem_cmd, capture_output=True, text=True, timeout=30)

    print(f"Config the link of c1-eth0 to have Bandwidth: {args.b}Mbps, Delay: {args.d}ms, Jitter: {args.j}ms, Packet-Loss: {args.l}%")
    
    success = asyncio.run(runner(args.t))
    
    if success:
        print(f"All tests on this senario(Bandwidth: {args.b}Mbps, Delay: {args.d}ms, Jitter: {args.j}ms, Packet-Loss: {args.l}%) are completed successfully!")
    
