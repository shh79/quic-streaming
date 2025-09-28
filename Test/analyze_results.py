import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np

class ResultsAnalyzer:
    def __init__(self, results_dir="results"):
        self.results_dir = Path(results_dir)
        self.df = None
        self.load_results()
    
    def load_results(self):
        """Load all test results into a DataFrame"""
        results = []
        
        for result_file in self.results_dir.glob('**/test_result.json'):
            with open(result_file, 'r') as f:
                result_data = json.load(f)
                results.append(result_data)
        
        self.df = pd.DataFrame(results)
        
        # Flatten nested structures
        if not self.df.empty:
            # Extract scenario parameters
            scenario_params = pd.json_normalize(self.df['scenario_params'])
            scenario_params.columns = [f'scenario_{col}' for col in scenario_params.columns]
            
            # Extract metrics
            metrics = pd.json_normalize(self.df['metrics'])
            metrics.columns = [f'metric_{col}' for col in metrics.columns]
            
            self.df = pd.concat([self.df, scenario_params, metrics], axis=1)
            
        print(f"Loaded {len(self.df)} test results")
    
    def plot_time_vs_bitrate(self):
        """Plot time vs bitrate for different scenarios"""
        if self.df.empty:
            print("No data to plot")
            return
        
        plt.figure(figsize=(12, 8))
        
        # Filter successful tests with bitrate data
        quic_data = self.df[self.df['protocol'] == 'QUIC']
        dash_data = self.df[self.df['protocol'] == 'DASH']
        
        # Create subplots for different network conditions
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        axes = axes.flatten()
        
        scenarios_to_plot = ['bw_10mbit', 'delay_40ms', 'loss_1p', 'jitter_10ms']
        
        for i, scenario in enumerate(scenarios_to_plot):
            if i >= len(axes):
                break
                
            ax = axes[i]
            scenario_data = self.df[self.df['scenario'] == scenario]
            
            for protocol in ['QUIC', 'DASH']:
                proto_data = scenario_data[scenario_data['protocol'] == protocol]
                if not proto_data.empty:
                    if protocol == 'QUIC':
                        bitrates = proto_data['metric_transfer_rate_kbps']
                    else:
                        bitrates = proto_data['metric_average_bitrate'] / 1000  # Convert to kbps
                    
                    ax.scatter([protocol] * len(bitrates), bitrates, alpha=0.7, label=protocol)
            
            ax.set_title(f'Scenario: {scenario}')
            ax.set_ylabel('Bitrate (kbps)')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / 'time_vs_bitrate.png', dpi=300, bbox_inches='tight')
        plt.show()
    
    def plot_startup_delay_cdf(self):
        """Plot CDF of startup delays"""
        if self.df.empty:
            return
        
        plt.figure(figsize=(10, 6))
        
        for protocol in ['QUIC', 'DASH']:
            protocol_data = self.df[self.df['protocol'] == protocol]
            if not protocol_data.empty:
                if protocol == 'QUIC':
                    delays = protocol_data['metric_startup_delay'] / 1000  # Convert to seconds
                else:
                    delays = protocol_data['metric_startup_delay']
                
                if len(delays) > 0:
                    delays_sorted = np.sort(delays)
                    cdf = np.arange(1, len(delays_sorted) + 1) / len(delays_sorted)
                    plt.plot(delays_sorted, cdf, label=protocol, linewidth=2)
        
        plt.xlabel('Startup Delay (seconds)')
        plt.ylabel('CDF')
        plt.title('CDF of Startup Delays')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(self.results_dir / 'startup_delay_cdf.png', dpi=300, bbox_inches='tight')
        plt.show()
    
    def plot_qoe_comparison(self):
        """Plot QoE comparison boxplots"""
        if self.df.empty:
            return
        
        # Calculate simple QoE score (higher is better)
        def calculate_qoe(row):
            if row['protocol'] == 'QUIC':
                bitrate = row.get('metric_transfer_rate_kbps', 0)
                delay = row.get('metric_startup_delay', 1) / 1000  # ms to seconds
            else:
                bitrate = row.get('metric_average_bitrate', 0) / 1000  # bps to kbps
                delay = row.get('metric_startup_delay', 1)
            
            # Simple QoE: bitrate / (delay + 1) - rebuffering_penalty
            rebuffering_penalty = row.get('metric_total_rebuffering_time', 0) * 10
            return bitrate / (delay + 1) - rebuffering_penalty
        
        self.df['qoe_score'] = self.df.apply(calculate_qoe, axis=1)
        
        plt.figure(figsize=(12, 6))
        
        # Boxplot by protocol
        data_to_plot = []
        labels = []
        for protocol in ['QUIC', 'DASH']:
            protocol_data = self.df[self.df['protocol'] == protocol]['qoe_score']
            if len(protocol_data) > 0:
                data_to_plot.append(protocol_data)
                labels.append(protocol)
        
        plt.boxplot(data_to_plot, labels=labels)
        plt.ylabel('QoE Score')
        plt.title('Quality of Experience Comparison')
        plt.grid(True, alpha=0.3)
        plt.savefig(self.results_dir / 'qoe_comparison.png', dpi=300, bbox_inches='tight')
        plt.show()
    
    def generate_comprehensive_report(self):
        """Generate comprehensive analysis report"""
        if self.df.empty:
            print("No results to analyze")
            return
        
        report = {
            'summary_statistics': {},
            'protocol_comparison': {},
            'scenario_analysis': {}
        }
        
        # Summary statistics
        report['summary_statistics'] = {
            'total_tests': len(self.df),
            'quic_tests': len(self.df[self.df['protocol'] == 'QUIC']),
            'dash_tests': len(self.df[self.df['protocol'] == 'DASH']),
            'unique_scenarios': self.df['scenario'].nunique()
        }
        
        # Protocol comparison
        for protocol in ['QUIC', 'DASH']:
            proto_data = self.df[self.df['protocol'] == protocol]
            if not proto_data.empty:
                report['protocol_comparison'][protocol] = {
                    'avg_startup_delay': proto_data['metric_startup_delay'].mean(),
                    'avg_bitrate': proto_data.get('metric_transfer_rate_kbps', proto_data.get('metric_average_bitrate', 0) / 1000).mean(),
                    'avg_rebuffering_events': proto_data.get('metric_rebuffering_events', 0).mean(),
                    'tests_count': len(proto_data)
                }
        
        # Save report
        report_file = self.results_dir / 'analysis_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Analysis report saved: {report_file}")
        return report
    
    def plot_all_analysis(self):
        """Generate all analysis plots"""
        print("Generating comprehensive analysis plots...")
        
        self.plot_time_vs_bitrate()
        self.plot_startup_delay_cdf()
        self.plot_qoe_comparison()
        
        # Additional plots
        self.plot_scenario_comparison()
        self.plot_network_impact()
        
        print("All plots generated and saved to results directory")

    def plot_scenario_comparison(self):
        """Compare performance across different scenarios"""
        if self.df.empty:
            return
        
        # Group by scenario and protocol
        scenario_performance = self.df.groupby(['scenario', 'protocol']).agg({
            'metric_startup_delay': 'mean',
            'metric_transfer_rate_kbps': 'mean',
            'metric_average_bitrate': 'mean'
        }).reset_index()
        
        plt.figure(figsize=(15, 5))
        
        # Startup delay comparison
        plt.subplot(1, 3, 1)
        for protocol in ['QUIC', 'DASH']:
            data = scenario_performance[scenario_performance['protocol'] == protocol]
            if not data.empty:
                if protocol == 'QUIC':
                    delays = data['metric_startup_delay'] / 1000
                else:
                    delays = data['metric_startup_delay']
                plt.plot(data['scenario'], delays, 'o-', label=protocol)
        
        plt.xticks(rotation=45)
        plt.ylabel('Startup Delay (s)')
        plt.title('Startup Delay by Scenario')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / 'scenario_comparison.png', dpi=300, bbox_inches='tight')
        plt.show()

    def plot_network_impact(self):
        """Plot impact of network parameters on performance"""
        if self.df.empty:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Bandwidth impact
        bw_scenarios = ['bw_2mbit', 'bw_5mbit', 'bw_10mbit', 'bw_20mbit']
        self._plot_parameter_impact(axes[0, 0], bw_scenarios, 'Bandwidth (Mbps)', [2, 5, 10, 20])
        
        # Delay impact
        delay_scenarios = ['delay_10ms', 'delay_40ms', 'delay_80ms']
        self._plot_parameter_impact(axes[0, 1], delay_scenarios, 'Delay (ms)', [10, 40, 80])
        
        # Loss impact
        loss_scenarios = ['loss_0p', 'loss_0.1p', 'loss_1p', 'loss_3p']
        self._plot_parameter_impact(axes[1, 0], loss_scenarios, 'Loss Rate (%)', [0, 0.1, 1, 3])
        
        # Jitter impact
        jitter_scenarios = ['jitter_0ms', 'jitter_10ms', 'jitter_30ms']
        self._plot_parameter_impact(axes[1, 1], jitter_scenarios, 'Jitter (ms)', [0, 10, 30])
        
        plt.tight_layout()
        plt.savefig(self.results_dir / 'network_impact.png', dpi=300, bbox_inches='tight')
        plt.show()
    
    def _plot_parameter_impact(self, ax, scenarios, xlabel, xvalues):
        """Helper function to plot parameter impact"""
        for protocol in ['QUIC', 'DASH']:
            bitrates = []
            for scenario in scenarios:
                data = self.df[(self.df['scenario'] == scenario) & (self.df['protocol'] == protocol)]
                if not data.empty:
                    if protocol == 'QUIC':
                        bitrate = data['metric_transfer_rate_kbps'].mean()
                    else:
                        bitrate = data['metric_average_bitrate'].mean() / 1000
                    bitrates.append(bitrate)
                else:
                    bitrates.append(0)
            
            ax.plot(xvalues[:len(bitrates)], bitrates, 'o-', label=protocol, linewidth=2)
        
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Bitrate (kbps)')
        ax.set_title(f'Impact of {xlabel.split(" ")[0]} on Bitrate')
        ax.legend()
        ax.grid(True, alpha=0.3)

if __name__ == "__main__":
    analyzer = ResultsAnalyzer()
    
    if not analyzer.df.empty:
        analyzer.generate_comprehensive_report()
        analyzer.plot_all_analysis()
        
        # Print summary
        print("\n=== ANALYSIS SUMMARY ===")
        print(f"Total tests analyzed: {len(analyzer.df)}")
        print(f"QUIC tests: {len(analyzer.df[analyzer.df['protocol'] == 'QUIC'])}")
        print(f"DASH tests: {len(analyzer.df[analyzer.df['protocol'] == 'DASH'])}")
        
        # Compare average performance
        quic_avg_delay = analyzer.df[analyzer.df['protocol'] == 'QUIC']['metric_startup_delay'].mean() / 1000
        dash_avg_delay = analyzer.df[analyzer.df['protocol'] == 'DASH']['metric_startup_delay'].mean()
        
        print(f"\nAverage Startup Delay:")
        print(f"  QUIC: {quic_avg_delay:.2f}s")
        print(f"  DASH: {dash_avg_delay:.2f}s")
    else:
        print("No test results found for analysis")