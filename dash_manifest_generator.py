import subprocess

def create_dash_package(input_files, output_dir):
    # Create MP4Box command to generate DASH content
    cmd = ['MP4Box', '-dash', '4000', 
           '-profile', 'dashavc264:onDemand',
           '-segment-name', 'segment_$RepresentationID$_',
           '-out', f'{output_dir}/manifest.mpd']
    
    cmd.extend(input_files)
    
    subprocess.run(cmd)
    
    return f'{output_dir}/manifest.mpd'

# Example usage:
input_files = ['sample_low.mp4', 'sample_medium.mp4', 'sample_high.mp4']
mpd_path = create_dash_package(input_files, 'dash_content')