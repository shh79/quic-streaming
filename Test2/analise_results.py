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

def parseRttFromQlog(qlog_file_path):
    """
    Extract RTT measurements from qlog file with enhanced logging
    """
    try:
        with open(qlog_file_path, 'r') as f:
            qlog_data = json.load(f)
    except Exception as e:
        print(f"Error reading qlog file: {e}")
        return pd.DataFrame()
    
    rtt_measurements = []
    
    # Extract events from qlog structure
    events = []
    if 'traces' in qlog_data:
        for trace in qlog_data['traces']:
            events.extend(trace.get('events', []))
    elif 'events' in qlog_data:
        events = qlog_data['events']
    else:
        events = qlog_data  # Assume direct list
    
    # print(f"Found {len(events)} total events in qlog")
    
    for event in events:
        try:
            try:
                data = event['data']
                timestamp = event['time']
                temp = event['name'].split(':')
                category = temp[0]
                event_type = temp[1]  
            except:
                continue
            
            # Look for metrics_updated events
            if (category == "recovery" and event_type == "metrics_updated" and isinstance(data, dict)):

                # Extract all RTT metrics
                rtt_entry = {'timestamp': timestamp}
                
                if "latest_rtt" in data:
                    rtt_entry['latest_rtt_ms'] = data["latest_rtt"]
                
                if "smoothed_rtt" in data:
                    rtt_entry['smoothed_rtt_ms'] = data["smoothed_rtt"]
                
                if "rtt_variance" in data:
                    rtt_entry['rtt_variance_ms'] = data["rtt_variance"]
                
                if "min_rtt" in data:
                    rtt_entry['min_rtt_ms'] = data["min_rtt"]
                
                # If we found any RTT metrics, add to results
                if len(rtt_entry) > 1:
                    rtt_measurements.append(rtt_entry)
                    
        except Exception as e:
            continue  # Skip malformed events
    
    # print(f"Extracted {len(rtt_measurements)} RTT measurement events")
    return pd.DataFrame(rtt_measurements)

def plotRttFromQlog(qlog_file_path):
    """
    Plot RTT vs Time from qlog file
    """
    # Parse RTT data
    rtt_df = parseRttFromQlog(qlog_file_path)
    
    if rtt_df.empty:
        print("No RTT data found in qlog file")
        return None
    
    # Process timestamps
    # Convert timestamp to seconds and normalize to start from 0
    rtt_df['time_seconds'] = rtt_df['timestamp'] / 1000  # Convert ms to seconds
    min_time = rtt_df['time_seconds'].min()
    rtt_df['normalized_time'] = rtt_df['time_seconds'] - min_time
    
    # Set style
    sns.set_style("whitegrid")
    plt.figure(figsize=(14, 8))
    
    # Determine which RTT columns are available
    rtt_columns = [col for col in rtt_df.columns if 'rtt' in col and col != 'timestamp']
    
    if not rtt_columns:
        print("No RTT columns found in data")
        return None
    
    # Plot all available RTT metrics
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    line_styles = ['-', '--', '-.', ':']
    
    for i, rtt_col in enumerate(rtt_columns):
        if i < len(colors):
            plt.plot(rtt_df['normalized_time'], rtt_df[rtt_col],
                    linewidth=2,
                    marker='o' if len(rtt_df) < 50 else '',  # Only show markers for sparse data
                    markersize=4,
                    label=rtt_col.replace('_ms', '').replace('_', ' ').title(),
                    color=colors[i],
                    linestyle=line_styles[i % len(line_styles)],
                    alpha=0.8)
    
    plt.title('QUIC RTT (Round Trip Time) vs Time', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Time from Connection Start (seconds)', fontsize=12)
    plt.ylabel('RTT (milliseconds)', fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    
    # Add statistics
    if not rtt_df.empty:
        # Use the first available RTT column for statistics
        primary_rtt_col = rtt_columns[0]
        rtt_data = rtt_df[primary_rtt_col].dropna()
        
        if not rtt_data.empty:
            stats_text = f"""RTT Statistics ({primary_rtt_col.replace('_ms', '').replace('_', ' ').title()}):
Average: {rtt_data.mean():.1f} ms
Min: {rtt_data.min():.1f} ms
Max: {rtt_data.max():.1f} ms
Std Dev: {rtt_data.std():.1f} ms
Samples: {len(rtt_data)}"""
            
            plt.annotate(stats_text, xy=(0.02, 0.95), xycoords='axes fraction',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.8),
                        fontsize=9, fontfamily='monospace')
    
    plt.tight_layout()

    save_path = './plots/qlog_rtt_time.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"RTT(Qlog) plot saved to: {save_path}")
    
    # plt.show()
    
    return rtt_df

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
    # print(f"QUIC session duration: {df1['normalized_time'].max():.2f} seconds")
    # print(f"DASH session duration: {df2['normalized_time'].max():.2f} seconds")
    # print(f"QUIC data points: {len(df1)}")
    # print(f"DASH data points: {len(df2)}")

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
    
    generateBitratePlot(quic, dash)
    generateBufferLevelPlot(quic, dash)
    generateThroughputPlot(quic, dash)
    generateStallTimelinePlot(quic, dash)
    plotRttFromQlog(findFile("qlog", "packet_trace"))
