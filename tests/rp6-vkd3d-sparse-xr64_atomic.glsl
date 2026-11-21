#version 450
#extension GL_EXT_shader_image_int64 : require
#extension GL_ARB_gpu_shader_int64 : require
#extension GL_EXT_shader_atomic_int64 : require
/* Add 1 to every 64-bit word of a R64_UINT STORAGE image.
 *
 * The write direction of probe XR64: the question is not whether a compressed
 * image can be read through an R64 view (the load shader asks that), but whether
 * an atomic on such a view lands on the same words, so that a later read shows
 * exactly the +1 that was added.
 *
 * Embedded SPIR-V: xr64_atomic_spv[] in rp6-vkd3d-sparse-xr64_spv.h
 * (regenerate: scripts/gen-xr64-spv.sh, in the glslang container)
 */
layout(local_size_x = 32, local_size_y = 32) in;
layout(set = 0, binding = 0, r64ui) uniform u64image2D img;
void main() {
    imageAtomicAdd(img, ivec2(gl_GlobalInvocationID.xy), uint64_t(1));
}
