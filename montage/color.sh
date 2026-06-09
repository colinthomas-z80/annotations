#!/bin/bash

mHdr "NGC 3372" 2.0 region.hdr

# Perform the same processing as in the single-band example
# script (singleband.sh) for all three 2MASS wavelengths.

mImgtbl raw_j rimages.tbl
mProjExec -q -p raw_j rimages.tbl region.hdr projected_j stats.tbl
mImgtbl projected_j pimages.tbl
mOverlaps pimages.tbl diffs_j.tbl
mDiffFitExec -p projected_j diffs_j.tbl region.hdr diffs_j fits_j.tbl
mBgModel pimages.tbl fits_j.tbl corrections_j.tbl
mBgExec -p projected_j pimages.tbl corrections_j.tbl corrected_j
mImgtbl corrected_j cimages.tbl
mAdd -p corrected_j cimages.tbl region.hdr jband.fits

# mImgtbl raw_h rimages.tbl
# mProjExec -q -p raw_h rimages.tbl region.hdr projected_h stats.tbl
# mImgtbl projected_h pimages.tbl
# mOverlaps pimages.tbl diffs_h.tbl
# mDiffFitExec -p projected_h diffs_h.tbl region.hdr diffs_h fits_h.tbl
# mBgModel pimages.tbl fits_h.tbl corrections_h.tbl
# mBgExec -p projected_h pimages.tbl corrections_h.tbl corrected_h
# mImgtbl corrected_h cimages.tbl
# mAdd -p corrected_h cimages.tbl region.hdr hband.fits

# mImgtbl raw_k rimages.tbl
# mProjExec -q -p raw_k rimages.tbl region.hdr projected_k stats.tbl
# mImgtbl projected_k pimages.tbl
# mOverlaps pimages.tbl diffs_k.tbl
# mDiffFitExec -p projected_k diffs_k.tbl region.hdr diffs_k fits_k.tbl
# mBgModel pimages.tbl fits_k.tbl corrections_k.tbl
# mBgExec -p projected_k pimages.tbl corrections_k.tbl corrected_k
# mImgtbl corrected_k cimages.tbl
# mAdd -p corrected_k cimages.tbl region.hdr kband.fits


# And make a color PNG image of the result.

#mShrink kband.fits ksmall.fits 5
# mShrink hband.fits hsmall.fits 5
mShrink jband.fits jsmall.fits 5

# mViewer -t 2 \
#         -red   ksmall.fits 0s max gaussian-log \
#         -green hsmall.fits 0s max gaussian-log \
#         -blue  jsmall.fits 0s max gaussian-log \
#         -out   color_mosaic.png

mViewer -ct 1 -gray jsmall.fits -2s max gaussian-log -out mosaic.png