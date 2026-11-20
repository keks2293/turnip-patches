/* tp8bpp.c - standalone 8bpp-UBWC probe (findings 4.10, exp-17/18).
 *
 * Why a separate binary: the 8bpp question is answered by three probes that
 * take seconds, but in rp6-vkd3d-sparse-test they sit behind ~20 minutes of
 * other workloads, and an environment override of the UBWC geometry
 * (TU_8BPP_UBWC, exp-17) can make the 2D engine hang the GPU before the
 * interesting probe is ever reached. This tool runs only:
 *
 *   AA  R8_UNORM 512x512, filled by imageStore (3D/TP path), read by
 *       texelFetch and by vkCmdCopyImageToBuffer (2D);
 *   AB  the same image filled by vkCmdCopyBufferToImage (2D engine);
 *   Z   NV12 512x512, Y plane filled and read back through copies - the
 *       driver forces those through the 3D engine and does NOT gate them on
 *       has_8bpp_ubwc, so it says whether cpp=1 UBWC works on this chip at all.
 *
 * Each of AA/AB also runs on a LINEAR image: without that control a zero
 * could be the tool's own bug.
 *
 * Run: VK_DRIVER_FILES=<icd.json> [FD_DEV_FEATURES=has_8bpp_ubwc=1]
 *      [TU_8BPP_UBWC=32x8] ./tp8bpp [dump-prefix]
 *      (-DW=.. -DH=.. at compile time picks another image size)
 * The dump-prefix writes <prefix>_AA_tiled.bin and friends with the whole
 * allocation (metadata plane first, then the data plane) after the fill, for
 * offline analysis by scripts/ubwc-dump-analyze.py.
 *
 * Reading the output: the texelFetch/i2b lines print the number of WRONG
 * elements ("<bad>/<total> ... MISMATCH", 0 = EXACT), not the number of good
 * ones. Two more caveats, both measured (analysis 22.1): the texelFetch path is
 * only under control at width 512 (at 256/64 it disagrees with its own linear
 * control), and at heights <= 16 both readers fail even for the linear image -
 * probe defects at small sizes, not UBWC behaviour. Prefer i2b, whose linear
 * control is EXACT at every size tested.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

/* Image size: the probe is one size per binary, but a -DW=.. -DH=.. build lets
 * the same source answer "does the loss start at a given size" (findings 4.10:
 * the metadata that the hardware writes for R8 looks like one 1 KB meta tile).
 */
#ifndef W
#define W 512
#endif
#ifndef H
#define H 512
#endif

#include "tp_readback_spv.h"
#include "tp_write_spv.h"

static void chk(VkResult r, const char *what)
{
    if (r != VK_SUCCESS)
        printf("[ERROR] %s -> %d\n", what, (int)r);
}

static const char *vkerr(VkResult r)
{
    switch (r) {
    case VK_SUCCESS: return "SUCCESS";
    case VK_ERROR_OUT_OF_HOST_MEMORY: return "OUT_OF_HOST_MEMORY";
    case VK_ERROR_OUT_OF_DEVICE_MEMORY: return "OUT_OF_DEVICE_MEMORY";
    case VK_ERROR_INITIALIZATION_FAILED: return "INITIALIZATION_FAILED";
    case VK_ERROR_DEVICE_LOST: return "DEVICE_LOST";
    default: return "err";
    }
}

static VkResult alloc_mem(VkDevice dev, VkDeviceSize size, uint32_t type, VkDeviceMemory *out)
{
    VkMemoryAllocateInfo mai = { VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, size, type };
    return vkAllocateMemory(dev, &mai, NULL, out);
}

/* Compute pipeline from embedded SPIR-V (entry "main", local size 32x32). */
static VkPipeline make_compute_pipe(VkDevice dev, VkPipelineLayout pl, const uint32_t *code,
                                    uint32_t code_size)
{
    VkShaderModuleCreateInfo smci = { VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0,
                                      code_size, code };
    VkShaderModule mod;
    if (vkCreateShaderModule(dev, &smci, NULL, &mod) != VK_SUCCESS)
        return VK_NULL_HANDLE;
    VkPipelineShaderStageCreateInfo ss = { VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                                           NULL, 0, VK_SHADER_STAGE_COMPUTE_BIT, mod, "main", NULL };
    VkComputePipelineCreateInfo cpc = { VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, NULL, 0, ss,
                                        pl, NULL, 0 };
    VkPipeline pipe = VK_NULL_HANDLE;
    VkResult r = vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpc, NULL, &pipe);
    vkDestroyShaderModule(dev, mod, NULL);
    return r == VK_SUCCESS ? pipe : VK_NULL_HANDLE;
}

/* texelFetch the whole 512x512 image into a buffer, hand the words back.
 * Words are r|g<<8|b<<16|a<<24; for R8_UNORM that is v | 0xff000000. */
static int tp_readback_words(VkDevice dev, VkQueue q, VkCommandPool pool, VkImage img,
                             VkFormat fmt, uint32_t **out)
{
    VkImageView v = VK_NULL_HANDLE;
    VkSampler sam = VK_NULL_HANDLE;
    VkDescriptorSetLayout dsl = VK_NULL_HANDLE;
    VkPipelineLayout pl = VK_NULL_HANDLE;
    VkPipeline pipe = VK_NULL_HANDLE;
    VkDescriptorPool dp = VK_NULL_HANDLE;
    VkDescriptorSet ds = VK_NULL_HANDLE;
    VkBuffer rb = VK_NULL_HANDLE;
    VkDeviceMemory rbm = VK_NULL_HANDLE;
    int ok = 0;

    VkImageViewCreateInfo ivci = { .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
                                   .image = img,
                                   .viewType = VK_IMAGE_VIEW_TYPE_2D,
                                   .format = fmt,
                                   .subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 } };
    if (vkCreateImageView(dev, &ivci, NULL, &v) != VK_SUCCESS)
        goto out;
    VkSamplerCreateInfo sci = { .sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,
                                .magFilter = VK_FILTER_NEAREST,
                                .minFilter = VK_FILTER_NEAREST,
                                .mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST,
                                .addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                                .addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                                .addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE };
    if (vkCreateSampler(dev, &sci, NULL, &sam) != VK_SUCCESS)
        goto out;

    VkDescriptorSetLayoutBinding dsb[3] = {
        { 0, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL },
        { 1, VK_DESCRIPTOR_TYPE_SAMPLER, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL },
        { 2, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL },
    };
    VkDescriptorSetLayoutCreateInfo dslci = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                              NULL, 0, 3, dsb };
    if (vkCreateDescriptorSetLayout(dev, &dslci, NULL, &dsl) != VK_SUCCESS)
        goto out;
    VkPipelineLayoutCreateInfo plci = { VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, 1,
                                        &dsl, 0, NULL };
    if (vkCreatePipelineLayout(dev, &plci, NULL, &pl) != VK_SUCCESS)
        goto out;
    pipe = make_compute_pipe(dev, pl, tp_readback_spv, (uint32_t)sizeof(tp_readback_spv));
    if (pipe == VK_NULL_HANDLE)
        goto out;

    VkBufferCreateInfo rbci = { VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0,
                                (VkDeviceSize)W * H * 4, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                                VK_SHARING_MODE_EXCLUSIVE, 0, NULL };
    if (vkCreateBuffer(dev, &rbci, NULL, &rb) != VK_SUCCESS)
        goto out;
    VkMemoryRequirements rbr;
    vkGetBufferMemoryRequirements(dev, rb, &rbr);
    if (alloc_mem(dev, rbr.size, 0, &rbm) != VK_SUCCESS)
        goto out;
    if (vkBindBufferMemory(dev, rb, rbm, 0) != VK_SUCCESS)
        goto out;

    VkDescriptorPoolSize dpsz[3] = { { VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 1 },
                                     { VK_DESCRIPTOR_TYPE_SAMPLER, 1 },
                                     { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1 } };
    VkDescriptorPoolCreateInfo dpci = { VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, NULL, 0, 1,
                                        3, dpsz };
    if (vkCreateDescriptorPool(dev, &dpci, NULL, &dp) != VK_SUCCESS)
        goto out;
    VkDescriptorSetAllocateInfo dai = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, NULL, dp, 1,
                                        &dsl };
    if (vkAllocateDescriptorSets(dev, &dai, &ds) != VK_SUCCESS)
        goto out;
    VkDescriptorImageInfo dii = { sam, v, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL };
    VkDescriptorBufferInfo bfi = { rb, 0, (VkDeviceSize)W * H * 4 };
    VkWriteDescriptorSet wd[3] = {
        { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds, 0, 0, 1,
          VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, &dii, NULL, NULL },
        { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds, 1, 0, 1, VK_DESCRIPTOR_TYPE_SAMPLER,
          &dii, NULL, NULL },
        { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds, 2, 0, 1,
          VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, NULL, &bfi, NULL },
    };
    vkUpdateDescriptorSets(dev, 3, wd, 0, NULL);

    VkCommandBuffer cb;
    VkCommandBufferAllocateInfo cai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL, pool,
                                        VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1 };
    if (vkAllocateCommandBuffers(dev, &cai, &cb) != VK_SUCCESS)
        goto out;
    VkCommandBufferBeginInfo bbi = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL,
                                     VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL };
    vkBeginCommandBuffer(cb, &bbi);
    VkImageSubresourceRange full = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    VkImageMemoryBarrier imb = { VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, NULL,
                                 VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT,
                                 VK_IMAGE_LAYOUT_UNDEFINED,
                                 VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, 0, 0, img, full };
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         0, 0, NULL, 0, NULL, 1, &imb);
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
    vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, NULL);
    vkCmdDispatch(cb, W / 32, H / 32, 1);
    vkEndCommandBuffer(cb);
    VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &cb, 0, NULL };
    if (vkQueueSubmit(q, 1, &si, NULL) != VK_SUCCESS || vkQueueWaitIdle(q) != VK_SUCCESS) {
        vkFreeCommandBuffers(dev, pool, 1, &cb);
        goto out;
    }
    vkFreeCommandBuffers(dev, pool, 1, &cb);

    unsigned char *got;
    if (vkMapMemory(dev, rbm, 0, rbr.size, 0, (void **)&got) != VK_SUCCESS)
        goto out;
    *out = malloc((size_t)W * H * 4);
    if (*out) {
        memcpy(*out, got, (size_t)W * H * 4);
        ok = 1;
    }
    vkUnmapMemory(dev, rbm);
out:
    if (dp && ds)
        vkFreeDescriptorSets(dev, dp, 1, &ds);
    if (dp)
        vkDestroyDescriptorPool(dev, dp, NULL);
    if (pipe)
        vkDestroyPipeline(dev, pipe, NULL);
    if (pl)
        vkDestroyPipelineLayout(dev, pl, NULL);
    if (dsl)
        vkDestroyDescriptorSetLayout(dev, dsl, NULL);
    if (sam)
        vkDestroySampler(dev, sam, NULL);
    if (rb)
        vkDestroyBuffer(dev, rb, NULL);
    if (rbm)
        vkFreeMemory(dev, rbm, NULL);
    if (v)
        vkDestroyImageView(dev, v, NULL);
    return ok;
}

static unsigned pat(unsigned x, unsigned y)
{
    return (x * 31 + y * 17 + 7) & 0xff;
}

static void good_map(const uint32_t *tp, const char *tag)
{
    /* 8x8 cells over the actual image, so a -DW=64 build still prints a sane
     * map instead of reading past the readback buffer. */
    unsigned cw = W / 8 ? W / 8 : 1, ch = H / 8 ? H / 8 : 1;
    printf("%s map 8x8 (good %%), cell %ux%u:\n", tag, cw, ch);
    for (unsigned by = 0; by * ch < H; by++) {
        printf("  ");
        for (unsigned bx = 0; bx * cw < W; bx++) {
            unsigned good = 0, tot = 0;
            for (unsigned y = by * ch; y < (by + 1) * ch && y < H; y++)
                for (unsigned x = bx * cw; x < (bx + 1) * cw && x < W; x++) {
                    good += tp[(size_t)y * W + x] == (pat(x, y) | 0xff000000u);
                    tot++;
                }
            printf("%3u ", tot ? good * 100 / tot : 0);
        }
        printf("\n");
    }
}

/* AA/AB. R8_UNORM 512x512, written either by imageStore (3D) or by
 * vkCmdCopyBufferToImage (2D), read by texelFetch and by vkCmdCopyImageToBuffer.
 * The linear tiling is the control for the tool itself. */
static void probe_r8(VkDevice dev, VkQueue q, VkCommandPool pool, const char *tag,
                     VkImageTiling tiling, int fill_by_shader, const char *dump)
{
    const VkDeviceSize bytes = (VkDeviceSize)W * H;
    VkImage img = VK_NULL_HANDLE;
    VkDeviceMemory mem = VK_NULL_HANDLE;
    VkImageView iv = VK_NULL_HANDLE;
    VkDescriptorSetLayout dsl = VK_NULL_HANDLE;
    VkPipelineLayout pl = VK_NULL_HANDLE;
    VkPipeline pipe = VK_NULL_HANDLE;
    VkDescriptorPool dp = VK_NULL_HANDLE;
    VkDescriptorSet ds = VK_NULL_HANDLE;
    VkBuffer fb = VK_NULL_HANDLE, cb2 = VK_NULL_HANDLE;
    VkDeviceMemory fbm = VK_NULL_HANDLE, cbm = VK_NULL_HANDLE;
    uint32_t *tp = NULL;

    VkImageCreateInfo ici = { VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, NULL, 0, VK_IMAGE_TYPE_2D,
                              VK_FORMAT_R8_UNORM, { W, H, 1 }, 1, 1, VK_SAMPLE_COUNT_1_BIT, tiling,
                              VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                                  VK_IMAGE_USAGE_TRANSFER_DST_BIT |
                                  (fill_by_shader ? VK_IMAGE_USAGE_STORAGE_BIT : 0),
                              VK_SHARING_MODE_EXCLUSIVE, 0, NULL, VK_IMAGE_LAYOUT_UNDEFINED };
    if (vkCreateImage(dev, &ici, NULL, &img) != VK_SUCCESS) {
        printf("%s vkCreateImage failed\n", tag);
        return;
    }
    VkMemoryRequirements mr;
    vkGetImageMemoryRequirements(dev, img, &mr);
    printf("%s R8_UNORM %s fill=%s memreq=0x%llx linear=0x%llx -> %s\n", tag,
           tiling == VK_IMAGE_TILING_LINEAR ? "linear" : "tiled", fill_by_shader ? "3D" : "2D",
           (unsigned long long)mr.size, (unsigned long long)bytes,
           mr.size > bytes ? "UBWC metadata present" : "no metadata");

    if (alloc_mem(dev, mr.size, 0, &mem) != VK_SUCCESS ||
        vkBindImageMemory(dev, img, mem, 0) != VK_SUCCESS) {
        printf("%s image memory failed\n", tag);
        goto out;
    }

    /* the staging buffer for the 2D fill and for the i2b read */
    VkBufferCreateInfo bci = { VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, bytes,
                               VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                               VK_SHARING_MODE_EXCLUSIVE, 0, NULL };
    if (vkCreateBuffer(dev, &bci, NULL, &fb) != VK_SUCCESS)
        goto out;
    VkMemoryRequirements br;
    vkGetBufferMemoryRequirements(dev, fb, &br);
    if (alloc_mem(dev, br.size, 0, &fbm) != VK_SUCCESS ||
        vkBindBufferMemory(dev, fb, fbm, 0) != VK_SUCCESS)
        goto out;
    if (vkCreateBuffer(dev, &bci, NULL, &cb2) != VK_SUCCESS)
        goto out;
    if (alloc_mem(dev, br.size, 0, &cbm) != VK_SUCCESS ||
        vkBindBufferMemory(dev, cb2, cbm, 0) != VK_SUCCESS)
        goto out;

    if (fill_by_shader) {
        VkImageViewCreateInfo ivci = { .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
                                       .image = img,
                                       .viewType = VK_IMAGE_VIEW_TYPE_2D,
                                       .format = VK_FORMAT_R8_UNORM,
                                       .subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0,
                                                             1 } };
        if (vkCreateImageView(dev, &ivci, NULL, &iv) != VK_SUCCESS)
            goto out;
        VkDescriptorSetLayoutBinding dsb = { 0, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1,
                                             VK_SHADER_STAGE_COMPUTE_BIT, NULL };
        VkDescriptorSetLayoutCreateInfo dslci = {
            VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, NULL, 0, 1, &dsb };
        if (vkCreateDescriptorSetLayout(dev, &dslci, NULL, &dsl) != VK_SUCCESS)
            goto out;
        VkPipelineLayoutCreateInfo plci = { VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0,
                                            1, &dsl, 0, NULL };
        if (vkCreatePipelineLayout(dev, &plci, NULL, &pl) != VK_SUCCESS)
            goto out;
        pipe = make_compute_pipe(dev, pl, tp_write_spv, (uint32_t)sizeof(tp_write_spv));
        if (pipe == VK_NULL_HANDLE) {
            printf("%s tp_write pipeline failed\n", tag);
            goto out;
        }
        VkDescriptorPoolSize dpsz = { VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1 };
        VkDescriptorPoolCreateInfo dpci = { VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, NULL, 0,
                                            1, 1, &dpsz };
        if (vkCreateDescriptorPool(dev, &dpci, NULL, &dp) != VK_SUCCESS)
            goto out;
        VkDescriptorSetAllocateInfo dai = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, NULL, dp,
                                            1, &dsl };
        if (vkAllocateDescriptorSets(dev, &dai, &ds) != VK_SUCCESS)
            goto out;
        VkDescriptorImageInfo dii = { VK_NULL_HANDLE, iv, VK_IMAGE_LAYOUT_GENERAL };
        VkWriteDescriptorSet wd = { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds, 0, 0, 1,
                                    VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, &dii, NULL, NULL };
        vkUpdateDescriptorSets(dev, 1, &wd, 0, NULL);
    } else {
        unsigned char *p = NULL;
        chk(vkMapMemory(dev, fbm, 0, br.size, 0, (void **)&p), "map fill");
        for (unsigned y = 0; y < H; y++)
            for (unsigned x = 0; x < W; x++)
                p[(size_t)y * W + x] = (unsigned char)pat(x, y);
        vkUnmapMemory(dev, fbm);
    }

    /* the fill, in its own submit */
    {
        VkCommandBuffer c;
        VkCommandBufferAllocateInfo cai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL,
                                            pool, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1 };
        if (vkAllocateCommandBuffers(dev, &cai, &c) != VK_SUCCESS)
            goto out;
        VkCommandBufferBeginInfo b = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL,
                                       VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL };
        vkBeginCommandBuffer(c, &b);
        VkImageSubresourceRange full = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
        VkImageMemoryBarrier to_dst = { VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, NULL, 0,
                                        fill_by_shader ? VK_ACCESS_SHADER_WRITE_BIT
                                                       : VK_ACCESS_TRANSFER_WRITE_BIT,
                                        VK_IMAGE_LAYOUT_UNDEFINED,
                                        fill_by_shader ? VK_IMAGE_LAYOUT_GENERAL
                                                       : VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                                        0, 0, img, full };
        vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                             fill_by_shader ? VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT
                                            : VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0, 0, NULL, 0, NULL, 1, &to_dst);
        if (fill_by_shader) {
            vkCmdBindPipeline(c, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
            vkCmdBindDescriptorSets(c, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, NULL);
            vkCmdDispatch(c, W / 32, H / 32, 1);
        } else {
            /* twice: the first r2d into a fresh image writes ~2% zeros (5.20) */
            VkBufferImageCopy cp = { 0, 0, 0, { VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1 }, { 0, 0, 0 },
                                     { W, H, 1 } };
            vkCmdCopyBufferToImage(c, fb, img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &cp);
            vkCmdCopyBufferToImage(c, fb, img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &cp);
        }
        VkImageMemoryBarrier to_rd = { VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, NULL,
                                       fill_by_shader ? VK_ACCESS_SHADER_WRITE_BIT
                                                      : VK_ACCESS_TRANSFER_WRITE_BIT,
                                       VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_TRANSFER_READ_BIT,
                                       fill_by_shader ? VK_IMAGE_LAYOUT_GENERAL
                                                      : VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                                       VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, 0, 0, img, full };
        vkCmdPipelineBarrier(c,
                             fill_by_shader ? VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT
                                            : VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT | VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0, 0, NULL, 0, NULL, 1, &to_rd);
        vkEndCommandBuffer(c);
        VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &c, 0, NULL };
        chk(vkQueueSubmit(q, 1, &si, NULL), "submit fill");
        chk(vkQueueWaitIdle(q), "wait fill");
        vkFreeCommandBuffers(dev, pool, 1, &c);
    }

    /* read 1: the texture path */
    if (!tp_readback_words(dev, q, pool, img, VK_FORMAT_R8_UNORM, &tp)) {
        printf("%s texelFetch failed\n", tag);
        goto out;
    }
    {
        unsigned bad = 0, zeros = 0, first = 0;
        for (unsigned y = 0; y < H; y++)
            for (unsigned x = 0; x < W; x++) {
                unsigned i = y * W + x;
                if (tp[i] != (pat(x, y) | 0xff000000u)) {
                    if (!bad)
                        first = i;
                    bad++;
                }
                if ((tp[i] & 0xff) == 0)
                    zeros++;
            }
        printf("%s texelFetch: %u/%u words MISMATCH%s zeros(r)=%u first=(x%u,y%u) got=0x%08x "
               "want=0x%08x\n", tag, bad, (unsigned)bytes, bad ? "" : " (EXACT)", zeros, first % W,
               first / W, tp[first], pat(first % W, first / W) | 0xff000000u);
        if (bad)
            good_map(tp, tag);
    }

    /* Raw allocation.  For a UBWC image the metadata plane comes FIRST: the
     * kernel expects it at the start of the buffer, and fd6_get_plane_layouts()
     * says so ("Place the UBWC slices before the uncompressed slices").  The
     * first revision of this probe split the allocation at W*H counted from the
     * front, which labels the two planes backwards; the percentages it printed
     * were not a map of anything.  Split from the END instead, and keep the
     * caveat that "the data plane is dense" does not mean "the content is
     * there": a UBWC block is not stored in linear byte order, see
     * scripts/ubwc-dump-analyze.py for the search that shows this.
     */
    {
        void *raw = NULL;
        if (vkMapMemory(dev, mem, 0, mr.size, 0, &raw) == VK_SUCCESS) {
            const unsigned char *p = raw;
            size_t data_sz = bytes < mr.size ? (size_t)bytes : mr.size;
            size_t mbytes = mr.size - data_sz;
            const unsigned char *meta = p, *data = p + mbytes;
            size_t lin = 0, mnz = 0, dzero = 0;
            for (size_t i = 0; i < data_sz; i++) {
                lin += data[i] == (unsigned char)pat(i % W, i / W);
                dzero += data[i] == 0;
            }
            for (size_t i = 0; i < mbytes; i++)
                mnz += meta[i] != 0;
            printf("%s raw: meta=%zu B nonzero=%zu, data=%zu B matches the LINEAR pattern "
                   "%zu (%.1f%%), zeros=%zu (%.1f%%)\n",
                   tag, mbytes, mnz, data_sz, lin, 100.0 * lin / data_sz, dzero,
                   100.0 * dzero / data_sz);
            if (data_sz < 65536)
                printf("%s raw: (the split above is memreq minus W*H; on small images "
                       "metadata and tile alignment are the same few KiB, so the meta "
                       "number there is not a plane size)\n", tag);
            if (dump) {
                char fn[512];
                snprintf(fn, sizeof(fn), "%s_%.2s_%s.bin", dump, tag,
                         strstr(tag, "tiled") ? "tiled" : "linear");
                FILE *f = fopen(fn, "wb");
                if (f) {
                    fwrite(p, 1, mr.size, f);
                    fclose(f);
                    printf("%s dump: %s\n", tag, fn);
                }
            }
            vkUnmapMemory(dev, mem);
        }
    }

    /* read 2: the 2D copy engine */
    {
        VkCommandBuffer c;
        VkCommandBufferAllocateInfo cai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL,
                                            pool, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1 };
        if (vkAllocateCommandBuffers(dev, &cai, &c) != VK_SUCCESS)
            goto out;
        VkCommandBufferBeginInfo b = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL,
                                       VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL };
        vkBeginCommandBuffer(c, &b);
        VkImageSubresourceRange full = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
        VkImageMemoryBarrier to_src = { VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, NULL,
                                        VK_ACCESS_SHADER_READ_BIT, VK_ACCESS_TRANSFER_READ_BIT,
                                        VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
                                        VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, 0, 0, img, full };
        vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                             VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, 1, &to_src);
        VkBufferImageCopy cp = { 0, 0, 0, { VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1 }, { 0, 0, 0 },
                                 { W, H, 1 } };
        vkCmdCopyImageToBuffer(c, img, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, cb2, 1, &cp);
        vkEndCommandBuffer(c);
        VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &c, 0, NULL };
        if (vkQueueSubmit(q, 1, &si, NULL) != VK_SUCCESS || vkQueueWaitIdle(q) != VK_SUCCESS) {
            printf("%s i2b submit failed\n", tag);
            vkFreeCommandBuffers(dev, pool, 1, &c);
            goto out;
        }
        vkFreeCommandBuffers(dev, pool, 1, &c);
    }
    {
        unsigned char *got = NULL;
        if (vkMapMemory(dev, cbm, 0, br.size, 0, (void **)&got) != VK_SUCCESS)
            goto out;
        unsigned bad = 0, zeros = 0, first = 0;
        for (unsigned y = 0; y < H; y++)
            for (unsigned x = 0; x < W; x++) {
                size_t i = (size_t)y * W + x;
                if (got[i] != (unsigned char)pat(x, y)) {
                    if (!bad)
                        first = (unsigned)i;
                    bad++;
                }
                if (got[i] == 0)
                    zeros++;
            }
        printf("%s i2b: %u/%u bytes MISMATCH%s zeros=%u first=(x%u,y%u) got=0x%02x want=0x%02x\n",
               tag, bad, (unsigned)bytes, bad ? "" : " (EXACT)", zeros, first % W, first / W,
               got[first], (unsigned char)pat(first % W, first / W));
        vkUnmapMemory(dev, cbm);
    }

out:
    free(tp);
    if (fb)
        vkDestroyBuffer(dev, fb, NULL);
    if (fbm)
        vkFreeMemory(dev, fbm, NULL);
    if (cb2)
        vkDestroyBuffer(dev, cb2, NULL);
    if (cbm)
        vkFreeMemory(dev, cbm, NULL);
    if (ds)
        vkFreeDescriptorSets(dev, dp, 1, &ds);
    if (dp)
        vkDestroyDescriptorPool(dev, dp, NULL);
    if (pipe)
        vkDestroyPipeline(dev, pipe, NULL);
    if (pl)
        vkDestroyPipelineLayout(dev, pl, NULL);
    if (dsl)
        vkDestroyDescriptorSetLayout(dev, dsl, NULL);
    if (iv)
        vkDestroyImageView(dev, iv, NULL);
    if (mem)
        vkFreeMemory(dev, mem, NULL);
    if (img)
        vkDestroyImage(dev, img, NULL);
}

/* Z. NV12 512x512, plane 0 (Y8, cpp=1 UBWC, {32,8}): the driver does NOT gate
 * this on has_8bpp_ubwc and forces its copies through the 3D engine, so it is
 * the reference for "does this chip compress 8bpp at all". */
static void probe_nv12(VkDevice dev, VkQueue q, VkCommandPool pool, const char *tag,
                       VkImageTiling tiling, const char *dump)
{
    const VkDeviceSize p0 = (VkDeviceSize)W * H;
    const VkDeviceSize lin_total = p0 + (VkDeviceSize)(W / 2) * (H / 2) * 2;

    VkImageCreateInfo iic = { VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, NULL, 0, VK_IMAGE_TYPE_2D,
                              VK_FORMAT_G8_B8R8_2PLANE_420_UNORM, { W, H, 1 }, 1, 1,
                              VK_SAMPLE_COUNT_1_BIT, tiling,
                              VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT,
                              VK_SHARING_MODE_EXCLUSIVE, 0, NULL, VK_IMAGE_LAYOUT_UNDEFINED };
    VkImage img = VK_NULL_HANDLE;
    VkResult rc = vkCreateImage(dev, &iic, NULL, &img);
    if (rc != VK_SUCCESS) {
        printf("Z[%s] NV12 create failed: %s\n", tag, vkerr(rc));
        return;
    }
    VkMemoryRequirements mr;
    vkGetImageMemoryRequirements(dev, img, &mr);
    /* for a LINEAR image memreq can exceed the plane sum because of tile
     * alignment, so only the OPTIMAL case means "metadata plane allocated" */
    printf("Z[%s] NV12 %dx%d memreq=0x%llx, linear planes=0x%llx%s\n", tag, W, H,
           (unsigned long long)mr.size, (unsigned long long)lin_total,
           tiling == VK_IMAGE_TILING_LINEAR
               ? (mr.size > lin_total ? " -> linear: no metadata, the gap is alignment"
                                       : " -> linear: no metadata")
               : (mr.size > lin_total ? " -> metadata present (UBWC likely on)"
                                       : " -> no metadata, UBWC off"));

    VkDeviceMemory im = VK_NULL_HANDLE;
    if (alloc_mem(dev, mr.size, 0, &im) != VK_SUCCESS ||
        vkBindImageMemory(dev, img, im, 0) != VK_SUCCESS) {
        printf("Z[%s] image memory failed\n", tag);
        vkDestroyImage(dev, img, NULL);
        return;
    }
    VkBufferCreateInfo bci = { VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, 2 * p0,
                               VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                               VK_SHARING_MODE_EXCLUSIVE, 0, NULL };
    VkBuffer buf = VK_NULL_HANDLE;
    if (vkCreateBuffer(dev, &bci, NULL, &buf) != VK_SUCCESS) {
        vkDestroyImage(dev, img, NULL);
        vkFreeMemory(dev, im, NULL);
        return;
    }
    VkMemoryRequirements br;
    vkGetBufferMemoryRequirements(dev, buf, &br);
    VkDeviceMemory bm = VK_NULL_HANDLE;
    if (alloc_mem(dev, br.size, 0, &bm) != VK_SUCCESS ||
        vkBindBufferMemory(dev, buf, bm, 0) != VK_SUCCESS) {
        printf("Z[%s] staging memory failed\n", tag);
        vkDestroyBuffer(dev, buf, NULL);
        vkDestroyImage(dev, img, NULL);
        vkFreeMemory(dev, im, NULL);
        return;
    }
    unsigned char *host = NULL;
    chk(vkMapMemory(dev, bm, 0, br.size, 0, (void **)&host), "Z: map staging");
    for (unsigned y = 0; y < H; y++)
        for (unsigned x = 0; x < W; x++)
            host[(size_t)y * W + x] = (unsigned char)pat(x, y);
    for (VkDeviceSize i = 0; i < p0; i++)
        host[p0 + i] = 0xCC;
    vkUnmapMemory(dev, bm);

    VkBufferImageCopy cp = { 0, 0, 0, { VK_IMAGE_ASPECT_PLANE_0_BIT, 0, 0, 1 }, { 0, 0, 0 },
                             { W, H, 1 } };
    VkImageSubresourceRange full = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 2 };
    for (int pass = 0; pass < 2; pass++) {
        VkCommandBuffer c;
        VkCommandBufferAllocateInfo cai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL,
                                            pool, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1 };
        vkAllocateCommandBuffers(dev, &cai, &c);
        VkCommandBufferBeginInfo b = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL,
                                       VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL };
        vkBeginCommandBuffer(c, &b);
        if (pass == 0) {
            VkImageMemoryBarrier to_dst = { VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, NULL, 0,
                                            VK_ACCESS_TRANSFER_WRITE_BIT,
                                            VK_IMAGE_LAYOUT_UNDEFINED,
                                            VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 0, 0, img, full };
            vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                                 VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, 1, &to_dst);
            vkCmdCopyBufferToImage(c, buf, img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &cp);
            VkImageMemoryBarrier to_src = { VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, NULL,
                                            VK_ACCESS_TRANSFER_WRITE_BIT,
                                            VK_ACCESS_TRANSFER_READ_BIT,
                                            VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                                            VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, 0, 0, img, full };
            vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                                 0, 0, NULL, 0, NULL, 1, &to_src);
        } else {
            VkBufferImageCopy rd = { p0, 0, 0, { VK_IMAGE_ASPECT_PLANE_0_BIT, 0, 0, 1 },
                                     { 0, 0, 0 }, { W, H, 1 } };
            vkCmdCopyImageToBuffer(c, img, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, buf, 1, &rd);
        }
        vkEndCommandBuffer(c);
        VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &c, 0, NULL };
        chk(vkQueueSubmit(q, 1, &si, NULL), "Z: submit");
        chk(vkQueueWaitIdle(q), "Z: wait");
        vkFreeCommandBuffers(dev, pool, 1, &c);
    }

    chk(vkMapMemory(dev, bm, 0, br.size, 0, (void **)&host), "Z: remap staging");
    unsigned bad = 0, zeros = 0, first = 0;
    for (unsigned y = 0; y < H; y++)
        for (unsigned x = 0; x < W; x++) {
            size_t i = (size_t)y * W + x;
            if (host[p0 + i] != (unsigned char)pat(x, y)) {
                if (!bad)
                    first = (unsigned)i;
                bad++;
            }
            if (host[p0 + i] == 0)
                zeros++;
        }
    printf("Z[%s] i2b: %u/%u bytes MISMATCH%s zeros=%u first=(x%u,y%u) got=0x%02x want=0x%02x\n",
           tag, bad, (unsigned)p0, bad ? "" : " (EXACT)", zeros, first % W, first / W,
           host[p0 + first], (unsigned char)pat(first % W, first / W));
    printf("Z[%s] VERDICT: %s\n", tag,
           bad ? "content lost -> cpp=1 UBWC does not work here"
               : "EXACT -> cpp=1 UBWC works here");
    vkUnmapMemory(dev, bm);

    /* the whole allocation, for scripts/ubwc-dump-analyze.py: this is the
     * positive control for the R8 dumps, because here the content is known to
     * have round-tripped */
    if (dump) {
        char fn[512];
        void *raw = NULL;
        snprintf(fn, sizeof(fn), "%s_Z_%s.bin", dump,
                 tiling == VK_IMAGE_TILING_OPTIMAL ? "tiled" : "linear");
        if (vkMapMemory(dev, im, 0, mr.size, 0, &raw) == VK_SUCCESS) {
            FILE *f = fopen(fn, "wb");
            if (f) {
                fwrite(raw, 1, mr.size, f);
                fclose(f);
                printf("Z[%s] dump: %s\n", tag, fn);
            }
            vkUnmapMemory(dev, im);
        }
    }

    vkDestroyBuffer(dev, buf, NULL);
    vkFreeMemory(dev, bm, NULL);
    vkFreeMemory(dev, im, NULL);
    vkDestroyImage(dev, img, NULL);
}

int main(int argc, char **argv)
{
    const char *dump = argc > 1 ? argv[1] : NULL;
    VkInstance inst;
    VkApplicationInfo ai = { VK_STRUCTURE_TYPE_APPLICATION_INFO, NULL, "tp8bpp", 1, NULL, 0,
                             VK_API_VERSION_1_3 };
    VkInstanceCreateInfo ici = { VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, NULL, 0, &ai, 0, NULL, 0,
                                 NULL };
    chk(vkCreateInstance(&ici, NULL, &inst), "vkCreateInstance");

    uint32_t nd = 0;
    vkEnumeratePhysicalDevices(inst, &nd, NULL);
    VkPhysicalDevice *devs = malloc(nd * sizeof(*devs));
    vkEnumeratePhysicalDevices(inst, &nd, devs);
    VkPhysicalDevice pd = NULL;
    for (uint32_t i = 0; i < nd; i++) {
        VkPhysicalDeviceProperties pp;
        vkGetPhysicalDeviceProperties(devs[i], &pp);
        if (pp.vendorID == 0x5143) {
            pd = devs[i];
            printf("device: %s (chip_id 0x%x)\n", pp.deviceName, pp.deviceID);
        }
    }
    chk(pd ? VK_SUCCESS : VK_ERROR_INITIALIZATION_FAILED, "find turnip");
    if (!pd)
        return 1;

    float prio = 1.0f;
    VkDeviceQueueCreateInfo dq = { VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, NULL, 0, 0, 1,
                                   &prio };
    VkDeviceCreateInfo dci = { VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, NULL, 0, 1, &dq, 0, NULL, 0,
                               NULL, NULL };
    VkDevice dev;
    chk(vkCreateDevice(pd, &dci, NULL, &dev), "vkCreateDevice");
    VkQueue q;
    vkGetDeviceQueue(dev, 0, 0, &q);
    VkCommandPoolCreateInfo cpci = { VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, NULL, 0, 0 };
    VkCommandPool pool;
    chk(vkCreateCommandPool(dev, &cpci, NULL, &pool), "vkCreateCommandPool");

    printf("\n=== Z. NV12 Y plane (cpp=1 UBWC, not gated by has_8bpp_ubwc) ===\n");
    probe_nv12(dev, q, pool, "tiled", VK_IMAGE_TILING_OPTIMAL, dump);
    probe_nv12(dev, q, pool, "linear", VK_IMAGE_TILING_LINEAR, dump);

    printf("\n=== AA. R8 filled by imageStore (3D), read by TP and i2b ===\n");
    probe_r8(dev, q, pool, "AA[tiled]", VK_IMAGE_TILING_OPTIMAL, 1, dump);
    probe_r8(dev, q, pool, "AA[linear]", VK_IMAGE_TILING_LINEAR, 1, dump);

    printf("\n=== AB. R8 filled by vkCmdCopyBufferToImage (2D) ===\n");
    probe_r8(dev, q, pool, "AB[tiled]", VK_IMAGE_TILING_OPTIMAL, 0, dump);
    probe_r8(dev, q, pool, "AB[linear]", VK_IMAGE_TILING_LINEAR, 0, dump);

    vkDestroyCommandPool(dev, pool, NULL);
    vkDestroyDevice(dev, NULL);
    vkDestroyInstance(inst, NULL);
    free(devs);
    return 0;
}
