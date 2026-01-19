import subprocess
import os
import shutil
import math
import re

# Use local ffmpeg
FFMPEG_BIN = os.path.abspath(r"ffmpeg\bin\ffmpeg.exe")
FFPROBE_BIN = os.path.abspath(r"ffmpeg\bin\ffprobe.exe")

def get_mean_volume(file_path):
    cmd = [
        FFMPEG_BIN, "-hide_banner", "-i", file_path,
        "-af", "volumedetect",
        "-vn", "-sn", "-dn",
        "-f", "null", "NUL"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    # Search for mean_volume: -20.0 dB
    match = re.search(r"mean_volume:\s+([-\d.]+)\s+dB", res.stderr)
    if match:
        return float(match.group(1))
    return None

def run_test():
    if not os.path.exists(FFMPEG_BIN):
        print(f"Error: FFmpeg not found at {FFMPEG_BIN}")
        return

    # 1. Generate Source (Sine wave, loud)
    # 5 seconds, 1kHz tone at -10dBFS usually standard, let's just use default sine
    src_file = "volume_test_src.mp4"
    if not os.path.exists(src_file):
        print("Generating source file...")
        subprocess.run([
            FFMPEG_BIN, "-y",
            "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=5",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=5",
            "-c:v", "libx264", "-c:a", "aac", 
            src_file
        ], check=True, stderr=subprocess.DEVNULL)

    src_vol = get_mean_volume(src_file)
    print(f"Source Volume: {src_vol} dB")

    # 2. Transcode with volume=0.05
    # Simulating the user command structure
    # ... -vf scale=800:450 -af volume=0.05 -c:v libx264 ...
    
    out_file = "volume_test_out.mp4"
    print("Transcoding with volume=0.05 ...")
    
    # NOTE: Using libx264 since I might not have nvenc on this agent, but filter logic is same
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", src_file,
        "-vf", "scale=800:450",
        "-af", "volume=0.05",
        "-c:v", "libx264",
        "-c:a", "aac", "-b:a", "128k",
        out_file
    ]
    
    subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
    
    out_vol = get_mean_volume(out_file)
    print(f"Output Volume: {out_vol} dB")
    
    expected_drop = 20 * math.log10(0.05) # approx -26 dB
    print(f"Expected Drop: {expected_drop:.2f} dB")
    
    diff = out_vol - src_vol
    print(f"Actual Drop: {diff:.2f} dB")
    
    if abs(diff - expected_drop) < 2.0:
        print("TEST PASSED: Volume reduced as expected.")
    else:
        print("TEST FAILED: Volume did not reduce correctly.")

if __name__ == "__main__":
    run_test()
