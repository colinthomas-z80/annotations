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

def build_template(m1, m2, delta_f):

    hp, hc = get_fd_waveform(
        approximant="TaylorF2",
        mass1=m1,
        mass2=m2,
        delta_f=delta_f,
        f_lower=20
    )

    return hp


def search_template(template_id,
                    m1,
                    m2,
                    strain):

    strain = strain.highpass_fir(15, 8)
    
    psd = interpolate(welch(strain), 1.0 / strain.duration)

    template = build_template(
        m1,
        m2,
        1.0 / strain.duration
    )

    template.resize(len(strain) // 2 + 1)

    snr = matched_filter(
        template,
        strain,
        psd=psd,
        low_frequency_cutoff=20
    )

    # filter rolloff 
    snr = snr[len(snr) // 4: len(snr) * 3 // 4]

    peak = abs(snr).numpy().max()

    peak_index = abs(snr).numpy().argmax()

    peak_time = float(
        snr.sample_times[peak_index]
    )

    return {
        "template": template_id,
        "peak_snr": float(peak),
        "peak_time": peak_time
    }


def main():

    parser = argparse.ArgumentParser(description="Match strain data with templates")
    parser.add_argument("--input-file", type=str, required=True, help="Path to input data file")
    parser.add_argument("--channel", type=str, required=True, help="Channel name for the strain data")
    parser.add_argument("--template-range", type=str, required=True, help="Range of templates to search, e.g., '10-15'")
    parser.add_argument("--template-step", type=float, default=1.0, help="Step size for template masses")
    parser.add_argument("--output-file", type=str, required=True, help="Path to output CSV file")
    args = parser.parse_args()

    input_file = args.input_file

    input_strain_ts = TimeSeries.read(input_file)
    
    input_strain_ts = PyCBCTimeSeries(
	    input_strain_ts.value,
	    delta_t=input_strain_ts.dt.value,
	    epoch=input_strain_ts.t0.value
    )

    templates = []

    template_range = args.template_range.split("-")
    m1_start = int(template_range[0])
    m1_end = int(template_range[1])

    for m1 in np.arange(m1_start, m1_end + 1, float(args.template_step)):
            for m2 in np.arange(m1_start, m1_end + 1, float(args.template_step)):
                templates.append((m1, m2))

    match_results = []
    for template_id, (m1, m2) in enumerate(templates):
        result = search_template(
            template_id,
            m1,
            m2,
            input_strain_ts
        )
        match_results.append(result)
    
    threshold = 5

    triggers = []
    for result in match_results:
        if result["peak_snr"] >= threshold:
            result["channel"] = args.channel
            triggers.append(result)

    
    # write csv file with triggers
    import csv
    with open(args.output_file, "w+", newline="") as csvfile:
        fieldnames = ["template", "peak_snr", "peak_time", "channel"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for trigger in triggers:
            writer.writerow(trigger)

if __name__ == "__main__":
    main()
