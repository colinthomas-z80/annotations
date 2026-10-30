import ndcctools.taskvine as vine
import argparse
import getpass
import numpy as np
import subprocess
import os
import csv
import make_inference

# PyCBC with each event and template chunk as a regulated subgraph: its H1 and L1
# match_strain tasks, their coincidence, the inference tasks submitted once the
# coincidence returns, and the collection of the inferences, which is the result.
# The manager keeps --window subgraphs in flight and reports a resource signal
# that factory.sh follows to size the worker pool.

pycbc_virtualenv = "/groups/dthain/users/cthoma26/annotations/pycbc/env"
env_get = f"source ~/.bashrc; source {pycbc_virtualenv}/bin/activate ;"


def subgraph_name(data_file, chunk_id):
    """The H1 and L1 files of one event share a subgraph per template chunk."""
    return f"{data_file[3:].split('.')[0]}_{chunk_id}"


def make_inference_job(m, coinc_f, coincident_events_file, category):
    data_file_number = coincident_events_file.split('_')[1][0]
    chunk_number = coincident_events_file.split('_')[2][0]
    collected_name = f"collected_inferences_{data_file_number}_{chunk_number}"

    coincidents = list(csv.DictReader(open(coincident_events_file)))
    deps = make_inference.make_scripts_ext(coincident_events_file, "wf") if coincidents else []

    if not deps:
        # Without events to infer, an empty collection is the subgraph's result,
        # so that every subgraph produces exactly one.
        empty = vine.Task(
                command = f"touch {collected_name}",
                outputs = {m.declare_file(collected_name): {"remote_name": collected_name}},
                semantic_category=category,
                semantic_output=True,
                cores=1,
            )
        m.submit(empty)
        return

    h1_data = m.declare_file(f"data/H1_strain_{data_file_number}.gwf")
    l1_data = m.declare_file(f"data/L1_strain_{data_file_number}.gwf")
    sampler_ini = m.declare_file("inference/emcee.ini")
    priors_ini = m.declare_file("inference/gw150914_like.ini")

    inference_outputs = []
    inference_outnames = []
    for segment, (data_config_path, run_script_path) in enumerate(deps):
        run_script = m.declare_file(run_script_path)
        print(run_script.source())
        data_config = m.declare_file(data_config_path)

        output = m.declare_temp()#declare_file(f"inference_{data_file_number}_{chunk_number}_{segment}.hdf")
        inference_outputs.append(output)
        inference_outnames.append(f"inference_{data_file_number}_{chunk_number}_{segment}.hdf")
        t = vine.Task(
            command = (f"{env_get}"
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
            semantic_category=category,
            cores=8,
            outputs = {output: {"remote_name": f"inference_{data_file_number}_{chunk_number}_{segment}.hdf"}}
        )
        m.submit(t)

    collect_inferences = vine.Task(
            command = (f"{env_get}"
                f"ls *.hdf | while read f; do cat $f >> {collected_name}; done;"),
                inputs = {
                    i:{"remote_name":inference_outnames[n]} for n,i in enumerate(inference_outputs)
                    },
                outputs = {
                    m.declare_file(collected_name) : {"remote_name":collected_name}
                    },
                semantic_category=category,
                semantic_output=True,
                cores=4,
            )
    m.submit(collect_inferences)

def main():
    parser = argparse.ArgumentParser(description="TaskVine Gravitational Wave Analysis, regulated by subgraph")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to data directory, will glob *.hdf5")
    parser.add_argument("--match-template-range", type=str, required=True, help="Range of templates to search, e.g., '5-10'")
    parser.add_argument("--template-step", type=float, default=1.0, help="Step size for template masses")
    parser.add_argument("--template-split", type=int, default=0, help="Number of templates to process per job")
    parser.add_argument("--name", type=str, default=f"vine-regulated-ligo-{getpass.getuser()}",
                        help="name to assign to the manager, used by factory.sh to find it")
    parser.add_argument("--port", type=int, default=9129, help="port for the manager, 0 for any")
    parser.add_argument("--window", type=int, default=2, help="subgraph-window: subgraphs in flight at once")
    parser.add_argument("--signal-interval", type=float, default=0,
                        help="subgraph-signal-interval in seconds, 0 for automatic (the mean subgraph span)")
    parser.add_argument("--signal-confirm", type=int, default=2,
                        help="subgraph-signal-confirm: consecutive decisions needed to change the signal")
    parser.add_argument("--release", type=int, default=1, help="subgraph-release: workers drained per over-allocated decision")
    parser.add_argument("--concurrency", type=int, default=4,
                        help="peak tasks per subgraph (the inference tasks are only known once the coincidence returns)")
    args = parser.parse_args()

    if args.template_split == 0:
        args.template_split = int(args.match_template_range.split('-')[1]) - int(args.match_template_range.split('-')[0])


    data_files = [f for f in os.listdir(args.data_dir) if f.endswith(".hdf5")]

    m = vine.Manager(port=args.port)
    m.set_name(args.name)

    m.tune("subgraph-window", args.window)
    m.tune("subgraph-signal-interval", args.signal_interval)
    m.tune("subgraph-signal-confirm", args.signal_confirm)
    m.tune("subgraph-release", args.release)

    match_strain = m.declare_file("match_strain.py")
    coincidence = m.declare_file("coincidence.py")
    inference = m.declare_file("make_inference.py")

    match_outputs = {}

    for data_file in data_files:
        data_path = os.path.join(args.data_dir, data_file)
        input_file = m.declare_file(data_path)

        template_start, template_end = map(int, args.match_template_range.split('-'))
        templates = np.arange(template_start, template_end, args.template_split)
        template_chunks = [templates[i:i + args.template_split] for i in range(0, len(templates), args.template_split)]

        for chunk_id, template_chunk in enumerate(template_chunks):
            category = subgraph_name(data_file, chunk_id)
            m.set_semantic_concurrency(category, args.concurrency)

            output_file = m.declare_temp()
            t = vine.Task(
                command = (f"{env_get}"
                    "python match_strain.py "
                    f" --input-file {data_file.split('/')[-1]} "
                    f" --channel {data_file.split('_')[0]} "
                    f" --template-range {int(template_chunk[0])}-{(int(template_chunk[-1]) + 1)} "
                    f" --template-step {args.template_step} "
                    f" --output-file {data_file.split('.')[0]}_match_{chunk_id}.csv"
                    ),
                inputs = {match_strain : {"remote_name": "match_strain.py"}, input_file: {"remote_name": data_file.split('/')[-1]}},
                outputs={output_file: {"remote_name": f"{data_file.split('.')[0]}_match_{chunk_id}.csv"}},
                semantic_category=category,
                cores=4,
            )

            if data_file in match_outputs.keys():
                match_outputs[data_file] += [output_file]
            else:
                match_outputs[data_file] = [output_file]

            m.submit(t)

    coincident_outputs = []
    coincident_category = {}
    for data_file in data_files:
        for chunk_id, template_chunk in enumerate(template_chunks):
            if data_file.split('_')[0] == "L1":
                l1_trig_file = match_outputs[data_file][chunk_id]
                l1_src = f"{data_file.split('.')[0]}_match_{chunk_id}.csv"
                h1_src = "H1" + l1_src[2:]
                h1_data = "H1" + data_file[2:]
                h1_trig_file = match_outputs[h1_data][chunk_id]
                coincident_output_file = m.declare_file(f"{data_file[3:].split('.')[0]}_{chunk_id}_coincident_events.csv")
                category = subgraph_name(data_file, chunk_id)

                t_coincidence = vine.Task(
                    command = (f"{env_get}"
                        "python coincidence.py "
                        f" --h1-trig {h1_src}"
                        f" --l1-trig {l1_src}"
                        f" --output-file {coincident_output_file.source()}"
                    ),
                    inputs = {coincidence: {"remote_name": "coincidence.py"}, h1_trig_file: {"remote_name": h1_src}, l1_trig_file: {"remote_name": l1_src}},
                    outputs={coincident_output_file: {"remote_name": coincident_output_file.source()}},
                    semantic_category=category,
                    cores=1,
                )
                coincident_outputs.append(coincident_output_file)
                coincident_category[coincident_output_file] = category
                m.submit(t_coincidence)

    print(f"TaskVine listening for workers on {m.port} as {args.name}")

    print("Waiting for tasks to complete...")
    while not m.empty():
        t = m.wait(5)
        if t:
            print(f"task {t.id} result: {t.std_output}")
            if t.successful():
                for (output, x, y) in t._tracked_outputs:
                    if output in coincident_outputs:
                        print(f"Coincident events file generated: {output.source()}")
                        make_inference_job(m, output, output.source(), coincident_category[output])

    print("all tasks complete!")


if __name__ == "__main__":
    main()

