# WiFi Channel Survey & CBR Logger

Python utility designed to monitor Linux wireless interface statistics in real-time. By parsing the output of `iw survey dump`, this script calculates the **Channel Busy Ratio (CBR)** and tracks airtime metrics (Active, Busy, RX, TX, Noise) for a specific frequency.

---

## Overview

Wireless hardware provides cumulative counters for channel usage. To get a real-time view of network congestion, this script samples those counters at regular intervals and calculates the **deltas** (the change between samples). This is essential for understanding how much "airtime" is actually available on a specific WiFi channel.

## Prerequisites

* **Operating System**: Linux (required for the `iw` tool).
* **System Tools**: `iw` must be installed (e.g., `sudo apt install iw`).
* **Permissions**: The script must be run with **root/sudo** privileges to access hardware survey data.
* **Python**: Version 3.7 or higher (uses standard libraries only).

---

## Usage Examples

To monitor interface `wlan0` on frequency `5900 MHz` with the default 0.5s sampling rate:
```bash
sudo python3 iw_survey_dump.py --iface wlan0 --freq 5900 --period 0.5 --logfile cbr_log.csv
```

A sampling rate lower than 0.5s may lead to inaccurate CBR calculations due to insufficient time for counter changes.