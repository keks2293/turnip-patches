#!/bin/bash
# Generate tp_write_spv.h from tp_write.comp (in the glslang container).
set -euxo pipefail
cd /work
glslangValidator -V tp_write.comp -o /tmp/tp_write.spv
{
    echo "/* Generated: glslangValidator -V tp_write.comp (do not edit). */"
    echo "static const uint32_t tp_write_spv[] = {"
    od -A n -t u4 -v /tmp/tp_write.spv | tr -s ' \t' ' ' | sed 's/^ //; s/ $//; s/ /, /g; s/$/,/' | sed '$ s/,$//'
    echo "};"
} > /work/tp_write_spv.h
head -5 /work/tp_write_spv.h
wc -l /work/tp_write_spv.h
