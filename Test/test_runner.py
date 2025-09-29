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
    
    async def run_quic_test(self, scenario_name, scenario_params):
        """Run QUIC streaming test"""
        test_id = f"quic_{scenario_name}_{datetime.now().strftime('%H%M%S')}"
        test_dir = self.output_dir / test_id
        test_dir.mkdir(exist_ok=True)
        
        print(f"\n=== QUIC TEST: {scenario_name.upper()} ===")
        
        try:
            # Run QUIC client
            client_cmd = [
                'python3', 'quic_client.py',
                '--host', '10.0.0.1',
                '--video', 'sample_240p.mp4'
            ]
            
            start_time = time.time()
            process = await asyncio.create_subprocess_exec(
                *client_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
                total_time = time.time() - start_time
                
                # Save logs
                with open(test_dir / 'stdout.log', 'wb') as f:
                    f.write(stdout)
                if stderr:
                    with open(test_dir / 'stderr.log', 'wb') as f:
                        f.write(stderr)
                
                success = process.returncode == 0
                
                # Collect basic metrics
                metrics = {
                    'success': success,
                    'total_time': total_time,
                    'return_code': process.returncode
                }
                
                # Look for QLog files
                qlog_files = list(Path('.').glob('*.qlog'))
                for qlog_file in qlog_files:
                    qlog_file.rename(test_dir / qlog_file.name)
                    metrics['qlog_file'] = qlog_file.name
                
                test_result = {
                    'test_id': test_id,
                    'protocol': 'QUIC', 
                    'scenario': scenario_name,
                    'scenario_params': scenario_params,
                    'metrics': metrics,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.results.append(test_result)
                self.save_test_result(test_dir, test_result)
                
                status = "✓ SUCCESS" if success else "✗ FAILED"
                print(f"QUIC Test: {status} - Time: {total_time:.1f}s")
                
                return success
                
            except asyncio.TimeoutError:
                print("QUIC Test: ⏰ TIMEOUT")
                process.terminate()
                return False
                
        except Exception as e:
            print(f"QUIC Test: ❌ ERROR: {e}")
            return False
    
    async def run_dash_test(self, scenario_name, scenario_params):
        """Run DASH streaming test"""
        test_id = f"dash_{scenario_name}_{datetime.now().strftime('%H%M%S')}"
        test_dir = self.output_dir / test_id
        test_dir.mkdir(exist_ok=True)
        
        print(f"\n=== DASH TEST: {scenario_name.upper()} ===")
        
        try:
            # Run DASH client
            client_cmd = [
                'python3', 'dash_client.py',
                '--manifest', 'http://10.0.0.2:8080/manifest.mpd',
                '--output', str(test_dir / 'dash_output.mp4'),
                '--duration', '30'
            ]
            
            start_time = time.time()
            process = await asyncio.create_subprocess_exec(
                *client_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
                total_time = time.time() - start_time
                
                # Save logs
                with open(test_dir / 'stdout.log', 'wb') as f:
                    f.write(stdout)
                if stderr:
                    with open(test_dir / 'stderr.log', 'wb') as f:
                        f.write(stderr)
                
                success = process.returncode == 0
                
                metrics = {
                    'success': success,
                    'total_time': total_time,
                    'return_code': process.returncode
                }
                
                test_result = {
                    'test_id': test_id,
                    'protocol': 'DASH',
                    'scenario': scenario_name, 
                    'scenario_params': scenario_params,
                    'metrics': metrics,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.results.append(test_result)
                self.save_test_result(test_dir, test_result)
                
                status = "✓ SUCCESS" if success else "✗ FAILED"
                print(f"DASH Test: {status} - Time: {total_time:.1f}s")
                
                return success
                
            except asyncio.TimeoutError:
                print("DASH Test: ⏰ TIMEOUT")
                process.terminate()
                return False
                
        except Exception as e:
            print(f"DASH Test: ❌ ERROR: {e}")
            return False
    
    def save_test_result(self, test_dir, test_result):
        """Save test result"""
        result_file = test_dir / 'test_result.json'
        with open(result_file, 'w') as f:
            json.dump(test_result, f, indent=2)
    
    def generate_summary_report(self):
        """Generate comprehensive test report"""
        if not self.results:
            print("No test results to report")
            return
        
        summary = {
            'total_tests': len(self.results),
            'successful_tests': len([r for r in self.results if r['metrics']['success']]),
            'failed_tests': len([r for r in self.results if not r['metrics']['success']]),
            'quic_tests': len([r for r in self.results if r['protocol'] == 'QUIC']),
            'dash_tests': len([r for r in self.results if r['protocol'] == 'DASH']),
            'scenarios_tested': list(set(r['scenario'] for r in self.results)),
            'results': self.results
        }
        
        report_file = self.output_dir / 'test_summary_report.json'
        with open(report_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n{'='*60}")
        print("TEST SUMMARY REPORT")
        print(f"{'='*60}")
        print(f"Total tests: {summary['total_tests']}")
        print(f"Successful: {summary['successful_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"QUIC tests: {summary['quic_tests']}")
        print(f"DASH tests: {summary['dash_tests']}")
        print(f"Scenarios tested: {', '.join(summary['scenarios_tested'])}")
        print(f"Report saved: {report_file}")
        
        return summary

async def run_comprehensive_tests():
    """Run comprehensive test suite"""
    runner = StreamingTestRunner()
    
    print("Starting Comprehensive Streaming Tests")
    print("This will test QUIC and DASH under different network conditions")
    
    scenarios_to_test = ['good', 'medium', 'poor']
    
    for scenario_name in scenarios_to_test:
        print(f"\n{'#'*60}")
        print(f"TESTING SCENARIO: {scenario_name.upper()}")
        print(f"{'#'*60}")
        
        scenario_params = SCENARIOS[scenario_name]
        
        # Setup network conditions
        print(f"Setting up network: {scenario_name}")
        success = runner.netem.setup_netem(**scenario_params)
        
        if not success:
            print(f"Failed to setup network for {scenario_name}, skipping...")
            continue
        
        time.sleep(3)  # Wait for network to stabilize
        
        # Run QUIC test
        await runner.run_quic_test(scenario_name, scenario_params)
        time.sleep(5)
        
        # Run DASH test
        await runner.run_dash_test(scenario_name, scenario_params)
        time.sleep(5)
        
        # Clear network rules
        runner.netem.clear_rules()
        time.sleep(2)
    
    # Generate final report
    runner.generate_summary_report()

async def run_quick_test():
    """Run quick test with only good network conditions"""
    runner = StreamingTestRunner()
    
    print("Running Quick Test (Good Network Conditions Only)")
    
    scenario_name = 'good'
    scenario_params = SCENARIOS[scenario_name]
    
    # Setup network
    print("Setting up good network conditions...")
    success = runner.netem.setup_netem(**scenario_params)
    
    if not success:
        print("Failed to setup network, aborting...")
        return
    
    time.sleep(2)
    
    # Run tests
    await runner.run_quic_test(scenario_name, scenario_params)
    time.sleep(3)
    
    await runner.run_dash_test(scenario_name, scenario_params)
    time.sleep(3)
    
    # Clear network
    runner.netem.clear_rules()
    
    # Generate report
    runner.generate_summary_report()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['comprehensive', 'quick'], default='quick',
                       help='Test mode: comprehensive (all scenarios), quick (good network only)')
    
    args = parser.parse_args()
    
    if args.mode == 'comprehensive':
        asyncio.run(run_comprehensive_tests())
    else:
        asyncio.run(run_quick_test())