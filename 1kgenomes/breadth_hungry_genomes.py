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
    #m.tune("reset-sched-cursor", 1)
    #m.tune("attempt-schedule-depth", args.schedule_depth)
    #m.tune("max-retrievals", 0)

    eas = m.declare_file("EAS")
    columns = m.declare_file("columns.txt")
    individuals_exec = m.declare_file("bin/individuals.py")
    individuals_merge_exec = m.declare_file("bin/individuals_merge.py")
    sifting_exec = m.declare_file("bin/sifting.py")
    mut_overlap_exec = m.declare_file("bin/mutation_overlap.py")
    frequency_exec = m.declare_file("bin/frequency.py")
    
    subgraph_priority = 1000

    all_tasks = []
    indiv_tasks = []
    merge_tasks = []
    sift_tasks = []
    mut_tasks = []
    freq_tasks = []


    for chr_num in range(1, args.num_chr + 1):
        chr_tasks = []


        chr_file_str = f"ALL.chr{chr_num}.250000.vcf"
        sift_file_str = f"ALL.chr{chr_num}.phase3_shapeit2_mvncall_integrated_v5.20130502.sites.annotation.vcf"

        #chr_file = m.declare_file(chr_file_str, cache=True)
        sift_file = m.declare_file(sift_file_str, cache=True)

        individuals_outputs = []

        for i in range(1, (args.num_individuals*100)+1, 100):
            output_file = m.declare_temp() #m.declare_temp(f"chr{chr_num}n-{i}-{i+100}.tar.gz")

            t = vine.Task(
                command=f"./individuals.py /groups/dthain/users/cthoma26/annotations/1kgenomes/{chr_file_str} {chr_num} {i} {i+100} 6000",
                inputs= {
        #            chr_file: {"remote_name" : chr_file_str},
                    individuals_exec: {"remote_name" : "individuals.py"},
                    columns: {"remote_name" : "columns.txt"},
                },
                outputs = {
                    output_file: {"remote_name" : f"chr{chr_num}n-{i}-{i+100}.tar.gz"},
                },
                priority=subgraph_priority,
                #category=f"{chr_num}",
                memory=1000,
                disk=5000,
                cores=4
            )
            t.worker_selection_algorithm = 2
            individuals_outputs.append(output_file)

            indiv_tasks.append(t)
#            print(f"submitted task {t.id}: {t.command}")

        merge_output = m.declare_temp() #m.declare_temp(f"chr{chr_num}n.tar.gz")
        merge = vine.Task(
            command=f"./individuals_merge.py {chr_num} {' '.join([f"chr{chr_num}n-{i}-{i+100}.tar.gz" for i, o in enumerate(individuals_outputs)])}",
            inputs={o: {"remote_name" : f"chr{chr_num}n-{i}-{i+100}.tar.gz"} for i, o in enumerate(individuals_outputs)} | {individuals_merge_exec: {"remote_name" : "individuals_merge.py"}},
            outputs={merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"}},
            #category=f"{chr_num}",
            disk=5000,
            priority=subgraph_priority,
            cores=12
        )
        merge.worker_selection_algorithm = 2
        merge_tasks.append(merge)

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
            priority=subgraph_priority,
            #category=f"{chr_num}",
            cores=12,
        )
        sift.worker_selection_algorithm = 2
        sift_tasks.append(sift)

        #mut_output = m.declare_file(f"chr{chr_num}-EAS")
        mut_output = m.declare_file(f"fakeput-mut")
        mutation = vine.Task(
            command=f"./mutation_overlap.py -c {chr_num} -pop EAS; echo hello > fakeput-mut",
            inputs={
                merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"},
                sift_output: {"remote_name" : f"sifted.SIFT.chr{chr_num}.txt"},
                mut_overlap_exec: {"remote_name" : "mutation_overlap.py"},
                eas: {"remote_name" : "EAS"},
            },
            outputs={
                mut_output: {"remote_name" : mut_output.source(), "failure_only" : True},
                mut_output: {"remote_name" : "fakeput-mut"},
            },
            priority=subgraph_priority,
            #category=f"{chr_num}",
            cores=12
        )
        mutation.worker_selection_algorithm = 2
        mut_tasks.append(mutation)

#        frequency_output = m.declare_file(f"chr{chr_num}-EAS-freq")
        frequency_output = m.declare_file(f"fakeput-freq")
        frequency = vine.Task(
            command=f"./frequency.py -c {chr_num} -pop EAS; echo hello > fakeput-freq",
            inputs={
                eas: {"remote_name" : "EAS"},
                merge_output: {"remote_name" : f"chr{chr_num}n.tar.gz"},
                columns: {"remote_name" : "columns.txt"},
                sift_output: {"remote_name" : f"sifted.SIFT.chr{chr_num}.txt"},
                frequency_exec: {"remote_name" : "frequency.py"},
            },
            outputs={
#                frequency_output: {"remote_name" : frequency_output.source(), "failure_only" : True},
            frequency_output: {"remote_name" : "fakeput-freq"},
            },
            priority=subgraph_priority,
            category=f"{chr_num}",
            cores=12,
        )
        frequency.worker_selection_algorithm = 2
        freq_tasks.append(frequency)

        subgraph_priority -= 10

    for i in range(5):
        indiv_tasks.append(merge_tasks.pop(0))
        sift_tasks.append(mut_tasks.pop(0))
        merge_tasks.append(freq_tasks.pop(0))

    top_ordering = indiv_tasks + sift_tasks + merge_tasks + mut_tasks + freq_tasks

    print(f"TaskVine listening for workers on {m.port}")
    while len(top_ordering):
        while m.hungry() and len(top_ordering):
                task_id = m.submit(top_ordering.pop(0))
                print(f"submitted task {task_id}")

        if not m.empty():
            t = m.wait(5)
            if t:
                if t.successful():
                    print(f"task {t.id} complete")
                elif t.completed():
                    print(
                        f"task {t.id} exited {t.exit_code}"
                    )
                else:
                    print(f"task {t.id} failed with status {t.result}")
    

    while not m.empty():
        t = m.wait(5)
        if t:
            print(f"task {t.id} complete")
    print("all tasks complete!")
# vim: set sts=4 sw=4 ts=4 expandtab ft=python:
