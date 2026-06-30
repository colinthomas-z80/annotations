import ndcctools.taskvine as vine
import argparse
import numpy as np
import subprocess
import os
import csv
import make_inference

def make_inference_job(m, coinc_f, coincident_events_file):
    coincidents = list(csv.DictReader(open(coincident_events_file)))
    if len(coincidents) == 0:
        return
    
    deps = make_inference.make_scripts_ext(coincident_events_file, "wf")
    data_file_number = coincident_events_file.split('_')[1][0]
    chunk_number = coincident_events_file.split('_')[2][0]

    h1_data = m.declare_file(f"data/H1_strain_{data_file_number}.gwf")
    l1_data = m.declare_file(f"data/L1_strain_{data_file_number}.gwf")
    sampler_ini = m.declare_file("inference/emcee.ini")
    priors_ini = m.declare_file("inference/gw150914_like.ini")
    for segment, (data_config_path, run_script_path) in enumerate(deps):
        run_script = m.declare_file(run_script_path)
        print(run_script.source())
        data_config = m.declare_file(data_config_path)

        output = m.declare_file(f"inference_{data_file_number}_{chunk_number}_{segment}.hdf")
        t = vine.Task(
            command = (f"/bin/bash -c 'source /home/scuzee/Programming/annotations/pycbc/env/bin/activate' ;"
                f"./{run_script.source().split('/')[-1]}"),
            inputs = {
                    sampler_ini: {"remote_name": "emcee.ini"},
                    priors_ini: {"remote_name": "gw150914_like.ini"},
                    data_config: {"remote_name": data_config.source().split('/')[-1]},
                    run_script: {"remote_name": run_script.source().split('/')[-1]},
                    h1_data: {"remote_name": f"H1_strain_{data_file_number}.gwf"},
                    l1_data: {"remote_name": f"L1_strain_{data_file_number}.gwf"},
                    coinc_f: {"remote_name": coincident_events_file.split('/')[-1]}
                },
            outputs = {output: {"remote_name": f"inference_{data_file_number}_{chunk_number}_{segment}.hdf"}}
        )
        m.submit(t)

def main():
    parser = argparse.ArgumentParser(description="TaskVine Gravitational Wave Analysis")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to data directory, will glob *.hdf5")
    parser.add_argument("--match-template-range", type=str, required=True, help="Range of templates to search, e.g., '5-10'")
    parser.add_argument("--template-step", type=float, default=1.0, help="Step size for template masses")
    parser.add_argument("--template-split", type=int, default=0, help="Number of templates to process per job")
    args = parser.parse_args()

    if args.template_split == 0:
        args.template_split = int(args.match_template_range.split('-')[1]) - int(args.match_template_range.split('-')[0])


    data_files = [f for f in os.listdir(args.data_dir) if f.endswith(".hdf5")]

    m = vine.Manager(port=9129)

    match_strain = m.declare_file("match_strain.py")
    coincidence = m.declare_file("coincidence.py")
    inference = m.declare_file("make_inference.py")

    pycbc_virtualenv = "env"

    match_outputs = []

    for data_file in data_files:
        data_path = os.path.join(args.data_dir, data_file)
        input_file = m.declare_file(data_path)
        template_start, template_end = map(int, args.match_template_range.split('-'))
        templates = np.arange(template_start, template_end, args.template_step)
        template_chunks = [templates[i:i + args.template_split] for i in range(0, len(templates), args.template_split)]

        for chunk_id, template_chunk in enumerate(template_chunks):
            output_file = m.declare_file(f"{data_file}_match_{chunk_id}.csv")
            t = vine.Task(
                command = (f"/bin/bash -c 'source {pycbc_virtualenv}/bin/activate' ;"
                    "python match_strain.py " 
                    f" --input-file {data_file.split('/')[-1]} " 
                    f" --channel {data_file.split('_')[0]} " 
                    f" --template-range {int(template_chunk[0])}-{int(template_chunk[-1])} " 
                    f" --template-step {args.template_step} " 
                    f" --output-file {output_file.source()}"
                    ),
                inputs = {match_strain : {"remote_name": "match_strain.py"}, input_file: {"remote_name": data_file.split('/')[-1]}},
                outputs={output_file: {"remote_name": f"{data_file}_match_{chunk_id}.csv"}}
            )
            match_outputs.append(output_file)
            m.submit(t)

    coincident_outputs = []
    for data_file in data_files:
        for chunk_id, template_chunk in enumerate(template_chunks):
            if data_file.split('_')[0] == "L1":
                #l1_trig_file = m.declare_file(f"{data_file}_match_{chunk_id}.csv")
                #h1_trig_file = m.declare_file(f"{data_file.replace('L1', 'H1')}_match_{chunk_id}.csv")
                l1_trig_file = [o for o in match_outputs if o.source().endswith(f"{data_file}_match_{chunk_id}.csv")][0]
                h1_trig_file = [o for o in match_outputs if o.source().endswith(f"{data_file.replace('L1', 'H1')}_match_{chunk_id}.csv")][0]
                coincident_output_file = m.declare_file(f"{data_file[3:]}_{chunk_id}_coincident_events.csv")

                t_coincidence = vine.Task(
                    command = (f"/bin/bash -c 'source {pycbc_virtualenv}/bin/activate' ;"
                        "python coincidence.py "
                        f" --h1-trig {h1_trig_file.source()}"
                        f" --l1-trig {l1_trig_file.source()}"
                        f" --output-file {coincident_output_file.source()}"
                    ),
                    inputs = {coincidence: {"remote_name": "coincidence.py"}, h1_trig_file: {"remote_name": h1_trig_file.source()}, l1_trig_file: {"remote_name": l1_trig_file.source()}},
                    outputs={coincident_output_file: {"remote_name": coincident_output_file.source()}}
                )
                coincident_outputs.append(coincident_output_file)
                m.submit(t_coincidence)

    print("Waiting for tasks to complete...")
    while not m.empty():
        t = m.wait(5)
        if t:
            print(f"task {t.id} result: {t.std_output}")
            if t.successful():
                for (output, x, y) in t._tracked_outputs:
                    if output in coincident_outputs:
                        print(f"Coincident events file generated: {output.source()}")
                        make_inference_job(m, output, output.source())

    print("all tasks complete!")


if __name__ == "__main__":
    main()

