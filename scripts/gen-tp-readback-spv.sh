#!/bin/bash
# Generate tp_readback_spv.h from tp_readback.comp (in the glslang container).
set -euxo pipefail
cd /work
glslangValidator -V tp_readback.comp -o /tmp/tp_readback.spv
{
    echo "/* Generated: glslangValidator -V tp_readback.comp (do not edit). */"
    echo "static const uint32_t tp_readback_spv[] = {"
    od -A n -t u4 -v /tmp/tp_readback.spv | tr -s ' \t' ' ' | sed 's/^ //; s/ $//; s/ /, /g; s/$/,/' | sed '$ s/,$//'
    echo "};"
} > /work/tp_readback_spv.h
head -5 /work/tp_readback_spv.h
wc -l /work/tp_readback_spv.h
