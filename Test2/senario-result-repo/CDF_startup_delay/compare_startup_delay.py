import json
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# ---- 1. Extract QUIC Startup Delay from QLOG ----
def extract_quic_startup_delays(folder):
    results = []
    for path in glob.glob(f"{folder}/*.qlog"):
        with open(path) as f:
            data = json.load(f)
            events = data["trace"]["events"]

            request_time = None
            first_data_time = None
            video_name = None

            for e in events:
                name = e["name"]
                if name == "stream:request" and request_time is None:
                    request_time = e["time"]
                    video_name = e["data"].get("video_name", "unknown")
                if name == "stream:data_received" and e["data"].get("is_first_chunk") and first_data_time is None:
                    first_data_time = e["time"]

            if request_time is not None and first_data_time is not None:
                startup_delay = first_data_time - request_time
                results.append({
                    "protocol": "QUIC",
                    "file": path.split("/")[-1],
                    "startup_delay_sec": startup_delay / 1000.0
                })
    return pd.DataFrame(results)

# ---- 2. Extract DASH Startup Delay from CSV logs ----
def extract_dash_startup_delays(folder):
    results = []
    for path in glob.glob(f"{folder}/*.csv"):
        df = pd.read_csv(path)
        # find init (segment 0) and first media segment (segment 1)
        seg0 = df[df["segment_index"] == 0].iloc[0]
        seg1 = df[df["segment_index"] == 1].iloc[0]

        # parse timestamps
        t0 = datetime.fromisoformat(seg0["timestamp"])
        t1 = datetime.fromisoformat(seg1["timestamp"])
        # approximate download start and end
        dash_startup_delay = (t1 - t0).total_seconds() + seg1["download_time_sec"]

        results.append({
            "protocol": "DASH",
            "file": path.split("/")[-1],
            "startup_delay_sec": dash_startup_delay
        })
    return pd.DataFrame(results)

# ---- 3. Extract both ----
df_quic = extract_quic_startup_delays("quic")
df_dash = extract_dash_startup_delays("dash")

df_all = pd.concat([df_quic, df_dash], ignore_index=True)
df_all.to_csv("startup_delay_quic_dash.csv", index=False)

print(df_all)
print(f"\nExtracted {len(df_all)} total startup delays")

# ---- 4. Plot CDF ----
plt.figure(figsize=(7,5))
for proto, df in df_all.groupby("protocol"):
    delays = np.sort(df["startup_delay_sec"].values)
    cdf = np.arange(1, len(delays) + 1) / len(delays)
    plt.plot(delays, cdf, label=proto, linewidth=2)

plt.xlabel("Startup Delay (seconds)")
plt.ylabel("CDF")
plt.title("CDF of Startup Delay — QUIC vs DASH")
plt.grid(True, linestyle="--", alpha=0.6)
plt.legend()
plt.tight_layout()

save_path = './CDF_startup_delay.png'
plt.savefig(save_path, dpi=300, bbox_inches='tight')
print(f"CDF startup delay plot saved to: {save_path}")

plt.show()
