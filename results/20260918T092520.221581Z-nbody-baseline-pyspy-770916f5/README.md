# Python sampling profile

Whole fixed-work driver process: imports, in-process warmup, benchmark calls and receipt writing. NOT perf-gated.

Separate statistical Python profile; not timing or a PMU measurement.

Sampler or benchmark failed; see pyspy.stderr.txt and workload.json. Permissions were not changed.

Warmup/startup samples have not been filtered out. Native perf has a different sampling scope.
