#!/bin/bash

mHdr "NGC 3372" 2.0 region.hdr

# Perform the same processing as in the single-band example
# script (singleband.sh) for all three 2MASS wavelengths.

mImgtbl min_raw_j rimages_j.tbl
mProjExec -q -p min_raw_j rimages_j.tbl region.hdr projected_j stats.tbl
mImgtbl projected_j pimages_j.tbl
mOverlaps pimages_j.tbl diffs_j.tbl
mDiffFitExec -p projected_j diffs_j.tbl region.hdr diffs_j fits_j.tbl
mBgModel pimages_j.tbl fits_j.tbl corrections_j.tbl
mBgExec -p projected_j pimages_j.tbl corrections_j.tbl corrected_j
mImgtbl corrected_j cimages_j.tbl
mAdd -p corrected_j cimages_j.tbl region.hdr jband.fits

mImgtbl min_raw_h rimages_h.tbl
mProjExec -q -p min_raw_h rimages_h.tbl region.hdr projected_h stats.tbl
mImgtbl projected_h pimages_h.tbl
mOverlaps pimages_h.tbl diffs_h.tbl
mDiffFitExec -p projected_h diffs_h.tbl region.hdr diffs_h fits_h.tbl
mBgModel pimages_h.tbl fits_h.tbl corrections_h.tbl
mBgExec -p projected_h pimages_h.tbl corrections_h.tbl corrected_h
mImgtbl corrected_h cimages_h.tbl
mAdd -p corrected_h cimages_h.tbl region.hdr hband.fits

mImgtbl min_raw_k rimages_k.tbl
mProjExec -q -p min_raw_k rimages_k.tbl region.hdr projected_k stats.tbl
mImgtbl projected_k pimages_k.tbl
mOverlaps pimages_k.tbl diffs_k.tbl
mDiffFitExec -p projected_k diffs_k.tbl region.hdr diffs_k fits_k.tbl
mBgModel pimages_k.tbl fits_k.tbl corrections_k.tbl
mBgExec -p projected_k pimages_k.tbl corrections_k.tbl corrected_k
mImgtbl corrected_k cimages_k.tbl
mAdd -p corrected_k cimages_k.tbl region.hdr kband.fits


# And make a color PNG image of the result.

mShrink kband.fits ksmall.fits 5
mShrink hband.fits hsmall.fits 5
mShrink jband.fits jsmall.fits 5

mViewer -t 2 \
        -red   ksmall.fits 0s max gaussian-log \
        -green hsmall.fits 0s max gaussian-log \
        -blue  jsmall.fits 0s max gaussian-log \
        -out   color_mosaic.png

mViewer -ct 1 -gray jsmall.fits -2s max gaussian-log -out mosaic.png