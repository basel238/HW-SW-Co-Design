# Stage 1 source study: raytrace

**Student review status: REQUIRED.** These notes explain the supplied source;
they do not certify that the student has reviewed it or supply new measurements.
Read the functions below and connect them to your own run's evidence before
using the notes in the submission or demonstration.

## Source and purpose

The baseline is `src/baseline/raytrace/run_benchmark.py`, copied unchanged from
pyperformance **1.14.0**. `SOURCES.json` records its origin and the SHA-256:
`88ef4d9060d8e8f6ce40f376477aaf89cc808fa44813225a3071a05a1467f017`.
Run provenance records the actual source and source-tree hashes separately.

It constructs and renders a small fixed scene using a Python object-oriented
ray tracer. Standard-library `math` supplies square roots and camera
trigonometry; standard-library `array` supplies the byte image buffer; `pyperf`
supplies timing and the benchmark runner. The numerical operations are ordinary
Python expressions and method calls, not NumPy or a native rendering engine.

## Scene, data structures, and data flow

Each `bench_raytrace()` loop creates a new `Canvas` and `Scene`. Defaults are
**100 by 100 pixels**, with:

- Seven spheres: one large sphere and six smaller spheres.
- One `Halfspace` with a checkerboard surface.
- Two point lights and a fixed camera looking toward `(0, 3, 0)`.

`Scene.objects` is a list of eight `(geometry, surface)` tuples.
`Scene.lightPoints` is a list of two `Point` objects. `Point` and `Vector` store
three numeric instance attributes. Most vector operations create new Python
objects rather than updating one in place. `Ray` stores an origin and a
**normalized** direction, so every construction invokes normalization even
when a caller constructs an equivalent direction repeatedly. `Canvas.bytes`
is an `array('B')` holding three RGB bytes per pixel: 30,000 bytes at the default
size, excluding object overhead.

`Scene.render()` computes a camera basis and visits every pixel. It constructs
a primary ray, calls `rayColour()`, and writes the returned colour through
`Canvas.plot()`. Plotting flips the vertical image index and clamps/scales
channels into bytes. The source uses `halfHeight = 0.75 * halfWidth` even for
the square default pixel grid; preserve this camera convention.

`rayColour()` evaluates `intersectionTime()` for **every object** into a list,
then `firstIntersection()` selects the nearest accepted intersection. There
is no bounding-volume tree or spatial acceleration structure. At a hit it
constructs the hit point and normal and calls the object's surface shader.

`SimpleSurface.colourAt()` combines three contributions:

1. A reflected ray, recursively traced when the specular coefficient is
   positive. Here the implementation models reflection; it is not a separate
   physically based specular-lighting calculation.
2. Lambert lighting from lights returned by `visibleLights()`. That method
   uses `_lightIsVisible()` to test potential occluders, with an early exit on
   the first accepted blocker.
3. An ambient term. `CheckerboardSurface.baseColourAt()` chooses alternate
   base colours using the hit position.

The recursion counter starts at zero. `rayColour()` returns black when its
**entry** depth is greater than three; otherwise it increments the counter and
restores it in `finally`. Consequently a path can trace a primary ray plus
three reflected levels. A fifth call, entering at depth four, immediately
returns black. There is at most one reflected continuation per hit, not a
binary reflection/refraction tree. Shadow rays do not recursively shade hits.

For width `W`, height `H`, traced depth `D`, object count `M` and light count
`L`, a useful upper-bound model is `O(W * H * D * M * (1 + L))`. Actual work
depends on misses, reflections, lighting and early shadow exits. With fixed
`D <= 4`, `M = 8` and `L = 2`, pixel count is the main scaling parameter.
Storage includes the `O(W*H)` canvas, `O(M+L)` scene, and bounded recursive
frames/intersection lists, up to `O(D*M)` live intersection entries. Temporary
vector allocation is frequent even though the resident scene is small.

## Measurement boundaries and baseline semantics

`bench_raytrace(loops, width, height, filename)` starts its internal timer
before constructing each canvas and scene. Construction, rendering, and pixel
writes are timed. If a filename is supplied, writing the **last** canvas as a
PPM happens after the internal timer. The profiling driver passes no filename,
so its normal measured workload performs no image-file I/O.

Unlike nbody, each loop rebuilds scene and image state. Warmups do not advance
a persistent scene. The gated perf region excludes imports and warmups but
includes whole public calls, driver overhead, and the small gate boundary
cost. Record actual width, height, calls, warmups and interpreter from the run
receipt. Profiled durations are not substitutes for unprofiled timing results.

The supplied benchmark contains simplified or unusual rendering semantics:

- `_lightIsVisible()` checks for any accepted positive intersection but does
  not check whether it lies before the light's distance. It also reconstructs
  `Ray(p, l - p)` inside the object loop.
- `Halfspace.intersectionTime()` returns `1 / -v` using the ray direction and
  plane normal; it does not use the general ray-origin/plane-point formula.
- `Sphere.intersectionTime()` returns the near quadratic root only. The caller
  applies the benchmark's own epsilon acceptance test.
- `CheckerboardSurface.baseColourAt()` calls `v.scale(...)` without keeping
  the returned vector. The default check size is one, but the general parameter
  behavior is not that of an in-place scale.

These are properties of the reference program, not permissions to silently
change its geometry or image while measuring an optimization. Preserve them
for a like-for-like benchmark comparison. Any independent renderer correction
must be identified and evaluated as a changed workload. The existing render
output and correctness checks provide a baseline reference, not proof that
the source is a physically complete renderer.

## Expected hotspots and what profiling must establish

Source inspection predicts substantial cost in `Sphere.intersectionTime()`,
`Vector.dot()`, `Point.__sub__()`, normalization, object constructors, and
shadow visibility. `_lightIsVisible()` repeats subtraction, Ray construction
and normalization inside its object loop, making it an especially useful
place to inspect call counts and inclusive source-level costs. This is a
testable redundancy hypothesis, not a measured speedup or a change included
in this package.

Native perf may attribute work to interpreter evaluation, Python calls and
attribute lookup, float arithmetic, allocation/deallocation, and native math
helpers. The perf-derived graph is the required native evidence; supplementary
Python sampling can explain which methods lead to those costs. cProfile is
useful for call counts but instruments Python calls and can disproportionately
perturb a call-heavy benchmark.

A function's **inclusive** percentage includes its callees and cannot be
added to those callees' percentages. A high L1 miss count can support greater
locality pressure but does not establish memory-bound execution without stall
or other corroborating evidence. Few explicit `dict.get()` calls also say
nothing decisive about native attribute-lookup costs. Use the new accepted
native and Python evidence to determine the actual bottleneck; do not turn
these expectations into claimed results.

## Questions to answer in the demonstration

1. Trace one pixel from camera-ray construction through intersection, shading,
   reflection, shadow tests and RGB storage. Which steps allocate objects?
2. Why are there at most four traced shading levels, and how do reflected and
   shadow rays differ?
3. Which rendering conventions must remain unchanged for a valid comparison,
   even if a more general ray tracer would implement them differently?
4. How would you distinguish redundant normalization/calls, interpreter
   overhead, arithmetic cost and memory stalls using the available evidence?
