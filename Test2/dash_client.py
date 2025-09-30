import requests
import xml.etree.ElementTree as ET
import os
import time

# Config
MPD_URL = "http://10.0.0.2:8080/manifest.mpd"
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

print("Fetching manifest...")
resp = requests.get(MPD_URL)
resp.raise_for_status()
mpd_content = resp.text

root = ET.fromstring(mpd_content)
ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}

# Parse representations
representations = []
for rep in root.findall(".//mpd:Representation", ns):
    rep_id = rep.attrib["id"]
    bw = int(rep.attrib["bandwidth"])
    base_url = rep.find("mpd:BaseURL", ns).text
    seg_list = rep.find("mpd:SegmentList", ns)
    init_url = seg_list.find("mpd:Initialization", ns).attrib["sourceURL"]
    seg_urls = [seg.attrib["media"] for seg in seg_list.findall("mpd:SegmentURL", ns)]
    representations.append({
        "id": rep_id,
        "bandwidth": bw,
        "base_url": base_url,
        "init": init_url,
        "segments": seg_urls
    })

# Sort representations by bitrate (low → high)
representations.sort(key=lambda r: r["bandwidth"])

# Start with lowest quality
current_rep = representations[0]
print(f"Starting with {current_rep['id']} ({current_rep['bandwidth']} bps)")

base_path = MPD_URL.rsplit("/", 1)[0] + "/"
num_segments = max(len(r["segments"]) for r in representations)

for i in range(num_segments):
    # Safety: pick segment from current_rep if exists
    if i >= len(current_rep["segments"]):
        continue
    seg_name = current_rep["segments"][i]
    seg_url = base_path + current_rep["base_url"] + seg_name
    seg_filename = os.path.join(RESULTS_DIR, f"{i}_{current_rep['id']}_{seg_name}")

    print(f"Downloading segment {i} from {current_rep['id']} -> {seg_filename}")
    start = time.time()
    data = requests.get(seg_url).content
    elapsed = time.time() - start
    throughput = (len(data) * 8) / max(elapsed, 1e-6)  # bits/sec
    print(f"  size={len(data)/1024:.1f} KB, time={elapsed:.2f}s, throughput={throughput/1e6:.2f} Mbps")

    # Save segment exactly as received
    with open(seg_filename, "wb") as f:
        f.write(data)

    # --- Adaptive bitrate logic ---
    safety_factor = 0.8
    suitable_reps = [r for r in representations if r["bandwidth"] < throughput * safety_factor]
    if suitable_reps:
        new_rep = suitable_reps[-1]  # pick highest suitable
    else:
        new_rep = representations[0]

    if new_rep["id"] != current_rep["id"]:
        print(f"⚡ Switching {current_rep['id']} -> {new_rep['id']}")
        current_rep = new_rep

print(f"✅ All segments saved in folder: {RESULTS_DIR}")
