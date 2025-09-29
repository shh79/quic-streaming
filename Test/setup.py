#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

def setup_environment():
    """Setup the testing environment"""
    print("Setting up streaming test environment...")
    
    # Create necessary directories
    directories = [
        'videos',
        'dash_content',
        'qlog',
        'results'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✓ Created directory: {directory}")
    
    # Generate sample video files
    print("\nCreating sample video files...")
    sample_videos = {
        'sample_240p.mp4': 5 * 1024 * 1024,   # 5MB
        'sample_480p.mp4': 10 * 1024 * 1024,  # 10MB
        'sample_720p.mp4': 20 * 1024 * 1024,  # 20MB
        'sample_1080p.mp4': 30 * 1024 * 1024, # 30MB
    }
    
    for video_name, size in sample_videos.items():
        video_path = Path('videos') / video_name
        if not video_path.exists():
            with open(video_path, 'wb') as f:
                f.write(b'0' * size)
            print(f"✓ Created sample video: {video_name} ({size//1024//1024}MB)")
    
    # Generate SSL certificates for QUIC
    print("\nGenerating SSL certificates for QUIC...")
    cert_path = Path('cert.pem')
    key_path = Path('key.pem')
    
    if not cert_path.exists() or not key_path.exists():
        result = subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', 'key.pem', '-out', 'cert.pem',
            '-days', '365', '-nodes', '-subj', '/CN=localhost'
        ], capture_output=True)
        
        if result.returncode == 0:
            print("✓ Generated SSL certificates")
        else:
            print("✗ Failed to generate SSL certificates")
    
    # Check required tools
    print("\nChecking required tools...")
    required_tools = ['tc', 'iperf3', 'python3']
    
    for tool in required_tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True)
            print(f"✓ {tool} is available")
        except:
            print(f"✗ {tool} is not available")
    
    print("\n✓ Setup completed!")
    print("\nNext steps:")
    print("1. Start Mininet: sudo python3 topo.py")
    print("2. In s1 terminal: python3 quic_server.py")
    print("3. In s2 terminal: python3 dash_server.py") 
    print("4. In c1 terminal: python3 test_runner.py")

if __name__ == "__main__":
    setup_environment()