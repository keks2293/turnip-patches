#version 450
/* Read a 64-bit four-channel uint view (R16G16B16A16_UINT / _SINT) and store the
 * four raw channel values as words: the driver zero-extends each 16-bit channel,
 * so the four words are the 64 stored bits split in halves.
 *
 * This is the read side of probe XMC together with rp6-vkd3d-sparse-xmc_u32g32.glsl:
 * both read the same image through a view of one of the two UBWC compat types the
 * 64-bit class contains, and both are compared with the words that were copied in.
 * No numeric interpretation is involved, both ends are integer formats.
 *
 * Embedded SPIR-V: xmc_u32x4_spv[] in tests/rp6-vkd3d-sparse-xmc_spv.h
 * (regenerate: scripts/gen-xmc-spv.sh, in the glslang container)
 */
layout(local_size_x = 32, local_size_y = 32) in;
layout(set = 0, binding = 0) uniform usampler2D img;
layout(set = 0, binding = 1) buffer Out { uint data[]; } outb;
void main() {
    ivec2 uv = ivec2(gl_GlobalInvocationID.xy);
    uvec4 c = texelFetch(img, uv, 0);
    outb.data[4 * (uv.y * 512 + uv.x) + 0] = c.x;
    outb.data[4 * (uv.y * 512 + uv.x) + 1] = c.y;
    outb.data[4 * (uv.y * 512 + uv.x) + 2] = c.z;
    outb.data[4 * (uv.y * 512 + uv.x) + 3] = c.w;
}
