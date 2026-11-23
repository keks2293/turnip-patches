/* vpc-attrbuf.c - does the VPC attribute-buffer carve-out exist on this chip?
 *
 * The question (journal 40.35, queue 35, asked by the operator after 40.34):
 * `sysmem_vpc_attr_buf_size` and `gmem_vpc_attr_buf_size` are 0 for a7xx_gen2, and
 * A740 therefore never writes VPC_ATTR_BUF_GMEM_SIZE / VPC_ATTR_BUF_GMEM_BASE /
 * PC_ATTR_BUF_GMEM_SIZE - `emit_vpc_attr_buf()` returns at tu_cmd_buffer.cc:649 unless
 * `props.has_gmem_vpc_attr_buf`, and the GMEM layout function consults the sizes only in
 * that same branch (fd6_gmem_cache.h:103-116).  That is a driver fact.  It is not yet a
 * fact about the silicon: "the code never writes the registers" and "the registers would
 * do nothing" are different claims, and `a6xx.xml:3227-3239` declares all three with
 * variants="A7XX", a family tag that covers A740 as well as A750.
 *
 * What this probe contributes is a workload heavy enough that a vertex-attribute
 * carve-out could show itself: 8 vec4 attributes in, 16 vec4 varyings out (out only since
 * journal 42.1 corrected the form of tests/vpc_attrbuf.frag - as committed on 23.11 its plain sum
 * of all sixteen collapsed to one varying, and the arms of journal 40.35 measured that), hundreds of
 * thousands of vertices per frame, one binned render pass per frame.  It is run with the
 * prop off, with the prop on at several sizes, and - the part without which the run
 * would prove nothing - with `TU_GMEM` set so that GMEM is shrunk by the same number of
 * bytes without the prop.  Raising `gmem_vpc_attr_buf_size` to S also takes 6*S bytes
 * away from usable GMEM (num_ccu = 6 for FD740, freedreno_devices.py:1241, and
 * fd6_gmem_cache.h:108-109 subtracts `size * num_ccu`), which by itself changes work per
 * bin; the TU_GMEM control arm has the identical usable size and identical CCU offsets
 * and writes none of the registers.  prop(S) vs control(S) is therefore a comparison of
 * the register writes alone.
 *
 * Build (no compiler on the device, see scripts/build-test.sh):
 *   podman run --rm -v "$PWD/tests:/work:Z" -v "$PWD/../build:/out:Z" \
 *     localhost/mesa-build-fedora44-wsi-glslang-vulkan \
 *     bash -c 'cd /work && gcc -O2 -Wall -o /out/vpc-attrbuf vpc-attrbuf.c -lvulkan -lm'
 *   (-lm since the --varyings arms added sqrt()/sin() to the vertex jitter; without it the link
 *   fails with "undefined reference to sqrt", which reads like a missing library path)
 * Run (one arm; the sweep is scripts/run-attrbuf-sweep.sh):
 *   VK_DRIVER_FILES=../build/out/freedreno_icd.json \
 *   [TU_FORCE_PROPS=has_gmem_vpc_attr_buf] [FD_DEV_FEATURES=gmem_vpc_attr_buf_size=4096] \
 *   [TU_GMEM=3997696] ./build/vpc-attrbuf --seconds 60
 *
 * A second question lives in the same rig, added 23.11 for queue 34 (journal 40.36 states
 * what the committed dumps already say about the two export counters): `--varyings=N`, with
 * N in 1, 2, 4, 8, 16, swaps in the shader pair of tests/gen-varyings-spv.sh - the same
 * vertex data, the same position expression, the same draw, and N vec4 outputs instead of 16.
 * That is the known-interface arm the unit of PERF_VPC_SP_COMPONENTS (VPC 10) and
 * PERF_SP_EXPORT_VPC_TRANS (SP 48) needs, and it is the same program on purpose: one rig means
 * the arms cannot differ in geometry, instance count, target size or clear value, which is the
 * property the parked sweep above also depends on.  Note that the *hash* is not the identity
 * check between varyings arms - the fragment shader sums what it is given, so a different N is
 * a different picture by construction; the identity checks there are VFD_TOTAL_VERTICES and
 * SP_OUTPUT_3D_PIXELS in the counters.  Without `--varyings` nothing changes for queue 35.
 *
 * Output is one line per fact on stdout: a `#`-prefixed header (device, GMEM as the
 * kernel reports it, the env this process was given, the shape of the workload) and then
 * `fps`, `frames` and a `hash` of the render target.  The hash is the arm's proof of
 * identity: every arm must print the same one, or the arms drew different pictures and
 * their counters are not comparable.
 */

#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <vulkan/vulkan.h>

#include "vpc_attrbuf_spv.h"
#include "varyings_spv.h"

/* GMEM size as the kernel reports it.  Defined here rather than included, for the same
 * reason turnip defines it (vulkan/tu_knl_drm_msm.cc:7 includes a copy of the uapi
 * header): the structure's size is part of the ioctl number, so it must match what the
 * driver itself sends, not what the container's kernel-headers happen to carry. */
struct drm_msm_param {
   uint32_t pipe;
   uint32_t param;
   uint64_t value;
   uint32_t len;
   uint32_t pad;
};
#define MSM_PIPE_3D0        0x01
#define MSM_PARAM_GMEM_SIZE 0x02
#define DRM_IOCTL_BASE      'd'
#define DRM_COMMAND_BASE    0x40
#define DRM_MSM_GET_PARAM   0x00
#define DRM_IOWR(nr, type)  _IOWR(DRM_IOCTL_BASE, (nr), type)
#define DRM_IOCTL_MSM_GET_PARAM \
   DRM_IOWR(DRM_COMMAND_BASE + DRM_MSM_GET_PARAM, struct drm_msm_param)

#define MAX_FRAMES_IN_FLIGHT 4
#define NUM_VARYINGS         16
#define NUM_ATTRIBS          8

static int failures = 0;

static void
chk(VkResult r, const char *what)
{
   if (r != VK_SUCCESS) {
      fprintf(stderr, "[FATAL] %s -> VkResult %d\n", what, (int) r);
      exit(1);
   }
}

static double
now_s(void)
{
   struct timespec ts;
   clock_gettime(CLOCK_MONOTONIC, &ts);
   return ts.tv_sec + ts.tv_nsec * 1e-9;
}

static const char *
env_or_unset(const char *name)
{
   const char *v = getenv(name);
   return (v && *v) ? v : "(unset)";
}

/* The kernel's GMEM size, or 0 if the ioctl is refused (a non-msm node, or a kernel that
 * will not answer on a render node).  Only printed, never used to compute anything: the
 * sweep script is what turns it into TU_GMEM values, and it refuses to guess. */
static uint64_t
query_gmem_size(void)
{
   const char *node = getenv("VPC_ATTRBUF_DRI");
   const char *path = (node && *node) ? node : "/dev/dri/renderD128";
   int fd = open(path, O_RDWR | O_CLOEXEC);
   if (fd < 0) {
      fprintf(stderr, "# gmem      %s: %s\n", path, strerror(errno));
      return 0;
   }

   struct drm_msm_param p = { .pipe = MSM_PIPE_3D0, .param = MSM_PARAM_GMEM_SIZE };
   uint64_t value = 0;
   if (ioctl(fd, DRM_IOCTL_MSM_GET_PARAM, &p) == 0) {
      value = p.value;
   } else {
      fprintf(stderr, "# gmem      MSM_PARAM_GMEM_SIZE on %s: %s\n", path, strerror(errno));
   }
   close(fd);
   return value;
}

static uint64_t
fnv1a(const uint8_t *p, size_t n)
{
   uint64_t h = 1469598103934665603ULL;
   for (size_t i = 0; i < n; i++) {
      h ^= p[i];
      h *= 1099511628211ULL;
   }
   return h;
}

/* Deterministic scatter: 32-bit xorshift, so every arm generates the same mesh from the
 * same seed and the render target can be hashed for comparison. */
static uint32_t
xs(uint32_t *s)
{
   uint32_t x = *s;
   x ^= x << 13;
   x ^= x >> 17;
   x ^= x << 5;
   return *s = x;
}

static float
f01(uint32_t *s)
{
   return (float)(xs(s) >> 8) * (1.0f / 16777216.0f);
}

typedef struct {
   float pos[4];
   float attr[NUM_ATTRIBS - 1][4];
} vertex_t;

/* The interface arms of queue 34, from tests/gen-varyings-spv.h.  `out` and `stride` are what
 * the driver has to write for an interface of N vec4 with no psize/layer/view/clip distance:
 * SP_VS_OUTPUT_CNTL.OUT counts POSITION too ("number of VS outputs including pos",
 * a6xx.xml:3677-3680, tu_pipeline.cc:1092) and VPC_VS_CNTL.STRIDE_IN_VPC is linkage.max_loc,
 * four components per vec4 plus four for position (tu_pipeline.cc:926-931).  They are printed
 * so that a run's own header carries the claim - this program cannot check them, it has no way
 * to read its command stream back.  Check them with the disassembler instead, which prints the
 * FS's bary immediates (the largest `vappro.x + k` plus 4 is the stride):
 *   IR3_SHADER_DEBUG=fs ./build/vpc-attrbuf --varyings=4 --seconds=1 2>&1 |
 *       grep -o 'vappro.x + [0-9]*' | sort -u -t+ -k2 -n | tail -1
 * which is why the interface is five compiled shader pairs and not one shader and a spec
 * constant: the constant would change the VS's work while the interface stayed 16 wide. */
typedef struct {
   uint32_t n;               /* vec4 varyings the vertex shader exports */
   uint32_t out, stride;     /* the register values named above */
   const uint32_t *vs;
   size_t vs_words;
   const uint32_t *fs;
   size_t fs_words;
} varying_arm_t;

#define ARM(n_, out_, stride_, vs_, fs_)                                        \
   {                                                                            \
      n_, out_, stride_, vs_, sizeof(vs_) / sizeof(uint32_t), fs_,              \
         sizeof(fs_) / sizeof(uint32_t)                                         \
   }

static const varying_arm_t varying_arms[] = {
   ARM(1u, 2u, 8u, varyings1_vert_spv, varyings1_frag_spv),
   ARM(2u, 3u, 12u, varyings2_vert_spv, varyings2_frag_spv),
   ARM(4u, 5u, 20u, varyings4_vert_spv, varyings4_frag_spv),
   ARM(8u, 9u, 36u, varyings8_vert_spv, varyings8_frag_spv),
   ARM(16u, 17u, 68u, varyings16_vert_spv, varyings16_frag_spv),
};

int
main(int argc, char **argv)
{
   double seconds = 60.0;
   uint32_t width = 768, height = 768, verts = 24576, instances = 8;
   uint32_t loop_count = 0;
   int do_hash = 1;
   const varying_arm_t *arm = NULL;   /* NULL: the vpc_attrbuf pair, 16 vec4 */

   for (int i = 1; i < argc; i++) {
      if (!strncmp(argv[i], "--seconds=", 10))
         seconds = atof(argv[i] + 10);
      else if (!strncmp(argv[i], "--size=", 7))
         width = height = (uint32_t) atoi(argv[i] + 7);
      else if (!strncmp(argv[i], "--verts=", 8))
         verts = (uint32_t) atoi(argv[i] + 8);
      else if (!strncmp(argv[i], "--instances=", 12))
         instances = (uint32_t) atoi(argv[i] + 12);
      else if (!strncmp(argv[i], "--loop=", 7))
         loop_count = (uint32_t) atoi(argv[i] + 7);
      else if (!strncmp(argv[i], "--varyings=", 11)) {
         /* A count we do not have must be an error and not a silent fall-back to the 16-wide
          * pair: an arm that quietly became another arm is the failure mode of this rig. */
         uint32_t want = (uint32_t) atoi(argv[i] + 11);
         for (unsigned k = 0; k < sizeof varying_arms / sizeof varying_arms[0]; k++)
            if (varying_arms[k].n == want)
               arm = &varying_arms[k];
         if (!arm) {
            fprintf(stderr,
                    "--varyings= takes one of 1 2 4 8 16 (the compiled pairs of"
                    " tests/gen-varyings-spv.sh), not %u\n", want);
            return 2;
         }
      } else if (!strcmp(argv[i], "--no-hash"))
         do_hash = 0;
      else {
         fprintf(stderr,
                 "usage: vpc-attrbuf [--seconds=N] [--size=PX] [--verts=N] "
                 "[--instances=N] [--loop=N] [--varyings=N] [--no-hash]\n"
                 "  --varyings: 1 2 4 8 16, the interface arms of queue 34; without it, the"
                 " 16-vec4 pair of tests/vpc_attrbuf.vert\n");
         return 2;
      }
   }
   if (verts < 3)
      verts = 3;
   verts -= verts % 3; /* triangle list: whole primitives only */

   /* ---- instance, device, queue -------------------------------------------- */
   VkApplicationInfo ai = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO };
   VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                                .pApplicationInfo = &ai };
   VkInstance inst;
   chk(vkCreateInstance(&ici, NULL, &inst), "vkCreateInstance");

   uint32_t nphys = 0;
   vkEnumeratePhysicalDevices(inst, &nphys, NULL);
   if (!nphys) {
      fprintf(stderr, "[FATAL] no Vulkan device: is VK_DRIVER_FILES right?\n");
      return 1;
   }
   VkPhysicalDevice *phys = calloc(nphys, sizeof *phys);
   vkEnumeratePhysicalDevices(inst, &nphys, phys);

   /* The probe is run against our ICD, so device 0 is the one that matters; if the
    * loader ever hands us an ANV or a lavapipe first, measuring it would be a silent
    * zero, so say which device is being measured and take the Adreno if there is one.
    * Chosen by name rather than by VkDriverId, because a name is what the dump has to be
    * trusted against anyway and the enum's spelling has moved between header versions. */
   VkPhysicalDevice pd = phys[0];
   for (uint32_t i = 0; i < nphys; i++) {
      VkPhysicalDeviceProperties2 pp = { .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2 };
      VkPhysicalDeviceDriverProperties dp = { .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES };
      pp.pNext = &dp;
      vkGetPhysicalDeviceProperties2(phys[i], &pp);
      printf("# device[%u] %s, driver %s %s, api %u.%u\n", i, pp.properties.deviceName,
             dp.driverName, dp.driverInfo, VK_API_VERSION_MAJOR(pp.properties.apiVersion),
             VK_API_VERSION_MINOR(pp.properties.apiVersion));
      if (strstr(pp.properties.deviceName, "Adreno") ||
          strstr(pp.properties.deviceName, "FD7") ||
          strstr(dp.driverName, "turnip"))
         pd = phys[i];
   }

   VkPhysicalDeviceProperties props;
   vkGetPhysicalDeviceProperties(pd, &props);

   uint32_t nq = 0;
   vkGetPhysicalDeviceQueueFamilyProperties(pd, &nq, NULL);
   VkQueueFamilyProperties *qf = calloc(nq, sizeof *qf);
   vkGetPhysicalDeviceQueueFamilyProperties(pd, &nq, qf);
   uint32_t qfi = UINT32_MAX;
   for (uint32_t i = 0; i < nq; i++)
      if (qf[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) {
         qfi = i;
         break;
      }
   if (qfi == UINT32_MAX) {
      fprintf(stderr, "[FATAL] no graphics queue\n");
      return 1;
   }

   float prio = 1.0f;
   VkDeviceQueueCreateInfo qci = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
                                   .queueFamilyIndex = qfi,
                                   .queueCount = 1,
                                   .pQueuePriorities = &prio };
   VkDeviceCreateInfo dci = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
                              .queueCreateInfoCount = 1,
                              .pQueueCreateInfos = &qci };
   VkDevice dev;
   chk(vkCreateDevice(pd, &dci, NULL, &dev), "vkCreateDevice");
   VkQueue queue;
   vkGetDeviceQueue(dev, qfi, 0, &queue);

   uint64_t gmem = query_gmem_size();

   printf("# measured  %s\n", props.deviceName);
   printf("# gmem      kernel reports %" PRIu64 " bytes (%.2f MiB)\n", gmem,
          (double) gmem / 1048576.0);
   printf("# env       TU_GMEM=%s\n", env_or_unset("TU_GMEM"));
   printf("# env       TU_FORCE_PROPS=%s\n", env_or_unset("TU_FORCE_PROPS"));
   printf("# env       FD_DEV_FEATURES=%s\n", env_or_unset("FD_DEV_FEATURES"));
   printf("# env       TU_DEBUG=%s\n", env_or_unset("TU_DEBUG"));
   printf("# workload  %ux%u, %u verts x %u instances = %u verts/frame, FS loop %u\n",
          width, height, verts, instances, verts * instances, loop_count);
   /* Names what the source asks for, not what the driver built.  How many vec4 the compiler leaves on
    * the interface is a property of the fragment shader's form: nir_opt_varyings moves a plain sum up
    * into the VS and one varying is all that survives.  Journal 42.1 found the default pair described
    * by this line reading 16 while its pipeline carried 1.  What each arm really compiles to is what
    * scripts/check-varyings-arms.py reads out of the disassembly, and scripts/run-varyings-sweep.sh
    * refuses to sample an arm the check has not confirmed.  A comment, not a code change, so the
    * binary the arms of 42.2 were sampled with stays the binary the source builds. */
   printf("# workload  %d attributes in (%zu B/vertex), %u vec4 varyings out%s\n",
          NUM_ATTRIBS, sizeof(vertex_t),
          arm ? arm->n : (unsigned) NUM_VARYINGS,
          arm ? "" : " (the pair of tests/vpc_attrbuf.vert)");
   if (arm)
      printf("# interface SP_VS_OUTPUT_CNTL.OUT=%u VPC_VS_CNTL.STRIDE_IN_VPC=%u, the state this"
             " arm asks for;\n#           this program cannot read it back - the check is the"
             " disassembler command in\n#           tests/gen-varyings-spv.sh's header\n",
             arm->out, arm->stride);

   /* ---- memory helpers ------------------------------------------------------ */
   VkPhysicalDeviceMemoryProperties mp;
   vkGetPhysicalDeviceMemoryProperties(pd, &mp);

   /* ---- vertex buffer ------------------------------------------------------- */
   size_t vb_bytes = (size_t) verts * sizeof(vertex_t);
   vertex_t *host = malloc(vb_bytes);
   uint32_t seed = 0x1234567u;
   for (uint32_t v = 0; v < verts; v++) {
      /* Triangles of 2-26 px, scattered: many tiles, little coverage, so the vertex
       * tract - not the pixels - sets how long a frame takes. */
      float cx = f01(&seed) * 2.0f - 1.0f;
      float cy = f01(&seed) * 2.0f - 1.0f;
      float r = 0.002f + f01(&seed) * 0.02f;
      float ang = f01(&seed) * 6.2831853f;
      for (int c = 0; c < 3; c++) {
         float a = ang + c * 2.0943951f;
         host[v].pos[0] = cx + r * cosf(a);
         host[v].pos[1] = cy + r * sinf(a);
         host[v].pos[2] = 0.0f;
         host[v].pos[3] = 1.0f;
      }
      for (int k = 0; k < NUM_ATTRIBS - 1; k++)
         for (int c = 0; c < 4; c++)
            host[v].attr[k][c] = f01(&seed);
   }

   VkBuffer vb;
   VkDeviceMemory vb_mem;
   VkBufferCreateInfo bci = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
                              .size = vb_bytes,
                              .usage = VK_BUFFER_USAGE_VERTEX_BUFFER_BIT,
                              .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
   chk(vkCreateBuffer(dev, &bci, NULL, &vb), "vkCreateBuffer(vertex)");
   VkMemoryRequirements mr;
   vkGetBufferMemoryRequirements(dev, vb, &mr);
   {
      uint32_t type = UINT32_MAX;
      for (uint32_t i = 0; i < mp.memoryTypeCount; i++)
         if ((mr.memoryTypeBits & (1u << i)) &&
             (mp.memoryTypes[i].propertyFlags &
              (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) ==
                 (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) {
            type = i;
            break;
         }
      if (type == UINT32_MAX) {
         fprintf(stderr, "[FATAL] no host-visible memory type\n");
         return 1;
      }
      VkMemoryAllocateInfo ai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                                  .allocationSize = mr.size,
                                  .memoryTypeIndex = type };
      chk(vkAllocateMemory(dev, &ai, NULL, &vb_mem), "vkAllocateMemory(vertex)");
      chk(vkBindBufferMemory(dev, vb, vb_mem, 0), "vkBindBufferMemory(vertex)");
      void *map = NULL;
      chk(vkMapMemory(dev, vb_mem, 0, VK_WHOLE_SIZE, 0, &map), "vkMapMemory(vertex)");
      memcpy(map, host, vb_bytes);
      vkUnmapMemory(dev, vb_mem);
   }
   free(host);

   /* ---- render target ------------------------------------------------------- */
   const VkFormat fmt = VK_FORMAT_R8G8B8A8_UNORM;
   VkImage rt;
   VkDeviceMemory rt_mem;
   VkImageCreateInfo iici = { .sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
                              .imageType = VK_IMAGE_TYPE_2D,
                              .format = fmt,
                              .extent = { width, height, 1 },
                              .mipLevels = 1,
                              .arrayLayers = 1,
                              .samples = VK_SAMPLE_COUNT_1_BIT,
                              .tiling = VK_IMAGE_TILING_OPTIMAL,
                              .usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
                                       VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
                              .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
                              .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED };
   chk(vkCreateImage(dev, &iici, NULL, &rt), "vkCreateImage");
   vkGetImageMemoryRequirements(dev, rt, &mr);
   {
      uint32_t type = UINT32_MAX;
      for (uint32_t i = 0; i < mp.memoryTypeCount; i++)
         if ((mr.memoryTypeBits & (1u << i)) &&
             (mp.memoryTypes[i].propertyFlags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) {
            type = i;
            break;
         }
      if (type == UINT32_MAX)
         type = 0; /* no device-local heap: any heap works, this is not what is measured */
      VkMemoryAllocateInfo ai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                                  .allocationSize = mr.size,
                                  .memoryTypeIndex = type };
      chk(vkAllocateMemory(dev, &ai, NULL, &rt_mem), "vkAllocateMemory(rt)");
      chk(vkBindImageMemory(dev, rt, rt_mem, 0), "vkBindImageMemory(rt)");
   }

   VkImageView rt_view;
   VkImageViewCreateInfo vci = { .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
                                 .image = rt,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D,
                                 .format = fmt,
                                 .subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 } };
   chk(vkCreateImageView(dev, &vci, NULL, &rt_view), "vkCreateImageView");

   /* ---- render pass, frame buffer ------------------------------------------- */
   VkAttachmentDescription att = { .format = fmt,
                                   .samples = VK_SAMPLE_COUNT_1_BIT,
                                   .loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE,
                                   .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
                                   .stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE,
                                   .stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE,
                                   .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED,
                                   .finalLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
   VkAttachmentReference aref = { .attachment = 0, .layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
   VkSubpassDescription sub = { .pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS,
                                .colorAttachmentCount = 1,
                                .pColorAttachments = &aref };
   VkSubpassDependency dep = { .srcSubpass = VK_SUBPASS_EXTERNAL,
                               .dstSubpass = 0,
                               .srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                               .dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                               .srcAccessMask = 0,
                               .dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT };
   VkRenderPass rp;
   VkRenderPassCreateInfo rpi = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,
                                  .attachmentCount = 1,
                                  .pAttachments = &att,
                                  .subpassCount = 1,
                                  .pSubpasses = &sub,
                                  .dependencyCount = 1,
                                  .pDependencies = &dep };
   chk(vkCreateRenderPass(dev, &rpi, NULL, &rp), "vkCreateRenderPass");

   VkFramebuffer fb;
   VkFramebufferCreateInfo fbi = { .sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,
                                   .renderPass = rp,
                                   .attachmentCount = 1,
                                   .pAttachments = &rt_view,
                                   .width = width,
                                   .height = height,
                                   .layers = 1 };
   chk(vkCreateFramebuffer(dev, &fbi, NULL, &fb), "vkCreateFramebuffer");

   /* ---- pipeline ------------------------------------------------------------- */
   VkShaderModule vs_mod, fs_mod;
   VkShaderModuleCreateInfo smi = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO };
   const uint32_t *vs_spv = vpc_attrbuf_vert_spv, *fs_spv = vpc_attrbuf_frag_spv;
   size_t vs_words = sizeof vpc_attrbuf_vert_spv / sizeof(uint32_t),
          fs_words = sizeof vpc_attrbuf_frag_spv / sizeof(uint32_t);
   if (arm) {                        /* --varyings=N, the interface arms of queue 34 */
      vs_spv = arm->vs;
      fs_spv = arm->fs;
      vs_words = arm->vs_words;
      fs_words = arm->fs_words;
   }
   smi.codeSize = vs_words * sizeof(uint32_t);
   smi.pCode = vs_spv;
   chk(vkCreateShaderModule(dev, &smi, NULL, &vs_mod), "vkCreateShaderModule(vs)");
   smi.codeSize = fs_words * sizeof(uint32_t);
   smi.pCode = fs_spv;
   chk(vkCreateShaderModule(dev, &smi, NULL, &fs_mod), "vkCreateShaderModule(fs)");

   VkSpecializationMapEntry sme = { .constantID = 0, .offset = 0, .size = sizeof(uint32_t) };
   VkSpecializationInfo spec = { .mapEntryCount = 1, .pMapEntries = &sme,
                                 .dataSize = sizeof loop_count, .pData = &loop_count };

   VkPipelineShaderStageCreateInfo stages[2] = {
      { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_VERTEX_BIT, .module = vs_mod, .pName = "main" },
      { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_FRAGMENT_BIT, .module = fs_mod, .pName = "main",
        .pSpecializationInfo = &spec },
   };

   VkVertexInputBindingDescription vbd = { .binding = 0, .stride = sizeof(vertex_t),
                                           .inputRate = VK_VERTEX_INPUT_RATE_VERTEX };
   VkVertexInputAttributeDescription vad[NUM_ATTRIBS];
   for (int k = 0; k < NUM_ATTRIBS; k++)
      vad[k] = (VkVertexInputAttributeDescription){ .location = (uint32_t) k, .binding = 0,
                                                    .format = VK_FORMAT_R32G32B32A32_SFLOAT,
                                                    .offset = (uint32_t)(k * 16) };
   VkPipelineVertexInputStateCreateInfo vis = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
      .vertexBindingDescriptionCount = 1, .pVertexBindingDescriptions = &vbd,
      .vertexAttributeDescriptionCount = NUM_ATTRIBS, .pVertexAttributeDescriptions = vad };
   VkPipelineInputAssemblyStateCreateInfo ias = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
      .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST };
   VkPipelineViewportStateCreateInfo vps = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
      .viewportCount = 1, .scissorCount = 1 };
   VkPipelineRasterizationStateCreateInfo ras = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
      .polygonMode = VK_POLYGON_MODE_FILL, .cullMode = VK_CULL_MODE_NONE,
      .frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE, .lineWidth = 1.0f };
   VkPipelineMultisampleStateCreateInfo mss = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
      .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT };
   VkPipelineDepthStencilStateCreateInfo dss = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO };
   VkPipelineColorBlendAttachmentState cba = { .colorWriteMask = VK_COLOR_COMPONENT_R_BIT |
                                                 VK_COLOR_COMPONENT_G_BIT |
                                                 VK_COLOR_COMPONENT_B_BIT |
                                                 VK_COLOR_COMPONENT_A_BIT };
   VkPipelineColorBlendStateCreateInfo cbs = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
      .attachmentCount = 1, .pAttachments = &cba };
   VkDynamicState dyn[] = { VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR };
   VkPipelineDynamicStateCreateInfo dsi = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
      .dynamicStateCount = 2, .pDynamicStates = dyn };

   VkPipelineLayout pl;
   VkPipelineLayoutCreateInfo pli = { .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO };
   chk(vkCreatePipelineLayout(dev, &pli, NULL, &pl), "vkCreatePipelineLayout");

   VkGraphicsPipelineCreateInfo gpi = { .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
                                        .stageCount = 2, .pStages = stages,
                                        .pVertexInputState = &vis,
                                        .pInputAssemblyState = &ias,
                                        .pViewportState = &vps,
                                        .pRasterizationState = &ras,
                                        .pMultisampleState = &mss,
                                        .pDepthStencilState = &dss,
                                        .pColorBlendState = &cbs,
                                        .pDynamicState = &dsi,
                                        .layout = pl, .renderPass = rp, .subpass = 0 };
   VkPipeline pipe;
   chk(vkCreateGraphicsPipelines(dev, NULL, 1, &gpi, NULL, &pipe), "vkCreateGraphicsPipelines");

   /* ---- the loop ------------------------------------------------------------- */
   VkCommandPool pool;
   VkCommandPoolCreateInfo cpci = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
                                    .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
                                    .queueFamilyIndex = qfi };
   chk(vkCreateCommandPool(dev, &cpci, NULL, &pool), "vkCreateCommandPool");

   VkCommandBuffer cms[MAX_FRAMES_IN_FLIGHT];
   VkCommandBufferAllocateInfo cai = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
                                       .commandPool = pool,
                                       .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                                       .commandBufferCount = MAX_FRAMES_IN_FLIGHT };
   chk(vkAllocateCommandBuffers(dev, &cai, cms), "vkAllocateCommandBuffers");

   VkFence fences[MAX_FRAMES_IN_FLIGHT];
   VkFenceCreateInfo fci = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO,
                             .flags = VK_FENCE_CREATE_SIGNALED_BIT };
   for (int i = 0; i < MAX_FRAMES_IN_FLIGHT; i++)
      chk(vkCreateFence(dev, &fci, NULL, &fences[i]), "vkCreateFence");

   uint64_t frames = 0;
   double t_start = now_s(), t_end = t_start;
   while ((t_end = now_s()) - t_start < seconds) {
      uint32_t slot = (uint32_t)(frames % MAX_FRAMES_IN_FLIGHT);
      VkCommandBuffer cm = cms[slot];

      if (frames >= MAX_FRAMES_IN_FLIGHT)
         chk(vkWaitForFences(dev, 1, &fences[slot], VK_TRUE, ~0ULL), "wait fence");

      VkCommandBufferBeginInfo bi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
                                      .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT };
      chk(vkResetCommandBuffer(cm, 0), "ResetCommandBuffer");
      chk(vkBeginCommandBuffer(cm, &bi), "BeginCommandBuffer");

      VkRenderPassBeginInfo rbi = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,
                                    .renderPass = rp, .framebuffer = fb,
                                    .renderArea = { { 0, 0 }, { width, height } } };
      vkCmdBeginRenderPass(cm, &rbi, VK_SUBPASS_CONTENTS_INLINE);
      VkViewport vp = { .x = 0, .y = 0, .width = (float) width, .height = (float) height,
                        .minDepth = 0.0f, .maxDepth = 1.0f };
      VkRect2D sc = { .offset = { 0, 0 }, .extent = { width, height } };
      vkCmdSetViewport(cm, 0, 1, &vp);
      vkCmdSetScissor(cm, 0, 1, &sc);
      vkCmdBindPipeline(cm, VK_PIPELINE_BIND_POINT_GRAPHICS, pipe);
      vkCmdBindVertexBuffers(cm, 0, 1, &vb, &(VkDeviceSize){ 0 });
      vkCmdDraw(cm, verts, instances, 0, 0);
      vkCmdEndRenderPass(cm);
      chk(vkEndCommandBuffer(cm), "EndCommandBuffer");

      chk(vkResetFences(dev, 1, &fences[slot]), "ResetFences");
      VkSubmitInfo si = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1,
                          .pCommandBuffers = &cm };
      chk(vkQueueSubmit(queue, 1, &si, fences[slot]), "vkQueueSubmit");
      frames++;
   }
   vkDeviceWaitIdle(dev);

   double elapsed = now_s() - t_start;
   printf("# clock     %.1f s wall, GPU clock is the devfreq governor's (the sweep keeps "
          "windows where the dump reports >= 676 MHz)\n", elapsed);
   printf("frames %" PRIu64 "\n", frames);
   printf("fps %.2f\n", frames / (elapsed > 0 ? elapsed : 1));
   printf("verts_per_s %.3f M\n", frames * (double) verts * instances / elapsed / 1e6);

   /* ---- one readback, at the end, as the arms' identity check ---------------- */
   if (do_hash) {
      size_t bytes = (size_t) width * height * 4;
      VkBuffer rb;
      VkDeviceMemory rb_mem;
      VkBufferCreateInfo rbi = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
                                 .size = bytes,
                                 .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                                 .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
      chk(vkCreateBuffer(dev, &rbi, NULL, &rb), "vkCreateBuffer(readback)");
      vkGetBufferMemoryRequirements(dev, rb, &mr);
      uint32_t type = 0;
      for (uint32_t i = 0; i < mp.memoryTypeCount; i++)
         if ((mr.memoryTypeBits & (1u << i)) &&
             (mp.memoryTypes[i].propertyFlags &
              (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))) {
            type = i;
            break;
         }
      VkMemoryAllocateInfo ai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                                  .allocationSize = mr.size, .memoryTypeIndex = type };
      chk(vkAllocateMemory(dev, &ai, NULL, &rb_mem), "vkAllocateMemory(readback)");
      chk(vkBindBufferMemory(dev, rb, rb_mem, 0), "vkBindBufferMemory(readback)");

      VkCommandBuffer cm = cms[0];
      VkCommandBufferBeginInfo bi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
                                      .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT };
      chk(vkResetCommandBuffer(cm, 0), "ResetCommandBuffer(readback)");
      chk(vkBeginCommandBuffer(cm, &bi), "BeginCommandBuffer(readback)");
      VkImageMemoryBarrier bar = { .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
                                   .srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,
                                   .dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT,
                                   .oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
                                   .newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                                   .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                                   .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                                   .image = rt,
                                   .subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 } };
      vkCmdPipelineBarrier(cm, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                           VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, 1, &bar);
      VkBufferImageCopy reg = { .imageSubresource = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1 },
                                .imageExtent = { width, height, 1 } };
      vkCmdCopyImageToBuffer(cm, rt, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, rb, 1, &reg);
      chk(vkEndCommandBuffer(cm), "EndCommandBuffer(readback)");
      VkFence f;
      VkFenceCreateInfo ff = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO };
      chk(vkCreateFence(dev, &ff, NULL, &f), "vkCreateFence(readback)");
      VkSubmitInfo si = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1,
                          .pCommandBuffers = &cm };
      chk(vkQueueSubmit(queue, 1, &si, f), "vkQueueSubmit(readback)");
      chk(vkWaitForFences(dev, 1, &f, VK_TRUE, ~0ULL), "wait fence(readback)");
      vkDestroyFence(dev, f, NULL);

      void *map = NULL;
      chk(vkMapMemory(dev, rb_mem, 0, VK_WHOLE_SIZE, 0, &map), "vkMapMemory(readback)");
      printf("hash 0x%016llx  (%zu B of the render target)\n",
             (unsigned long long) fnv1a(map, bytes), bytes);
      vkUnmapMemory(dev, rb_mem);
      vkDestroyBuffer(dev, rb, NULL);
      vkFreeMemory(dev, rb_mem, NULL);
   }

   vkDestroyDevice(dev, NULL);
   vkDestroyInstance(inst, NULL);
   free(phys);
   free(qf);
   return failures ? 1 : 0;
}
