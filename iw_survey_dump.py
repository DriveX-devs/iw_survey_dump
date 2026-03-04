import re
import subprocess
import time
import argparse
from dataclasses import dataclass
from typing import Optional, Tuple, List

@dataclass
class SurveyBlock:
    freq_mhz: Optional[int] = None
    in_use: bool = False
    active_ms: Optional[int] = None
    busy_ms: Optional[int] = None
    rx_ms: Optional[int] = None
    tx_ms: Optional[int] = None
    noise_dbm: Optional[int] = None


def parse_iw_survey_dump(output: str, target_freq_mhz: int = 5910) -> Optional[Tuple[int, int, int, int]]:
    chunks = re.split(r"\n(?=Survey data from )", output.strip())
    blocks: List[SurveyBlock] = []

    re_freq = re.compile(r"^\s*frequency:\s*(\d+)\s*MHz(\s*\[in use\])?\s*$", re.MULTILINE)
    re_active = re.compile(r"^\s*channel active time:\s*(\d+)\s*ms\s*$", re.MULTILINE)
    re_busy = re.compile(r"^\s*channel busy time:\s*(\d+)\s*ms\s*$", re.MULTILINE)
    re_rx = re.compile(r"^\s*channel receive time:\s*(\d+)\s*ms\s*$", re.MULTILINE)
    re_tx = re.compile(r"^\s*channel transmit time:\s*(\d+)\s*ms\s*$", re.MULTILINE)
    re_noise = re.compile(r"^\s*noise:\s*(-?\d+)\s*dBm\s*$", re.MULTILINE)

    for ch in chunks:
        if not ch.startswith("Survey data from"):
            continue

        b = SurveyBlock()

        m = re_freq.search(ch)
        if m:
            b.freq_mhz = int(m.group(1))
            b.in_use = bool(m.group(2))

        for regex, attr in [
            (re_active, "active_ms"),
            (re_busy, "busy_ms"),
            (re_rx, "rx_ms"),
            (re_tx, "tx_ms"),
            (re_noise, "noise_dbm")
        ]:
            m = regex.search(ch)
            if m:
                setattr(b, attr, int(m.group(1)))

        blocks.append(b)

    def complete(x: SurveyBlock) -> bool:
        return all([
            x.active_ms is not None,
            x.busy_ms is not None,
            x.rx_ms is not None,
            x.tx_ms is not None,
            x.freq_mhz is not None,
            x.noise_dbm is not None
        ])

    for b in blocks:
        if b.freq_mhz == target_freq_mhz and complete(b):
            return b.active_ms, b.busy_ms, b.rx_ms, b.tx_ms, b.noise_dbm

    return None


@dataclass
class Data:
    first_time: bool = True
    start_active_time: int = 0
    start_busy_time: int = 0
    start_receive_time: int = 0
    start_transmit_time: int = 0


class Computer:
    def __init__(self):
        self.data = Data()

    def compute(self, active_time, busy_time, rx_time, tx_time) -> Optional[Tuple[int, int, int, int, float]]:
        d = self.data

        if d.first_time:
            d.first_time = False
            d.start_active_time = active_time
            d.start_busy_time = busy_time
            d.start_receive_time = rx_time
            d.start_transmit_time = tx_time
            return None

        # reset detection
        if (active_time < d.start_active_time or
            busy_time < d.start_busy_time or
            rx_time < d.start_receive_time or
            tx_time < d.start_transmit_time):

            d.start_active_time = active_time
            d.start_busy_time = busy_time
            d.start_receive_time = rx_time
            d.start_transmit_time = tx_time
            return None

        delta_active = active_time - d.start_active_time
        delta_busy = busy_time - d.start_busy_time
        delta_rx = rx_time - d.start_receive_time
        delta_tx = tx_time - d.start_transmit_time

        cbr = None
        if delta_active > 0:
            cbr = float(delta_busy) / float(delta_active)
            cbr = max(0.0, min(1.0, cbr))

        d.start_active_time = active_time
        d.start_busy_time = busy_time
        d.start_receive_time = rx_time
        d.start_transmit_time = tx_time

        return delta_active, delta_busy, delta_rx, delta_tx, cbr


def read_iw_survey(iface: str) -> str:
    result = subprocess.run(
        ["iw", "dev", iface, "survey", "dump"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def run_logging(iface: str, period_s: float, target_freq_mhz: int, logfile=None):

    assert period_s > 0.0, "Period must be positive"
    assert target_freq_mhz > 0, "Target frequency must be positive"
    assert iface, "Interface name must be non-empty"

    computer = Computer()

    next_deadline = time.monotonic()
    try:
        while True:
            output = read_iw_survey(iface)
            parsed = parse_iw_survey_dump(output, target_freq_mhz=target_freq_mhz)

            if parsed:
                active, busy, rx, tx, noise_dbm = parsed
                result = computer.compute(active, busy, rx, tx)

                if result:
                    delta_active, delta_busy, delta_rx, delta_tx, cbr_value = result
                    timestamp = time.time()
                    # Print to console in a human-readable format
                    print(
                        f"timestamp={timestamp:.3f}\n",
                        f"delta_active={delta_active}\n",
                        f"delta_busy={delta_busy}\n",
                        f"delta_rx={delta_rx}\n",
                        f"delta_tx={delta_tx}\n",
                        f"noise_dbm={noise_dbm}\n",
                        f"cbr={cbr_value:.6f}\n"
                    )
                    print("\n\n")
                    if logfile:
                        # Write like a csv file
                        with open(logfile, "a") as f:
                            f.write(f"{timestamp:.3f},{delta_active},{delta_busy},{delta_rx},{delta_tx},{noise_dbm},{cbr_value:.6f}\n")

            next_deadline += period_s
            sleep_time = next_deadline - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_deadline = time.monotonic()

    except Exception as e:
        print(f"An error occurred: {e}")
        exit(-1)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Logger for iw survey dump")
    parser.add_argument("--iface", required=True, help="Wireless interface to monitor")
    parser.add_argument("--period", required=True, type=float, default=0.5, help="Sampling period in seconds")
    parser.add_argument("--logfile", default=None, help="Output log file")
    parser.add_argument("--freq", required=True, type=int, default=5900, help="Target frequency in MHz")

    args = parser.parse_args()
    run_logging(
        iface=args.iface,
        period_s=args.period,
        target_freq_mhz=args.freq,
        logfile=args.logfile,
    )
