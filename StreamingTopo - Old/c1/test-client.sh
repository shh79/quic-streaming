#!/bin/bash

echo "🔥 Testing MPEG-DASH:"
curl http://10.0.0.2:8080/video.mpd

echo -e "\n📺 Testing HLS:"
curl http://10.0.0.3:8080/index.m3u8

echo -e "\n⚡️ Testing QUIC (need curl compiled with http3):"
# نیازمند curl با http3 است یا استفاده از quiche-client
