#!/usr/bin/env python


import ndcctools.taskvine as vine
import random
import argparse
import getpass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="vine_genomes.py",
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
        help="name to assign to the manager.",
        default=f"vine-blast-{getpass.getuser()}",
    )
    parser.add_argument(
        "--port",
        nargs="?",
        type=int,
        help="port for the manager to listen for connections. If 0, pick any available.",
        default=9123,
    )

    args = parser.parse_args()

    m = vine.Manager(port=args.port)
    m.set_name(args.name)


    m.tune("wait-for-workers", 5)

    eas = m.declare_file("EAS")
    columns = m.declare_file("columns.txt")
    individuals_exec = m.declare_file("bin/individuals.py")
    individuals_merge_exec = m.declare_file("bin/individuals_merge.py")
    sifting_exec = m.declare_file("bin/sifting.py")
    mut_overlap_exec = m.declare_file("bin/mutation_overlap.py")
    frequency_exec = m.declare_file("bin/frequency.py")
    
    subgraph_priority = 1

    for chr_num in range(1, args.num_chr + 1):

        chr_file_str = f"ALL.chr{chr_num}.250000.vcf"
        sift_file_str = f"ALL.chr{chr_num}.phase3_shapeit2_mvncall_integrated_v5.20130502.sites.annotation.vcf"

        chr_file = m.declare_file(chr_file_str, cache=True)
        sift_file = m.declare_file(sift_file_str, cache=True)

        individuals_outputs = []

        for i in range(1, (args.num_individuals*100)+1, 100):
            output_file = m.declare_temp() #m.declare_temp(f"chr{chr_num}n-{i}-{i+100}.tar.gz")

            t = vine.Task(
                command=f"./individuals.py {chr_file_str} {chr_num} {i} {i+100} 6000",
                inputs= {
                    chr_file: {"remote_name" : chr_file_str},
                    individuals_exec: {"remote_name" : "individuals.py"},
                    columns: {"remote_name" : "columns.txt"},
                },
                outputs = {
                    output_file: {"remote_name" : f"chr{chr_num}n-{i}-{i+100}.tar.gz"},
                },
                priority=1*subgraph_priority,
                category=f"{chr_num}",
                memory=1000,
                disk=5000,
                cores=1
            )
            t.worker_selection_algorithm = 2
            individuals_outputs.append(output_file)

            task_id = m.submit(t)
            print(f"submitted task {t.id}: {t.command}")

        merge_output = m.declare_temp() #m.declare_temp(f"chr{chr_num}n.tar.gz")
        merge = vine.Task(
            command=f"./individuals_merge.py {chr_num} {' '.join([f"chr{chr_num}n-{i}-{i+100}.tar.gz" for i, o in enumerate(individuals_outputs)])}",
            inputs={o: {"remote_name" : f"chr{chr_num}n-{i}-{i+100}.tar.gz"} for i, o in enumerate(individuals_outputs)} | {individuals_merge_exec: {"remote_name" : "individuals_merge.py"}},
            outputs={merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"}},
            category=f"{chr_num}",
            disk=5000,
            priority=2*subgraph_priority
        )
        merge.worker_selection_algorithm = 2
        m.submit(merge)

        sift_output = m.declare_temp() # m.declare_temp(f"sifted.SIFT.chr{chr_num}.txt")
        sift = vine.Task(
            command=f"./sifting.py {sift_file_str} {chr_num}",
            inputs={
                sift_file: {"remote_name" : sift_file_str},
                sifting_exec: {"remote_name" : "sifting.py"},
            },
            outputs={
                sift_output: {"remote_name" : f"sifted.SIFT.chr{chr_num}.txt"},
            },
            priority=3*subgraph_priority,
            category=f"{chr_num}"
        )
        sift.worker_selection_algorithm = 2
        m.submit(sift)

        mut_output = m.declare_file(f"chr{chr_num}-EAS")
        mutation = vine.Task(
            command=f"./mutation_overlap.py -c {chr_num} -pop EAS",
            inputs={
                merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"},
                sift_output: {"remote_name" : f"sifted.SIFT.chr{chr_num}.txt"},
                mut_overlap_exec: {"remote_name" : "mutation_overlap.py"},
                eas: {"remote_name" : "EAS"},
            },
            outputs={
                mut_output: {"remote_name" : mut_output.source()},
            },
            priority=4*subgraph_priority,
            category=f"{chr_num}"
        )
        mutation.worker_selection_algorithm = 2
        m.submit(mutation)

        frequency_output = m.declare_file(f"chr{chr_num}-EAS-freq")
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
                frequency_output: {"remote_name" : frequency_output.source()},
            },
            priority=4*subgraph_priority,
            category=f"{chr_num}"
        )
        frequency.worker_selection_algorithm = 2
        m.submit(frequency)

        subgraph_priority += 1

    print(f"TaskVine listening for workers on {m.port}")

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
