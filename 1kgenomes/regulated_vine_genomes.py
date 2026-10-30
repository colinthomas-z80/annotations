#!/usr/bin/env python

# 1000 Genomes with each chromosome as a regulated subgraph: the manager keeps
# --window chromosomes in flight, counts a chromosome when its mutation_overlap
# and frequency tasks both return, and reports a resource signal that
# factory.sh follows to size the worker pool. --replicas repeats the pass over the
# chromosome inputs, giving more subgraphs from the same files.

import ndcctools.taskvine as vine
import argparse
import getpass

# The chromosome and annotation files are read in place from the shared filesystem,
# rather than sent by the manager, which blocks while it sends each 1.2-1.7 GB file.
shared_dir = "/groups/dthain/users/cthoma26/annotations/1kgenomes"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="regulated_vine_genomes.py",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--num-chr",
        nargs="?",
        type=int,
        help="number of chromosome files (sub workflows)",
        default=1,
    )

    parser.add_argument(
        "--replicas",
        nargs="?",
        type=int,
        help="passes over the chromosome files, each chromosome a new subgraph per pass",
        default=1,
    )

    parser.add_argument(
        "--num-individuals",
        nargs="?",
        type=int,
        help="number of individuals tasks to split the input",
        default=3
    )

    parser.add_argument(
        "--name",
        nargs="?",
        type=str,
        help="name to assign to the manager, used by factory.sh to find it.",
        default=f"vine-regulated-genomes-{getpass.getuser()}",
    )
    parser.add_argument(
        "--port",
        nargs="?",
        type=int,
        help="port for the manager to listen for connections. If 0, pick any available.",
        default=9123,
    )
    parser.add_argument("--window", type=int, default=2, help="subgraph-window: chromosomes in flight at once")
    parser.add_argument("--signal-interval", type=float, default=0,
                        help="subgraph-signal-interval in seconds, 0 for automatic (the mean chromosome span)")
    parser.add_argument("--signal-confirm", type=int, default=2,
                        help="subgraph-signal-confirm: consecutive decisions needed to change the signal")
    parser.add_argument("--release", type=int, default=1, help="subgraph-release: workers drained per over-allocated decision")
    parser.add_argument("--concurrency", type=int, default=0,
                        help="peak tasks per chromosome, 0 for its individuals tasks plus the sifting task")

    args = parser.parse_args()

    m = vine.Manager(port=args.port)
    m.set_name(args.name)

    m.tune("subgraph-window", args.window)
    m.tune("subgraph-signal-interval", args.signal_interval)
    m.tune("subgraph-signal-confirm", args.signal_confirm)
    m.tune("subgraph-release", args.release)

    eas = m.declare_file("EAS")
    columns = m.declare_file("columns.txt")
    individuals_exec = m.declare_file("bin/individuals.py")
    individuals_merge_exec = m.declare_file("bin/individuals_merge.py")
    sifting_exec = m.declare_file("bin/sifting.py")
    mut_overlap_exec = m.declare_file("bin/mutation_overlap.py")
    frequency_exec = m.declare_file("bin/frequency.py")

    for subgraph in range(args.num_chr * args.replicas):

        # Passes are submitted in turn, so repeats of a chromosome are num_chr apart.
        chr_num = subgraph % args.num_chr + 1
        rep = subgraph // args.num_chr
        category = f"chr{chr_num}.{rep}"
        m.set_semantic_concurrency(category, args.concurrency or args.num_individuals + 1)

        chr_file_str = f"ALL.chr{chr_num}.250000.vcf"
        sift_file_str = f"ALL.chr{chr_num}.phase3_shapeit2_mvncall_integrated_v5.20130502.sites.annotation.vcf"

        individuals_outputs = []

        for i in range(1, (args.num_individuals*100)+1, 100):
            output_file = m.declare_temp() #m.declare_temp(f"chr{chr_num}n-{i}-{i+100}.tar.gz")

            t = vine.Task(
                command=f"./individuals.py {shared_dir}/{chr_file_str} {chr_num} {i} {i+100} 6000",
                inputs= {
        #            chr_file: {"remote_name" : chr_file_str},
                    individuals_exec: {"remote_name" : "individuals.py"},
                    columns: {"remote_name" : "columns.txt"},
                },
                outputs = {
                    output_file: {"remote_name" : f"chr{chr_num}n-{i}-{i+100}.tar.gz"},
                },
                semantic_category=category,
                memory=1000,
                disk=5000,
                cores=6
            )
            t.worker_selection_algorithm = 2
            individuals_outputs.append(output_file)

            task_id = m.submit(t)
            print(f"submitted task {t.id}: {t.command}")

        merge_output = m.declare_temp() #m.declare_temp(f"chr{chr_num}n.tar.gz")
        merge = vine.Task(
            command=f"./individuals_merge.py {chr_num} {' '.join([f'chr{chr_num}n-{i}-{i+100}.tar.gz' for i, o in enumerate(individuals_outputs)])}",
            inputs={o: {"remote_name" : f"chr{chr_num}n-{i}-{i+100}.tar.gz"} for i, o in enumerate(individuals_outputs)} | {individuals_merge_exec: {"remote_name" : "individuals_merge.py"}},
            outputs={merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"}},
            semantic_category=category,
            disk=5000,
            cores=12
        )
        m.submit(merge)

        sift_output = m.declare_temp() # m.declare_temp(f"sifted.SIFT.chr{chr_num}.txt")
        sift = vine.Task(
            command=f"./sifting.py {shared_dir}/{sift_file_str} {chr_num}",
            inputs={
                sifting_exec: {"remote_name" : "sifting.py"},
            },
            outputs={
                sift_output: {"remote_name" : f"sifted.SIFT.chr{chr_num}.txt"},
            },
            semantic_category=category,
            cores=12,
        )
        m.submit(sift)

        # mutation_overlap and frequency both end the chromosome. Both are outputs,
        # and the chromosome counts once, when the last of them returns.
        mut_output = m.declare_file(f"chr{chr_num}-EAS.{rep}")
        mutation = vine.Task(
            command=f"./mutation_overlap.py -c {chr_num} -pop EAS",
            inputs={
                merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"},
                sift_output: {"remote_name" : f"sifted.SIFT.chr{chr_num}.txt"},
                mut_overlap_exec: {"remote_name" : "mutation_overlap.py"},
                eas: {"remote_name" : "EAS"},
            },
            outputs={
                mut_output: {"remote_name" : f"chr{chr_num}-EAS", "failure_only" : True},
            },
            semantic_category=category,
            semantic_output=True,
            cores=12
        )
        m.submit(mutation)

        frequency_output = m.declare_file(f"chr{chr_num}-EAS-freq.{rep}")
        frequency = vine.Task(
            command=f"./frequency.py -c {chr_num} -pop EAS",
            inputs={
                eas: {"remote_name" : "EAS"},
                merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"},
                columns: {"remote_name" : "columns.txt"},
                sift_output: {"remote_name" : f"sifted.SIFT.chr{chr_num}.txt"},
                frequency_exec: {"remote_name" : "frequency.py"},
            },
            outputs={
                frequency_output: {"remote_name" : f"chr{chr_num}-EAS-freq", "failure_only" : True},
            },
            semantic_category=category,
            semantic_output=True,
            cores=12,
        )
        m.submit(frequency)

    print(f"TaskVine listening for workers on {m.port} as {args.name}")

    print("Waiting for tasks to complete...")
    while not m.empty():
        t = m.wait(5)
        if t:
            if t.successful():
                print(f"task {t.id} result: {t.std_output}")
            elif t.completed():
                print(
                    f"task {t.id} completed with an executin error, exit code {t.exit_code}"
                )
            else:
                print(f"task {t.id} failed with status {t.result}")

    print("all tasks complete!")
# vim: set sts=4 sw=4 ts=4 expandtab ft=python:
