import argparse
import csv
import os
import numpy as np


def make_scripts_ext(coincident_events_file, output_dir):
    coincidents = list(csv.DictReader(open(coincident_events_file)))

    data_file_number = coincident_events_file.split('_')[1][0]
    chunk_number = coincident_events_file.split('_')[2][0]

    base = 1126259400
    segment_id = 0

    deps = []
    for event in coincidents:
        # do not process events outside of base time
        if int(float(event["h1_peak_time"])) < base:
            continue
        #print("Mass H1: ", templates[int(event["h1_template"])], "Mass L1: ", templates[int(event["l1_template"])])

        data_config = f"""
[data]
instruments = H1 L1
trigger-time = {int(float(event["h1_peak_time"]))}
analysis-start-time = -1
analysis-end-time = 1
psd-estimation = median-mean
psd-start-time = -1
psd-end-time = 1
psd-inverse-length = 2
psd-segment-length = 1
psd-segment-stride = 1
frame-files = H1:H1_strain_{data_file_number}.gwf L1:L1_strain_{data_file_number}.gwf
channel-name = H1:Strain L1:Strain
sample-rate = 2048
strain-high-pass = 15
pad-data = 0
"""

        # priors = f"""[prior]
        
        
        # """

        nprocs = 4
        run_script = f'''
#!/bin/bash
OMP_NUM_THREADS=1 \
pycbc_inference --verbose \
--seed 1897234 \
--config-file gw150914_like.ini data_{data_file_number}_{chunk_number}_{segment_id}.ini emcee.ini \
--output-file inference_{data_file_number}_{chunk_number}_{segment_id}.hdf \
--nprocesses {nprocs} \
--force
'''

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        data_config_path = f"{output_dir}/data_{data_file_number}_{chunk_number}_{segment_id}.ini"
        with open(data_config_path, "w+") as f:
            f.write(data_config)

        run_script_path = f"{output_dir}/run_{data_file_number}_{chunk_number}_{segment_id}.sh"
        with open(run_script_path, "w+") as f:
            f.write(run_script)

        os.chmod(run_script_path, 0o755)

        deps.append((data_config_path, run_script_path))
        segment_id += 1
    return deps


def main():
    parser = argparse.ArgumentParser(description="Search for gravitational wave signals in strain data")
    parser.add_argument("--coincident-events", type=str, required=True, help="Path to coincident events CSV file")
    parser.add_argument("--output-dir", type=str, required=True, help="Directory to save output files")
    parser.add_argument("--name-pattern", type=str, required=True, help="Name pattern for output files")
    parser.add_argument("--template-range", type=str, required=True, help="Range of templates to search, e.g., '5-10'")
    parser.add_argument("--template-step", type=float, default=1.0, help="Step size for template masses")
    args = parser.parse_args()


    templates = []
    template_start, template_end = map(int, args.template_range.split('-'))
    for m1 in np.arange(template_start, template_end + 1, args.template_step):
            for m2 in np.arange(template_start, template_end + 1, args.template_step):
                templates.append((m1, m2))

    coincidents = list(csv.DictReader(open(args.coincident_events)))

    base = 1126259400
    segment_id = 0
    for event in coincidents:
        #print("Mass H1: ", templates[int(event["h1_template"])], "Mass L1: ", templates[int(event["l1_template"])])

        data_config = f"""[data]
        instruments = H1 L1
        trigger-time = {event["h1_peak_time"]}
        analysis-start-time = {float(event["h1_peak_time"])%10}
        analysis-end-time = {float(event["h1_peak_time"])%10 + 10}
        psd-estimation = median-mean
        psd-start-time = -10
        psd-end-time = 10
        psd-inverse-length = 8
        psd-segment-length = 2
        psd-segment-stride = 1
        frame-files = H1:H1_strain_{segment_id}.gwf L1:L1_strain_{segment_id}.gwf
        channel-name = H1:Strain L1:Strain
        sample-rate = 2048
        strain-high-pass = 15
        pad-data = 0
        """

        # priors = f"""[prior]
        
        
        # """

        nprocs = 4
        run_script = f'''
        #!/bin/bash
        OMP_NUM_THREADS=1 \
        pycbc_inference --verbose \
            --seed 1897234 \
            --config-file gw150914_like.ini data_{segment_id}.ini emcee.ini \
            --output-file inference_{segment_id}.hdf \
            --nprocesses {nprocs} \
            --force
        '''

        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)

        with open(f"{args.output_dir}/data_{args.name_pattern}_{segment_id}.ini", "w+") as f:
            f.write(data_config)

        with open(f"{args.output_dir}/run_{args.name_pattern}_{segment_id}.sh", "w+") as f:
            f.write(run_script)

        segment_id += 1


if __name__ == "__main__":
    main()