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


    chr_file_str = "ALL.chr1.250000.vcf"
    sift_file_str = "ALL.chr1.phase3_shapeit2_mvncall_integrated_v5.20130502.sites.annotation.vcf"

    chr_file = m.declare_file(chr_file_str)
    sift_file = m.declare_file(sift_file_str)
    columns = m.declare_file("columns.txt")

    individuals_exec = m.declare_file("bin/individuals.py")
    individuals_merge_exec = m.declare_file("bin/individuals_merge.py")
    sifting_exec = m.declare_file("bin/sifting.py")
    mut_overlap_exec = m.declare_file("bin/mutation_overlap.py")
    frequency_exec = m.declare_file("bin/frequency.py")

    individuals_outputs = []

    for i in range(1, (args.num_individuals*100)+1, 100):
        output_file = m.declare_file(f"chr1n-{i}-{i+100}.tar.gz")

        t = vine.Task(
            command=f"./individuals.py {chr_file_str} 1 {i} {i+100} 6000",
            inputs= {
                chr_file: {"remote_name" : chr_file_str},
                individuals_exec: {"remote_name" : "individuals.py"},
                columns: {"remote_name" : "columns.txt"},
            },
            outputs = {
                output_file: {"remote_name" : f"chr1n-{i}-{i+100}.tar.gz"},
            }
        )
        individuals_outputs.append(output_file)

        task_id = m.submit(t)
        print(f"submitted task {t.id}: {t.command}")

    merge_output = m.declare_file("chr1n.tar.gz")
    merge = vine.Task(
        command=f"./individuals_merge.py 1 {' '.join([o.source() for o in individuals_outputs])}",
        inputs={o: {"remote_name" : o.source()} for o in individuals_outputs} | {individuals_merge_exec: {"remote_name" : "individuals_merge.py"}},
        outputs={merge_output: {"remote_name" : "chr1n.tar.gz"}}
    )
    m.submit(merge)

    sift_output = m.declare_file("sifted.SIFT.chr1.txt")
    sift = vine.Task(
        command=f"./sifting.py {sift_file_str} 1",
        inputs={
            sift_file: {"remote_name" : sift_file_str},
            sifting_exec: {"remote_name" : "sifting.py"},
        },
        outputs={
            sift_output: {"remote_name" : "sifted.SIFT.chr1.txt"},
        }
    )
    m.submit(sift)

    eas = m.declare_file("EAS")
    mut_output = m.declare_file("chr1-EAS")
    mutation = vine.Task(
        command=f"./mutation_overlap.py -c 1 -pop EAS",
        inputs={
            merge_output: {"remote_name" : merge_output.source()},
            sift_output: {"remote_name" : sift_output.source()},
            mut_overlap_exec: {"remote_name" : "mutation_overlap.py"},
            eas: {"remote_name" : "EAS"},
        },
        outputs={
            mut_output: {"remote_name" : mut_output.source()},
        }
    )
    m.submit(mutation)

    frequency_output = m.declare_file("chr1-EAS-freq")
    frequency = vine.Task(
        command=f"./frequency.py -c 1 -pop EAS",
        inputs={
            eas: {"remote_name" : "EAS"},
            merge_output: {"remote_name" : merge_output.source()},
            columns: {"remote_name" : "columns.txt"},
            sift_output: {"remote_name" : sift_output.source()},
            frequency_exec: {"remote_name" : "frequency.py"},
        },
        outputs={
            frequency_output: {"remote_name" : frequency_output.source()},
        }
    )
    m.submit(frequency)

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
