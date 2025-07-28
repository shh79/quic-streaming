import pandas as pd
import matplotlib.pyplot as plt

# Load results
df = pd.read_csv("results.csv")

# Plot Delay Comparison
plt.figure(figsize=(8, 5))
plt.bar(df["Protocol"], df["Delay (s)"], color=['orange', 'blue', 'green'])
plt.title("Video Streaming Protocol Comparison: Delay")
plt.ylabel("Delay (seconds)")
plt.xlabel("Protocol")
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.savefig("delay_comparison.png")
plt.show()

# Plot Data Rate Comparison
plt.figure(figsize=(8, 5))
plt.bar(df["Protocol"], df["Data Rate (KB/s)"], color=['orange', 'blue', 'green'])
plt.title("Video Streaming Protocol Comparison: Data Rate")
plt.ylabel("Data Rate (KB/s)")
plt.xlabel("Protocol")
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.savefig("data_rate_comparison.png")
plt.show()
