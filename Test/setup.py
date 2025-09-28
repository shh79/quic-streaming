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
        'results',
        'certificates'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"Created directory: {directory}")
    
    # Generate sample video files (placeholder)
    print("\nCreating sample video files...")
    sample_videos = {
        'sample_240p.mp4': 10 * 1024 * 1024,  # 10MB
        'sample_480p.mp4': 20 * 1024 * 1024,  # 20MB
        'sample_720p.mp4': 50 * 1024 * 1024,  # 50MB
        'sample_1080p.mp4': 100 * 1024 * 1024, # 100MB
    }
    
    for video_name, size in sample_videos.items():
        video_path = Path('videos') / video_name
        if not video_path.exists():
            # Create dummy video file
            with open(video_path, 'wb') as f:
                f.write(b'0' * size)
            print(f"Created sample video: {video_name} ({size//1024//1024}MB)")
    
    # Generate SSL certificates for QUIC
    print("\nGenerating SSL certificates for QUIC...")
    cert_path = Path('cert.pem')
    key_path = Path('key.pem')
    
    if not cert_path.exists() or not key_path.exists():
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-keyout', 'key.pem', '-out', 'cert.pem',
            '-days', '365', '-nodes', '-subj', '/CN=localhost'
        ], capture_output=True)
        print("Generated SSL certificates")
    
    # Check required tools
    print("\nChecking required tools...")
    required_tools = ['tc', 'iperf3', 'python3']
    
    for tool in required_tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True)
            print(f"✓ {tool} is available")
        except:
            print(f"✗ {tool} is not available")
    
    # Install Python dependencies
    print("\nInstalling Python dependencies...")
    dependencies = [
        'aioquic',
        'requests',
        'matplotlib',
        'seaborn',
        'pandas',
        'numpy'
    ]
    
    for dep in dependencies:
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)
            print(f"✓ Installed {dep}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {dep}")
    
    print("\nSetup completed!")
    print("\nNext steps:")
    print("1. Place your actual video files in the 'videos' directory")
    print("2. Place DASH content in 'dash_content' directory")
    print("3. Run Mininet topology: sudo python3 topo.py")
    print("4. Run tests: python3 test_runner.py")
    print("5. Analyze results: python3 analyze_results.py")

if __name__ == "__main__":
    setup_environment()