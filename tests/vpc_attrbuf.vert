#version 450

/* Vertex half of the VPC attribute-buffer probe (tests/vpc-attrbuf.c, journal 40.35).
 *
 * What this shader is for: the question is whether writing VPC_ATTR_BUF_GMEM_SIZE /
 * _BASE / PC_ATTR_BUF_GMEM_SIZE (a7xx, tu_cmd_buffer.cc:647-660) changes anything on
 * A740, and that question can only be asked of a chip that is loading the path those
 * registers size.  So the vertex half maximises the two things the path carries:
 *
 *   * attributes in   - 8 vec4 inputs, so VFD decodes 128 B and 8 attributes per vertex
 *     (VFD_DECODED_ATTRIBUTE_BYTES / VFD_NUM_ATTRIBUTES are in the cfg and report it);
 *   * varyings out    - 16 vec4, which is `vs_max_inputs_count`-scale and far above
 *     RE4's interface (40.27 measures 5.02 attributes per vertex on the game side).
 *
 * Every output is a different mix of the inputs.  That is not decoration: turnip runs
 * nir_opt_varyings_bulk with promotion limits of UINT32_MAX (tu_shader.cc:3878, journal
 * 40.34), which turns a varying the compiler can prove uniform into a constant load and
 * takes it out of the varyings traffic entirely.  A constant or gl_VertexIndex-derived
 * output would be promoted away and the probe would measure an empty stream.
 */

layout(location = 0) in vec4 aPos;
layout(location = 1) in vec4 a0;
layout(location = 2) in vec4 a1;
layout(location = 3) in vec4 a2;
layout(location = 4) in vec4 a3;
layout(location = 5) in vec4 a4;
layout(location = 6) in vec4 a5;
layout(location = 7) in vec4 a6;

layout(location = 0)  out vec4 v0;
layout(location = 1)  out vec4 v1;
layout(location = 2)  out vec4 v2;
layout(location = 3)  out vec4 v3;
layout(location = 4)  out vec4 v4;
layout(location = 5)  out vec4 v5;
layout(location = 6)  out vec4 v6;
layout(location = 7)  out vec4 v7;
layout(location = 8)  out vec4 v8;
layout(location = 9)  out vec4 v9;
layout(location = 10) out vec4 v10;
layout(location = 11) out vec4 v11;
layout(location = 12) out vec4 v12;
layout(location = 13) out vec4 v13;
layout(location = 14) out vec4 v14;
layout(location = 15) out vec4 v15;

void main()
{
   /* gl_InstanceIndex shifts the scatter, so eight instances of one buffer cover the
    * target eight times over instead of drawing the same pixels eight times. */
   vec2 jitter = vec2(float(gl_InstanceIndex) * 0.011,
                      float(gl_InstanceIndex) * 0.017);
   gl_Position = vec4(aPos.xy + jitter, aPos.z, 1.0);

   vec4 s = a0 + a1 + a2 + a3;
   vec4 t = a4 + a5 + a6;

   v0  = a0 * aPos.x;
   v1  = a1 + s.zyxw;
   v2  = a2 * t.w;
   v3  = a3 - t.xyzw;
   v4  = a4 + s.xyzw;
   v5  = a5 * aPos.y;
   v6  = a6 - s.yzwx;
   v7  = a0 * t.xyzw;
   v8  = fract(a1 * 1.0001) + t.z;
   v9  = a2 + a3.yzwx;
   v10 = a4 * a5;
   v11 = a6 + a0.wzyx;
   v12 = s * 0.25 + t;
   v13 = t * 0.5 - s;
   v14 = fract(s * 0.125) * aPos.x;
   v15 = fract(t * 0.125) * aPos.y;
}
