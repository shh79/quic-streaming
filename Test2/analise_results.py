from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Patch
import numpy as np
from datetime import datetime
import json

def findFile(folder, pattern):
    return f"./{list(Path(f'./{folder}').glob(f'{pattern}*'))[0]}"

def parseQlogForRtt(qlogFilePath):
    """
    Parse qlog file to extract RTT measurements from ACK frames and packet timing
    """
    with open(qlogFilePath, 'r') as f:
        qlog_data = json.load(f)
    
    rtt_events = []
    
    # qlog structure: traces -> events
    if 'traces' in qlog_data:
        traces = qlog_data['traces']
    else:
        traces = [qlog_data]  # Handle different qlog formats
    
    for trace in traces:
        if 'events' not in trace:
            continue
            
        for event in trace['events']:
            if len(event) >= 3:
                timestamp, category, event_type = event[0], event[1], event[2]
                
                # Look for ACK frames and packet loss events
                if (category == "transport" and 
                    event_type in ["packet_received", "packet_sent", "metrics_updated"]):
                    
                    data = event[3] if len(event) > 3 else {}
                    
                    # Extract RTT from metrics_updated
                    if (event_type == "metrics_updated" and 
                        "latest_rtt" in data.get("metrics", {})):
                        rtt_ms = data["metrics"]["latest_rtt"]
                        rtt_events.append({
                            'timestamp': timestamp,
                            'rtt_ms': rtt_ms,
                            'event_type': 'latest_rtt'
                        })
                    
                    # Extract from ACK frames in packet_received
                    elif event_type == "packet_received" and "frames" in data:
                        for frame in data["frames"]:
                            if frame.get("frame_type") == "ack":
                                ack_delay = frame.get("ack_delay", 0)
                                # Calculate RTT from ACK timing (simplified)
                                rtt_events.append({
                                    'timestamp': timestamp,
                                    'rtt_ms': ack_delay * 1000,  # Convert to ms
                                    'event_type': 'ack_delay'
                                })
    
    return pd.DataFrame(rtt_events)

def calculateRttFromPackets(qlogFilePath):
    """
    More sophisticated RTT calculation by tracking packet send/receive times
    """
    with open(qlogFilePath, 'r') as f:
        qlog_data = json.load(f)
    
    sent_packets = {}
    rtt_measurements = []
    
    if 'traces' in qlog_data:
        traces = qlog_data['traces']
    else:
        traces = [qlog_data]
    
    for trace in traces:
        if 'events' not in trace:
            continue
            
        for event in trace['events']:
            if len(event) < 3:
                continue

            print(event)
                
            timestamp, category, event_type = event[0], event[1], event[2]
            data = event[3] if len(event) > 3 else {}
            
            # Track sent packets
            if (category == "transport" and event_type == "packet_sent" and 
                "header" in data and "packet_number" in data["header"]):
                
                packet_num = data["header"]["packet_number"]
                sent_packets[packet_num] = {
                    'send_time': timestamp,
                    'packet_type': data.get("frames", [{}])[0].get("frame_type", "unknown") if data.get("frames") else "unknown"
                }
            
            # Calculate RTT when ACK is received
            elif (category == "transport" and event_type == "packet_received" and 
                  "frames" in data):
                
                for frame in data["frames"]:
                    if frame.get("frame_type") == "ack" and "acked_ranges" in frame:
                        for ack_range in frame["acked_ranges"]:
                            if isinstance(ack_range, list) and len(ack_range) == 2:
                                start, end = ack_range
                                for packet_num in range(start, end + 1):
                                    if packet_num in sent_packets:
                                        send_time = sent_packets[packet_num]['send_time']
                                        rtt_ms = (timestamp - send_time) * 1000  # Convert to ms
                                        
                                        if rtt_ms > 0:  # Valid RTT measurement
                                            rtt_measurements.append({
                                                'timestamp': timestamp,
                                                'rtt_ms': rtt_ms,
                                                'packet_number': packet_num,
                                                'event_type': 'calculated_rtt'
                                            })
    
    return pd.DataFrame(rtt_measurements)

def generateRttPlot(quicQlogPath, dash):
    """
    Generate RTT vs Time plot from qlog file, with optional DASH comparison
    """
    # Set style
    sns.set_style("whitegrid")
    
    # Parse qlog for RTT
    print("Parsing qlog file for RTT measurements...")
    quic_rtt_df = calculateRttFromPackets(quicQlogPath)
    
    if quic_rtt_df.empty:
        print("No RTT measurements found in qlog, trying alternative method...")
        quic_rtt_df = parseQlogForRtt(quicQlogPath)
    
    if quic_rtt_df.empty:
        print("Warning: No RTT data could be extracted from qlog file")
        return
    
    # Convert timestamp to datetime and normalize
    quic_rtt_df['timestamp_dt'] = pd.to_datetime(quic_rtt_df['timestamp'], unit='ms', errors='coerce')
    if quic_rtt_df['timestamp_dt'].isna().all():
        # If timestamp is not in ms, try seconds
        quic_rtt_df['timestamp_dt'] = pd.to_datetime(quic_rtt_df['timestamp'], unit='s', errors='coerce')
    
    # Remove invalid timestamps
    quic_rtt_df = quic_rtt_df.dropna(subset=['timestamp_dt'])
    
    # Normalize time to start from 0
    min_time = quic_rtt_df['timestamp_dt'].min()
    quic_rtt_df['normalized_time'] = (quic_rtt_df['timestamp_dt'] - min_time).dt.total_seconds()
    
    # Create figure
    plt.figure(figsize=(15, 8))
    
    # Plot QUIC RTT
    plt.plot(quic_rtt_df['normalized_time'], quic_rtt_df['rtt_ms'], 
             marker='o', linewidth=2, markersize=4, alpha=0.7,
             label='QUIC RTT', color='#1f77b4')
    
    # Add DASH RTT if provided
    dash_df = dash
    dash_df['timestamp'] = pd.to_datetime(dash_df['timestamp'])
        
    # Standardize RTT column name
    rtt_col = None
    for col in ['rtt_sec', 'rtt_estimate_sec', 'rtt']:
        if col in dash_df.columns:
            rtt_col = col
            break
        
    if rtt_col:
        dash_df['normalized_time'] = (dash_df['timestamp'] - dash_df['timestamp'].min()).dt.total_seconds()
        plt.plot(dash_df['normalized_time'], dash_df[rtt_col] * 1000,  # Convert to ms
                 marker='s', linewidth=2, markersize=4, alpha=0.7,
                 label='DASH RTT', color='#ff7f0e')
    
    plt.title('Round Trip Time (RTT) vs Time', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Time from Session Start (seconds)', fontsize=12)
    plt.ylabel('RTT (milliseconds)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    
    # Add statistics
    if not quic_rtt_df.empty:
        avg_rtt = quic_rtt_df['rtt_ms'].mean()
        max_rtt = quic_rtt_df['rtt_ms'].max()
        min_rtt = quic_rtt_df['rtt_ms'].min()
        std_rtt = quic_rtt_df['rtt_ms'].std()
        
        stats_text = f"""QUIC RTT Statistics:
                        Average: {avg_rtt:.1f} ms
                        Min: {min_rtt:.1f} ms
                        Max: {max_rtt:.1f} ms
                        Std: {std_rtt:.1f} ms"""
        
        plt.annotate(stats_text, xy=(0.02, 0.95), xycoords='axes fraction',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7),
                    fontsize=10, fontfamily='monospace')
    
    plt.tight_layout()
    
    save_path = "./plots/rtt_time.png"
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"RTT plot saved to: {save_path}")
    
    plt.show()
    
    return quic_rtt_df

def generateBitratePlot(quic, dash):
    # Set style
    sns.set_style("whitegrid")

    # Read CSV files
    df1 = quic
    df2 = dash

    # Add protocol identifiers
    df1['protocol'] = 'QUIC'
    df2['protocol'] = 'DASH'

    # Standardize bitrate column name
    if 'bitrate_bps' in df2.columns:
        df2 = df2.rename(columns={'bitrate_bps': 'bitrate'})

    # Convert timestamps
    df1['timestamp'] = pd.to_datetime(df1['timestamp'])
    df2['timestamp'] = pd.to_datetime(df2['timestamp'])

    # Normalize timestamps to start from 0 for both datasets
    df1['normalized_time'] = (df1['timestamp'] - df1['timestamp'].iloc[0]).dt.total_seconds()
    df2['normalized_time'] = (df2['timestamp'] - df2['timestamp'].iloc[0]).dt.total_seconds()

    # Sort by normalized time
    df1 = df1.sort_values('normalized_time')
    df2 = df2.sort_values('normalized_time')

    # Create figure
    plt.figure(figsize=(15, 8))

    # Plot with enhanced styling using normalized time
    plt.plot(df1['normalized_time'], df1['bitrate'], 
            marker='o', linewidth=2.5, markersize=6,
            label='QUIC', color='#1f77b4', alpha=0.8)

    plt.plot(df2['normalized_time'], df2['bitrate'], 
            marker='s', linewidth=2.5, markersize=6,
            label='DASH', color='#ff7f0e', alpha=0.8)

    plt.title('Bitrate Evolution: QUIC vs DASH Protocol (Time Normalized)', 
            fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Time from Session Start (seconds)', fontsize=12)
    plt.ylabel('Bitrate (bps)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)

    # Format axes
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}kbps'))

    # Add some statistics to the plot
    max_bitrate1 = df1['bitrate'].max()
    max_bitrate2 = df2['bitrate'].max()
    avg_bitrate1 = df1['bitrate'].mean()
    avg_bitrate2 = df2['bitrate'].mean()

    plt.annotate(f'Max QUIC: {max_bitrate1/1000:.0f}kbps\nAvg QUIC: {avg_bitrate1/1000:.0f}kbps', 
                xy=(0.02, 0.95), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7),
                fontsize=9)

    plt.annotate(f'Max DASH: {max_bitrate2/1000:.0f}kbps\nAvg DASH: {avg_bitrate2/1000:.0f}kbps', 
                xy=(0.02, 0.80), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcoral", alpha=0.7),
                fontsize=9)

    # Print time range information
    print(f"QUIC session duration: {df1['normalized_time'].max():.2f} seconds")
    print(f"DASH session duration: {df2['normalized_time'].max():.2f} seconds")
    print(f"QUIC data points: {len(df1)}")
    print(f"DASH data points: {len(df2)}")

    plt.tight_layout()

    save_path = './plots/bitrate_time.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Bitrate plot saved to: {save_path}")

    # plt.show()

def generateBufferLevelPlot(quic, dash):
    # Set style
    sns.set_style("whitegrid")

    # Read CSV files
    df1 = quic
    df2 = dash

    # Add protocol identifiers
    df1['protocol'] = 'QUIC'
    df2['protocol'] = 'DASH'

    # Convert timestamps
    df1['timestamp'] = pd.to_datetime(df1['timestamp'])
    df2['timestamp'] = pd.to_datetime(df2['timestamp'])

    # Normalize timestamps to start from 0 for both datasets
    df1['normalized_time'] = (df1['timestamp'] - df1['timestamp'].iloc[0]).dt.total_seconds()
    df2['normalized_time'] = (df2['timestamp'] - df2['timestamp'].iloc[0]).dt.total_seconds()

    # Sort by normalized time
    df1 = df1.sort_values('normalized_time')
    df2 = df2.sort_values('normalized_time')

    # Create figure
    plt.figure(figsize=(15, 8))

    # Plot buffer levels with enhanced styling
    plt.plot(df1['normalized_time'], df1['buffer_level_sec'], 
            marker='o', linewidth=2.5, markersize=6,
            label='QUIC', color='#1f77b4', alpha=0.8)

    plt.plot(df2['normalized_time'], df2['buffer_level_sec'], 
            marker='s', linewidth=2.5, markersize=6,
            label='DASH', color='#ff7f0e', alpha=0.8)

    plt.title('Buffer Level Evolution: QUIC vs DASH Protocol', 
            fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Time from Session Start (seconds)', fontsize=12)
    plt.ylabel('Buffer Level (seconds)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)

    # Add some statistics to the plot
    max_buffer1 = df1['buffer_level_sec'].max()
    max_buffer2 = df2['buffer_level_sec'].max()
    avg_buffer1 = df1['buffer_level_sec'].mean()
    avg_buffer2 = df2['buffer_level_sec'].mean()

    plt.annotate(f'Max QUIC: {max_buffer1:.1f}s\nAvg QUIC: {avg_buffer1:.1f}s', 
                xy=(0.02, 0.95), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7),
                fontsize=9)

    plt.annotate(f'Max DASH: {max_buffer2:.1f}s\nAvg DASH: {avg_buffer2:.1f}s', 
                xy=(0.02, 0.85), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcoral", alpha=0.7),
                fontsize=9)

    # Add a horizontal line at buffer=0 for reference
    plt.axhline(y=0, color='red', linestyle='--', alpha=0.5, label='Zero Buffer')

    plt.tight_layout()
    
    # Save the plot if save_path is provided
    save_path = './plots/buffer_level_time.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Buffer level plot saved to: {save_path}")
    
    # plt.show()

def generateThroughputPlot(quic, dash):
    # Set style
    sns.set_style("whitegrid")

    # Read CSV files
    df1 = quic
    df2 = dash

    # Add protocol identifiers
    df1['protocol'] = 'QUIC'
    df2['protocol'] = 'DASH'

    # Convert timestamps
    df1['timestamp'] = pd.to_datetime(df1['timestamp'])
    df2['timestamp'] = pd.to_datetime(df2['timestamp'])

    # Normalize timestamps to start from 0 for both datasets
    df1['normalized_time'] = (df1['timestamp'] - df1['timestamp'].iloc[0]).dt.total_seconds()
    df2['normalized_time'] = (df2['timestamp'] - df2['timestamp'].iloc[0]).dt.total_seconds()

    # Sort by normalized time
    df1 = df1.sort_values('normalized_time')
    df2 = df2.sort_values('normalized_time')

    # Create figure
    plt.figure(figsize=(15, 8))

    # Plot throughput with enhanced styling
    plt.plot(df1['normalized_time'], df1['throughput_bps'], 
            marker='o', linewidth=2.5, markersize=6,
            label='QUIC Throughput', color='#1f77b4', alpha=0.8)

    plt.plot(df2['normalized_time'], df2['throughput_bps'], 
            marker='s', linewidth=2.5, markersize=6,
            label='DASH Throughput', color='#ff7f0e', alpha=0.8)

    # Plot smoothed throughput as dashed lines
    plt.plot(df1['normalized_time'], df1['smoothed_throughput_bps'], 
            linestyle='--', linewidth=2,
            label='QUIC Smoothed', color='#1f77b4', alpha=0.6)

    plt.plot(df2['normalized_time'], df2['smoothed_throughput_bps'], 
            linestyle='--', linewidth=2,
            label='DASH Smoothed', color='#ff7f0e', alpha=0.6)

    plt.title('Throughput Evolution: QUIC vs DASH Protocol', 
            fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Time from Session Start (seconds)', fontsize=12)
    plt.ylabel('Throughput (bps)', fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)

    # Format y-axis for better readability
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000000:.1f}Mbps' if x >= 1000000 else f'{x/1000:.0f}kbps'))

    # Add statistics to the plot
    max_throughput1 = df1['throughput_bps'].max()
    max_throughput2 = df2['throughput_bps'].max()
    avg_throughput1 = df1['throughput_bps'].mean()
    avg_throughput2 = df2['throughput_bps'].mean()

    plt.annotate(f'QUIC:\nMax: {max_throughput1/1000000:.1f}Mbps\nAvg: {avg_throughput1/1000000:.1f}Mbps', 
                xy=(0.02, 0.95), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7),
                fontsize=9)

    plt.annotate(f'DASH:\nMax: {max_throughput2/1000000:.1f}Mbps\nAvg: {avg_throughput2/1000000:.1f}Mbps', 
                xy=(0.02, 0.80), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcoral", alpha=0.7),
                fontsize=9)

    plt.tight_layout()
    
    # Save the plot if save_path is provided
    save_path = './plots/throughput_time.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Throughput plot saved to: {save_path}")
    
    # plt.show()

def generateStallTimelinePlot(quic, dash):
    # Set style
    sns.set_style("whitegrid")

    # Read and process data
    df1 = quic
    df2 = dash

    # Add protocol identifiers
    df1['protocol'] = 'QUIC'
    df2['protocol'] = 'DASH'

    # Convert timestamps
    df1['timestamp'] = pd.to_datetime(df1['timestamp'])
    df2['timestamp'] = pd.to_datetime(df2['timestamp'])

    # Normalize timestamps
    df1['normalized_time'] = (df1['timestamp'] - df1['timestamp'].iloc[0]).dt.total_seconds()
    df2['normalized_time'] = (df2['timestamp'] - df2['timestamp'].iloc[0]).dt.total_seconds()

    # Sort by normalized time
    df1 = df1.sort_values('normalized_time')
    df2 = df2.sort_values('normalized_time')

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))

    # Plot settings
    bar_height = 0.3
    y_positions = {'QUIC': 1, 'DASH': 2}
    colors = {'QUIC': '#ff6b6b', 'DASH': '#4ecdc4'}

    # Function to find rebuffering periods
    def find_rebuffering_periods(df):
        periods = []
        in_rebuffer = False
        start_time = None
        
        for i, row in df.iterrows():
            if row['is_rebuffering'] and not in_rebuffer:
                in_rebuffer = True
                start_time = row['normalized_time']
            elif not row['is_rebuffering'] and in_rebuffer:
                in_rebuffer = False
                end_time = row['normalized_time']
                periods.append((start_time, end_time))
        
        if in_rebuffer:
            periods.append((start_time, df['normalized_time'].max()))
            
        return periods

    # Plot 1: Gantt chart
    quic_periods = find_rebuffering_periods(df1)
    dash_periods = find_rebuffering_periods(df2)

    # Plot rebuffering periods
    for periods, protocol in [(quic_periods, 'QUIC'), (dash_periods, 'DASH')]:
        for start, end in periods:
            ax1.barh(y_positions[protocol], end - start, left=start, 
                    height=bar_height, color=colors[protocol], alpha=0.8,
                    edgecolor='black', linewidth=1)

    # Plot playback periods
    for protocol, df, periods in [('QUIC', df1, quic_periods), ('DASH', df2, dash_periods)]:
        playback_start = df['normalized_time'].min()
        for rebuffer_start, rebuffer_end in periods:
            if rebuffer_start > playback_start:
                ax1.barh(y_positions[protocol], rebuffer_start - playback_start, 
                        left=playback_start, height=bar_height, color='#2ecc71', 
                        alpha=0.7, edgecolor='black', linewidth=0.5)
            playback_start = rebuffer_end
        
        # Final playback period
        if playback_start < df['normalized_time'].max():
            ax1.barh(y_positions[protocol], df['normalized_time'].max() - playback_start, 
                    left=playback_start, height=bar_height, color='#2ecc71', 
                    alpha=0.7, edgecolor='black', linewidth=0.5)

    ax1.set_yticks(list(y_positions.values()))
    ax1.set_yticklabels(list(y_positions.keys()))
    ax1.set_xlabel('Time from Session Start (seconds)', fontsize=12)
    ax1.set_title('Stall Timeline: Rebuffering Events', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='x')

    # Create legend
    legend_elements = [
        Patch(facecolor='#ff6b6b', alpha=0.8, label='Rebuffering'),
        Patch(facecolor='#2ecc71', alpha=0.7, label='Playback')
    ]
    ax1.legend(handles=legend_elements, loc='upper right')

    # Plot 2: Buffer level with rebuffering highlights
    ax2.plot(df1['normalized_time'], df1['buffer_level_sec'], 
             label='QUIC Buffer', color='#1f77b4', linewidth=2)
    ax2.plot(df2['normalized_time'], df2['buffer_level_sec'], 
             label='DASH Buffer', color='#ff7f0e', linewidth=2)

    # Highlight rebuffering periods on buffer plot
    for periods, color in [(quic_periods, '#1f77b4'), (dash_periods, '#ff7f0e')]:
        for start, end in periods:
            ax2.axvspan(start, end, alpha=0.2, color=color)

    ax2.set_xlabel('Time from Session Start (seconds)', fontsize=12)
    ax2.set_ylabel('Buffer Level (seconds)', fontsize=12)
    ax2.set_title('Buffer Level with Rebuffering Periods Highlighted', 
                  fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='red', linestyle='--', alpha=0.5, label='Zero Buffer')

    plt.tight_layout()

    # Add overall statistics
    total_rebuffer_quic = sum(end - start for start, end in quic_periods)
    total_rebuffer_dash = sum(end - start for start, end in dash_periods)
    
    stats_text = f"""Overall Statistics:
                    QUIC: {len(quic_periods)} rebuffering events
                    Total rebuffering: {total_rebuffer_quic:.3f}s
                    DASH: {len(dash_periods)} rebuffering events  
                    Total rebuffering: {total_rebuffer_dash:.3f}s"""
    
    fig.text(0.02, 0.02, stats_text, fontfamily='monospace', fontsize=10,
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    save_path = './plots/stall_timeline(gantt-like).png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Stall timeline saved to: {save_path}")
    
    # plt.show()

    return quic_periods, dash_periods

if __name__ == "__main__":
    quic = pd.read_csv(findFile("results", "quic_metrics"))
    dash = pd.read_csv(findFile("results", "dash_metrics"))
    
    # generateBitratePlot(quic, dash)
    # generateBufferLevelPlot(quic, dash)
    # generateThroughputPlot(quic, dash)
    # generateStallTimelinePlot(quic, dash)
    generateRttPlot(findFile("qlog", "packet_trace"), dash)
