import subprocess

def prepare_video(input_file, output_prefix):
    # Convert video to multiple bitrates
    bitrates = [
        ('low', '640x360', '600k'),
        ('medium', '854x480', '1200k'),
        ('high', '1280x720', '2400k')
    ]
    
    for name, resolution, bitrate in bitrates:
        cmd = [
            'ffmpeg', '-i', input_file,
            '-c:v', 'libx264', '-crf', '22',
            '-vf', f'scale={resolution}',
            '-b:v', bitrate,
            '-c:a', 'aac', '-b:a', '128k',
            '-f', 'mp4',
            f'{output_prefix}_{name}.mp4'
        ]
        subprocess.run(cmd)
    
    return [f'{output_prefix}_{name}.mp4' for name, _, _ in bitrates]

# Example usage:
prepare_video('sample.mp4', 'sample')