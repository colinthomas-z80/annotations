#!/usr/bin/env python


import ndcctools.taskvine as vine
import random
import argparse
import getpass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="vine_montage.py",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
    m.tune("hungry-internal", 1)
    m.tune("attempt-schedule-depth", 300)

    region_name = f"region.hdr"
    region = m.declare_file(region_name)

    for data_dir in ["raw_j", "raw_k", "raw_h", "raw_l", "raw_m", "raw_n", "raw_o", "raw_p"]:

        import glob
        raw_input_names = glob.glob(f"{data_dir}/*")

        raw_inputs = {}
        for f in raw_input_names:
            img = m.declare_file(f)
            raw_inputs[img] = {"remote_name":f}

        rimages_name = f"rimages_{data_dir[-1]}.tbl"
        rimages = m.declare_temp() # rimages_{data_dir[-1]}.tbl 
        mimgtbl = vine.Task(
                command = f"mImgtbl {data_dir} {rimages_name}",
                inputs = raw_inputs,
                outputs = {rimages:{"remote_name":rimages_name}},
                semantic_category=data_dir,
                disk=2000,
                cores=12,
                )

        m.submit(mimgtbl)

        
        projected_outputs = {}
        for img in raw_inputs:
            proj_img = m.declare_temp()
            proj_area = m.declare_temp()
            # projected_j/hdu0_2mass-atlas-000121s-j0760009.fits
            proj_name = f"projected_{data_dir[-1]}/hdu0_{raw_inputs[img]['remote_name'].split('/')[-1]}"
            proj_area_name = f"{proj_name.split('.fits')[0]}_area.fits"
            projected_outputs[proj_img] = {"remote_name":proj_name}
            projected_outputs[proj_area] = {"remote_name":proj_area_name}

            t = vine.Task(
                    command = f"mkdir projected_{data_dir[-1]}; mProject {raw_inputs[img]['remote_name']} {proj_name} {region_name}",
                    inputs = {
                                region:{"remote_name":region_name},
                                rimages:{"remote_name":rimages_name},
                                img:raw_inputs[img],
                            },
                    outputs = {
                                proj_img:{"remote_name":proj_name},
                                proj_area:{"remote_name":proj_area_name}
                               },
                    semantic_category=data_dir,
                    cores=1,
                    disk=1000,
                    )

            m.submit(t)


        projected_name = f"projected_{data_dir[-1]}"
        pimages_name = f"pimages_{data_dir[-1]}.tbl"
        pimages = m.declare_temp() # pimages_{data_dir[-1]}.tbl

        mimgtbl_projected = vine.Task(
                command = f"mImgtbl {projected_name} {pimages_name}",
                inputs = projected_outputs,
                outputs = {pimages:{"remote_name":pimages_name}},
                semantic_category=data_dir,
                disk=5000,
                cores=12,
                )
        m.submit(mimgtbl_projected)

        diffstbl_name = f"diffs_{data_dir[-1]}.tbl"
        diffstbl = m.declare_temp() # diffs_{data_dir[-1]}.tbl

        moverlaps = vine.Task(
                command = f"mOverlaps {pimages_name} {diffstbl_name}",
                inputs = {pimages:{"remote_name":pimages_name}},
                outputs = {diffstbl:{"remote_name":diffstbl_name}},
                semantic_category=data_dir,
                disk=5000,
                cores=12,
                )
        m.submit(moverlaps)

        diffs_name = f"diffs_{data_dir[-1]}"

        fitstbl_name = f"fits_{data_dir[-1]}.tbl"
        fitstbl = m.declare_temp() # fits_{data_dir[-1]}.tbl

        mdifffit = vine.Task(
                command = f"mkdir {diffs_name}; mDiffFitExec -p {projected_name} {diffstbl_name} {region_name} {diffs_name} {fitstbl_name}",
                inputs = {
                    diffstbl:{"remote_name":diffstbl_name},
                    region:{"remote_name":region_name}
                    } | projected_outputs,
                outputs = {
                    fitstbl:{"remote_name":f"fits_{data_dir[-1]}.tbl"}
                    },
                semantic_category=data_dir,
                disk=2000,
                cores=12,
                )
        m.submit(mdifffit)

        correctionstbl_name = f"corrections_{data_dir[-1]}.tbl"
        correctionstbl = m.declare_temp() # corrections_{data_dir[-1]}.tbl

        mbgmodel = vine.Task(
                command = f"mBgModel {pimages_name} {fitstbl_name} {correctionstbl_name}",
                inputs = {pimages:{"remote_name":pimages_name},
                    fitstbl:{"remote_name":fitstbl_name}
                    },
                outputs = {correctionstbl:{"remote_name":correctionstbl_name}},
                semantic_category=data_dir,
                disk=2000,
                cores=12,
                )

        m.submit(mbgmodel)

        corrected_name= f"corrected_{data_dir[-1]}"
        corrected = m.declare_temp() # corrected_{data_dir[-1]}

        mbgexec = vine.Task(
                command = f"mkdir {corrected_name}; mBgExec -p {projected_name} {pimages_name} {correctionstbl_name} {corrected_name}",
                inputs = {
                    pimages:{"remote_name":pimages_name},
                    correctionstbl:{"remote_name":correctionstbl_name}
                    } | projected_outputs,
                outputs = {corrected:{"remote_name":f"corrected_{data_dir[-1]}"}},
                semantic_category=data_dir,
                disk=2000,
                cores=12,
                )
        m.submit(mbgexec)

        cimages_name = f"cimages_{data_dir[-1]}.tbl"
        cimages = m.declare_temp() # cimages_{data_dir[-1]}.tbl

        mimgtbl_corrected = vine.Task(
                command = f"mImgtbl corrected_{data_dir[-1]} {cimages_name}",
                inputs = {corrected:{"remote_name":f"{corrected_name}"}},
                outputs = {cimages:{"remote_name":cimages_name}},
                semantic_category=data_dir,
                disk=2000,
                cores=12,
                )
        m.submit(mimgtbl_corrected)

        fitsoutput = m.declare_file(f"{data_dir[-1]}band.fits") # jband.fits

        madd = vine.Task(
                command = f"mAdd -p corrected_{data_dir[-1]} {cimages_name} {region_name} {data_dir[-1]}band.fits",
                inputs = {corrected:{"remote_name":f"corrected_{data_dir[-1]}"},
                    cimages:{"remote_name":cimages_name},
                    region:{"remote_name":region_name}
                    },
                outputs = {fitsoutput:{"remote_name":f"{data_dir[-1]}band.fits"}},
                semantic_category=data_dir,
                disk=2000,
                cores=12,
                )
        m.submit(madd)

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

