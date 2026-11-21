#version 450
#extension GL_EXT_shader_image_int64 : require
#extension GL_ARB_gpu_shader_int64 : require
/* Read a 64-bit single-channel integer view (R64_UINT) through a STORAGE image
 * and store the two raw words: data[2*(y*512+x)] = low, data[+1] = high.
 *
 * This is the reader for the one member of the 64-bit compatibility class that
 * probe XMC deliberately avoided (tests/rp6-vkd3d-sparse-test.c, probe_xr64).
 * R64_UINT is not a sampled format on this driver: tu_formats.cc grants it
 * STORAGE and TRANSFER features only (under has_64b_image_atomics), so the
 * texture unit may not be used and the only legal reader is an image descriptor.
 *
 * Embedded SPIR-V: xr64_load_spv[] in rp6-vkd3d-sparse-xr64_spv.h
 * (regenerate: scripts/gen-xr64-spv.sh, in the glslang container)
 */
layout(local_size_x = 32, local_size_y = 32) in;
layout(set = 0, binding = 0, r64ui) uniform u64image2D img;
layout(set = 0, binding = 1) buffer Out { uint data[]; } outb;
void main() {
    ivec2 uv = ivec2(gl_GlobalInvocationID.xy);
    u64vec4 r = imageLoad(img, uv);
    uint64_t v = r.x;
    outb.data[2 * (uv.y * 512 + uv.x)] = uint(v & 0xFFFFFFFFul);
    outb.data[2 * (uv.y * 512 + uv.x) + 1] = uint(v >> 32u);
}
