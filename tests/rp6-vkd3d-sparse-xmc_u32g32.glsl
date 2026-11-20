#version 450
/* Read a 64-bit two-channel uint view (R32G32_UINT / R32G32_SINT) and store the
 * two raw words: data[2*(y*512+x)] = c.x, data[2*(y*512+x)+1] = c.y.
 *
 * This is the read side of probe XMC: the words are compared with the words that
 * were copied into the image, so the probe asks "did the read hand back the bits
 * that are stored" and nothing else - no numeric interpretation is involved, both
 * ends are integer formats.
 *
 * Embedded SPIR-V: xmc_u32g32_spv[] in rp6-vkd3d-sparse-xmc_spv.h
 * (regenerate: scripts/gen-xmc-spv.sh, in the glslang container)
 */
layout(local_size_x = 32, local_size_y = 32) in;
layout(set = 0, binding = 0) uniform usampler2D img;
layout(set = 0, binding = 1) buffer Out { uint data[]; } outb;
void main() {
    ivec2 uv = ivec2(gl_GlobalInvocationID.xy);
    uvec4 c = texelFetch(img, uv, 0);
    outb.data[2 * (uv.y * 512 + uv.x)] = c.x;
    outb.data[2 * (uv.y * 512 + uv.x) + 1] = c.y;
}
