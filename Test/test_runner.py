import asyncio
import subprocess
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from netem_manager import NetworkEmulator, SCENARIOS

class StreamingTestRunner:
    def __init__(self, output_dir="results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.netem = NetworkEmulator()
        self.results = []
        
    async def run_quic_test(self, scenario_name, scenario_params, quic_params):
        """Run QUIC streaming test"""
        test_id = f"quic_{scenario_name}_{datetime.now().strftime('%H%M%S')}"
        test_dir = self.output_dir / test_id
        test_dir.mkdir(exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"Starting QUIC Test: {test_id}")
        print(f"{'='*60}")
        
        # Start QUIC server
        server_cmd = [
            'python3', 'quic_server.py',
            '--host', '10.0.0.1',
            '--port', '4433',
            '--cc', quic_params['cc_algorithm']
        ]
        
        server_proc = subprocess.Popen(server_cmd)
        time.sleep(3)  # Wait for server to start
        
        try:
            # Run QUIC client
            client_cmd = [
                'python3', 'quic_client.py',
                '--host', '10.0.0.1',
                '--port', '4433',
                '--video', quic_params['video'],
                '--cc', quic_params['cc_algorithm']
            ]
            
            start_time = time.time()
            client_proc = await asyncio.create_subprocess_exec(
                *client_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await client_proc.communicate()
            total_time = time.time() - start_time
            
            # Save results
            with open(test_dir / 'stdout.log', 'w') as f:
                f.write(stdout.decode())
            
            if stderr:
                with open(test_dir / 'stderr.log', 'w') as f:
                    f.write(stderr.decode())
            
            # Copy qlog files to test directory
            for qlog_file in Path('.').glob('*.qlog'):
                qlog_file.rename(test_dir / qlog_file.name)
            
            # Collect metrics
            metrics = self.collect_quic_metrics(test_dir, total_time)
            
            test_result = {
                'test_id': test_id,
                'protocol': 'QUIC',
                'scenario': scenario_name,
                'scenario_params': scenario_params,
                'quic_params': quic_params,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(test_result)
            self.save_test_result(test_dir, test_result)
            
            print(f"QUIC test completed: {test_id}")
            return test_dir
            
        except Exception as e:
            print(f"Error in QUIC test: {e}")
            return None
        finally:
            server_proc.terminate()
            server_proc.wait()
    
    async def run_dash_test(self, scenario_name, scenario_params, dash_params):
        """Run DASH streaming test"""
        test_id = f"dash_{scenario_name}_{datetime.now().strftime('%H%M%S')}"
        test_dir = self.output_dir / test_id
        test_dir.mkdir(exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"Starting DASH Test: {test_id}")
        print(f"{'='*60}")
        
        try:
            # Run DASH client
            client_cmd = [
                'python3', 'dash_client.py',
                '--manifest', dash_params['manifest_url'],
                '--output', str(test_dir / 'dash_output.mp4'),
                '--duration', str(dash_params['duration']),
                '--segment-length', str(dash_params['segment_length']),
                '--abr', dash_params['abr_algorithm'],
                '--buffer-target', str(dash_params['buffer_target'])
            ]
            
            start_time = time.time()
            client_proc = await asyncio.create_subprocess_exec(
                *client_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await client_proc.communicate()
            total_time = time.time() - start_time
            
            # Save results
            with open(test_dir / 'stdout.log', 'w') as f:
                f.write(stdout.decode())
            
            if stderr:
                with open(test_dir / 'stderr.log', 'w') as f:
                    f.write(stderr.decode())
            
            # Collect metrics
            metrics = self.collect_dash_metrics(test_dir, total_time)
            
            test_result = {
                'test_id': test_id,
                'protocol': 'DASH',
                'scenario': scenario_name,
                'scenario_params': scenario_params,
                'dash_params': dash_params,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(test_result)
            self.save_test_result(test_dir, test_result)
            
            print(f"DASH test completed: {test_id}")
            return test_dir
            
        except Exception as e:
            print(f"Error in DASH test: {e}")
            return None
    
    def collect_quic_metrics(self, test_dir, total_time):
        """Collect metrics from QUIC test"""
        metrics = {
            'total_time': total_time,
            'qlog_files': list(test_dir.glob('*.qlog'))
        }
        
        # Parse qlog files for detailed metrics
        for qlog_file in metrics['qlog_files']:
            try:
                with open(qlog_file, 'r') as f:
                    qlog_data = json.load(f)
                
                # Extract metrics from qlog events
                for event in qlog_data.get('trace', {}).get('events', []):
                    if event.get('name') == 'stream:transfer_complete':
                        metrics.update(event.get('data', {}))
                        break
            except:
                pass
        
        return metrics
    
    def collect_dash_metrics(self, test_dir, total_time):
        """Collect metrics from DASH test"""
        metrics = {
            'total_time': total_time
        }
        
        # Parse metrics file
        metrics_file = test_dir / 'dash_output.mp4_metrics.json'
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    dash_metrics = json.load(f)
                metrics.update(dash_metrics)
            except:
                pass
        
        return metrics
    
    def save_test_result(self, test_dir, test_result):
        """Save individual test result"""
        result_file = test_dir / 'test_result.json'
        with open(result_file, 'w') as f:
            json.dump(test_result, f, indent=2)
    
    def generate_summary_report(self):
        """Generate comprehensive test report"""
        report = {
            'summary': {
                'total_tests': len(self.results),
                'quic_tests': len([r for r in self.results if r['protocol'] == 'QUIC']),
                'dash_tests': len([r for r in self.results if r['protocol'] == 'DASH']),
                'scenarios_tested': list(set(r['scenario'] for r in self.results))
            },
            'detailed_results': self.results,
            'comparison_metrics': self.calculate_comparison_metrics()
        }
        
        report_file = self.output_dir / 'test_summary_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nSummary report generated: {report_file}")
        return report
    
    def calculate_comparison_metrics(self):
        """Calculate comparison metrics between QUIC and DASH"""
        comparison = {}
        
        # Group by scenario
        for scenario in set(r['scenario'] for r in self.results):
            scenario_results = [r for r in self.results if r['scenario'] == scenario]
            quic_results = [r for r in scenario_results if r['protocol'] == 'QUIC']
            dash_results = [r for r in scenario_results if r['protocol'] == 'DASH']
            
            if quic_results and dash_results:
                comparison[scenario] = {
                    'quic_avg_startup_delay': sum(r['metrics'].get('startup_delay', 0) for r in quic_results) / len(quic_results),
                    'dash_avg_startup_delay': sum(r['metrics'].get('startup_delay', 0) for r in dash_results) / len(dash_results),
                    'quic_avg_bitrate': sum(r['metrics'].get('transfer_rate_kbps', 0) for r in quic_results) / len(quic_results),
                    'dash_avg_bitrate': sum(r['metrics'].get('average_bitrate', 0) / 1000 for r in dash_results) / len(dash_results),
                }
        
        return comparison

async def run_comprehensive_test_suite():
    """Run comprehensive test suite"""
    runner = StreamingTestRunner()
    
    # QUIC parameters
    quic_configs = [
        {'cc_algorithm': 'cubic', 'video': 'sample_720p.mp4'},
        {'cc_algorithm': 'reno', 'video': 'sample_720p.mp4'},
    ]
    
    # DASH parameters
    dash_configs = [
        {'manifest_url': 'http://10.0.0.2:8080/manifest.mpd', 'duration': 60, 
         'segment_length': 4, 'abr_algorithm': 'throughput', 'buffer_target': 15},
        {'manifest_url': 'http://10.0.0.2:8080/manifest.mpd', 'duration': 60,
         'segment_length': 4, 'abr_algorithm': 'buffer', 'buffer_target': 15},
    ]
    
    # Background traffic configurations
    background_configs = [
        {'protocol': 'tcp', 'flows': 1, 'bandwidth': '5mbit', 'duration': 70},
        {'protocol': 'udp', 'flows': 2, 'bandwidth': '2mbit', 'duration': 70},
    ]
    
    total_scenarios = len(SCENARIOS) * (len(quic_configs) + len(dash_configs))
    current_scenario = 0
    
    for scenario_name, scenario_params in SCENARIOS.items():
        current_scenario += 1
        
        print(f"\n{'#'*80}")
        print(f"Scenario {current_scenario}/{total_scenarios}: {scenario_name}")
        print(f"Network: {scenario_params}")
        print(f"{'#'*80}")
        
        # Setup network conditions
        success = runner.netem.setup_netem(**scenario_params)
        if not success:
            print(f"Failed to setup network for {scenario_name}, skipping...")
            continue
        
        time.sleep(2)
        
        # Add background traffic for some scenarios
        if scenario_name in ['loss_1p', 'delay_80ms', 'jitter_30ms']:
            bg_config = background_configs[0]  # Use first background config
            runner.netem.create_background_traffic(**bg_config)
            time.sleep(5)
        
        # Run QUIC tests
        for quic_config in quic_configs:
            await runner.run_quic_test(scenario_name, scenario_params, quic_config)
            time.sleep(5)  # Cool-down period
        
        # Run DASH tests
        for dash_config in dash_configs:
            await runner.run_dash_test(scenario_name, scenario_params, dash_config)
            time.sleep(5)  # Cool-down period
        
        # Clear background traffic
        runner.netem.clear_rules()
        time.sleep(2)
    
    # Generate final report
    report = runner.generate_summary_report()
    
    print(f"\n{'='*80}")
    print("COMPREHENSIVE TEST SUITE COMPLETED")
    print(f"Total tests run: {len(runner.results)}")
    print(f"Results directory: {runner.output_dir}")
    print(f"{'='*80}")
    
    return report

async def run_specific_scenarios(scenario_names, protocols=['quic', 'dash']):
    """Run specific scenarios"""
    runner = StreamingTestRunner()
    
    for scenario_name in scenario_names:
        if scenario_name not in SCENARIOS:
            print(f"Unknown scenario: {scenario_name}")
            continue
        
        scenario_params = SCENARIOS[scenario_name]
        print(f"\nRunning scenario: {scenario_name}")
        
        # Setup network - FIXED: Extract individual parameters
        success = runner.netem.setup_netem(
            bandwidth=scenario_params['bandwidth'],
            delay=scenario_params['delay'],
            jitter=scenario_params['jitter'],
            loss=scenario_params['loss'],
            queue_algorithm=scenario_params['queue']
        )
        
        if not success:
            print(f"Failed to setup network for {scenario_name}, skipping...")
            continue
            
        time.sleep(2)
        
        if 'quic' in protocols:
            quic_config = {'cc_algorithm': 'cubic', 'video': 'sample_720p.mp4'}
            await runner.run_quic_test(scenario_name, scenario_params, quic_config)
            time.sleep(3)
        
        if 'dash' in protocols:
            dash_config = {
                'manifest_url': 'http://10.0.0.2:8080/manifest.mpd', 
                'duration': 60,
                'segment_length': 4, 
                'abr_algorithm': 'throughput', 
                'buffer_target': 15
            }
            await runner.run_dash_test(scenario_name, scenario_params, dash_config)
            time.sleep(3)
    
    runner.generate_summary_report()
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Streaming Test Runner')
    parser.add_argument('--mode', choices=['comprehensive', 'quick', 'specific'], default='quick',
                       help='Test mode: comprehensive (all scenarios), quick (subset), specific (custom)')
    parser.add_argument('--scenarios', nargs='+', help='Specific scenarios to run')
    parser.add_argument('--protocols', nargs='+', choices=['quic', 'dash'], default=['quic', 'dash'],
                       help='Protocols to test')
    
    args = parser.parse_args()
    
    if args.mode == 'comprehensive':
        asyncio.run(run_comprehensive_test_suite())
    elif args.mode == 'specific' and args.scenarios:
        asyncio.run(run_specific_scenarios(args.scenarios, args.protocols))
    else:
        # Quick test with few scenarios
        quick_scenarios = ['bw_10mbit', 'delay_40ms', 'loss_1p']
        asyncio.run(run_specific_scenarios(quick_scenarios, args.protocols))