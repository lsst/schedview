import argparse
import glob
import logging
from pathlib import Path

import h5py
import numpy as np


def split_sb_file(in_fname, out_dir, nights):
    in_start_mjd, in_end_mjd = Path(in_fname).stem.split("_")

    in_start_mjd = int(in_start_mjd) if float(in_start_mjd) == int(in_start_mjd) else float(in_start_mjd)
    in_end_mjd = int(in_end_mjd) if float(in_end_mjd) == int(in_end_mjd) else float(in_end_mjd)

    in_sb_h5 = h5py.File(in_fname, "r")
    in_mjds = in_sb_h5["mjds"][:]
    in_sky_mags = in_sb_h5["sky_mags"]

    _timestep_max = np.empty(1, dtype=float)
    in_sb_h5["timestep_max"].read_direct(_timestep_max)
    timestep_max = np.max(_timestep_max)

    for start_mjd in np.arange(in_start_mjd, in_end_mjd, nights):
        # Make sure all all files have exactly nights nights.
        end_mjd = start_mjd + nights
        if end_mjd > in_end_mjd:
            start_mjd = in_end_mjd - nights
            end_mjd = in_end_mjd

        keep = np.where((in_mjds >= start_mjd) & (in_mjds <= end_mjd))
        first_index, last_index = np.min(keep), np.max(keep)
        mjds = in_mjds[first_index:last_index]
        sky_mags = in_sky_mags[first_index:last_index]

        final_sky_mags = np.zeros(
            (mjds.size, in_sky_mags.shape[1]),
            dtype=in_sky_mags.dtype,
        )
        for key in sky_mags.dtype.fields.keys():
            final_sky_mags[key] = sky_mags[key]

        out_fname = Path(out_dir).joinpath(f"{start_mjd}_{end_mjd}.h5")
        logging.info(f"Writing {out_fname}")
        with h5py.File(out_fname, "w") as h5_out:
            h5_out.create_dataset("mjds", data=mjds)
            h5_out.create_dataset("sky_mags", data=final_sky_mags, compression="gzip")
            h5_out.create_dataset("timestep_max", data=timestep_max)

    return out_dir


def split_all(in_dir, out_dir, nights):
    for in_fname in glob.glob(f"{in_dir}/*.h5"):
        logging.info(f"Splitting {in_fname}")
        split_sb_file(in_fname, out_dir, nights)


def main(*args):
    parser = argparse.ArgumentParser(description="split sky brightness files into smaller chunks")
    parser.add_argument("in_directory", type=str, help="Input directory")
    parser.add_argument("out_directory", type=str, help="Output directory")
    parser.add_argument("nights", type=int, help="target nights per file")
    arg_values = parser.parse_args() if len(args) == 0 else parser.parse_args(args)
    in_dir = arg_values.in_directory
    out_dir = arg_values.out_directory
    nights = arg_values.nights

    split_all(in_dir, out_dir, nights)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
