from pycbc.catalog import Merger
from pycbc.frame import query_and_read_frame
from pycbc.waveform import get_fd_waveform
from pycbc.filter import matched_filter
from pycbc.psd import interpolate
from pycbc.events.coinc import time_coincidence
from pycbc.psd import welch, interpolate

import numpy as np

from gwpy.timeseries import TimeSeries
from pycbc.types import TimeSeries as PyCBCTimeSeries

import argparse
import csv

def main():
    parser = argparse.ArgumentParser(description="Match strain data with templates")
    parser.add_argument("--h1-trig", type=str, required=True, help="Path to H1 trigger events")
    parser.add_argument("--l1-trig", type=str, required=True, help="Path to L1 trigger events")
    parser.add_argument("--output-file", type=str, required=True, help="Path to output CSV file for potential events")
    args = parser.parse_args()

    h1_triggers = list(csv.DictReader(open(args.h1_trig)))
    l1_triggers = list(csv.DictReader(open(args.l1_trig)))

    h1_idx, l1_idx, slide = time_coincidence(
        np.array([float(t["peak_time"]) for t in h1_triggers]),
        np.array([float(t["peak_time"]) for t in l1_triggers]),
        0.01
    )

    snr_threshold = 10
    potential_events = []
    for h, l in zip(h1_idx, l1_idx):
        h_snr = float(h1_triggers[h]["peak_snr"])
        l_snr = float(l1_triggers[l]["peak_snr"])
        
        combined_snr = np.sqrt(h_snr**2 + l_snr**2)
   
        if combined_snr > snr_threshold:
            potential_events.append((h1_triggers[h], l1_triggers[l], combined_snr))


    with open(args.output_file, 'w+', newline='') as csvfile:
        fieldnames = ["h1_peak_time", "h1_peak_snr", "h1_template", "l1_peak_time", "l1_peak_snr", "l1_template", "combined_snr"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for h_event, l_event, combined_snr in potential_events:
            writer.writerow({
                "h1_peak_time": h_event["peak_time"],
                "h1_peak_snr": h_event["peak_snr"],
                "h1_template": h_event["template"],
                "l1_peak_time": l_event["peak_time"],
                "l1_peak_snr": l_event["peak_snr"],
                "l1_template": l_event["template"],
                "combined_snr": combined_snr
            })



if __name__ == "__main__":
    main()