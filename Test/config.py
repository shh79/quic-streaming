# Configuration file for streaming tests

# Network scenarios
BANDWIDTHS = ['2mbit', '5mbit', '10mbit', '20mbit']
DELAYS = ['10ms', '40ms', '80ms']
JITTERS = ['0ms', '10ms', '30ms']
LOSS_RATES = ['0%', '0.1%', '1%', '3%']
QUEUE_TYPES = ['fq_codel', 'pfifo']

# QUIC configurations
QUIC_CONGESTION_CONTROLS = ['cubic', 'reno']  # Add 'bbr' if available
QUIC_VIDEOS = ['sample_240p.mp4', 'sample_480p.mp4', 'sample_720p.mp4', 'sample_1080p.mp4']

# DASH configurations
DASH_SEGMENT_LENGTHS = [2, 4, 6]
DASH_ABR_ALGORITHMS = ['throughput', 'buffer', 'hybrid']
DASH_BUFFER_TARGETS = [10, 15, 20]

# Test parameters
TEST_DURATION = 60  # seconds
COOLDOWN_PERIOD = 5  # seconds between tests

# Background traffic
BACKGROUND_FLOWS = [1, 3, 5]
BACKGROUND_BANDWIDTHS = ['1mbit', '3mbit', '5mbit']
BACKGROUND_DURATION = 70  # Slightly longer than test duration

# Analysis settings
METRICS_OF_INTEREST = [
    'startup_delay',
    'average_bitrate',
    'rebuffering_events',
    'total_rebuffering_time',
    'bitrate_switches',
    'transfer_rate_kbps'
]

# Plot settings
PLOT_STYLE = 'seaborn-v0_8'
FIGURE_SIZE = (12, 8)
DPI = 300