# python-numpy-fenics-consumer

This repository is a deliberately small downstream consumer of
[`precsim/python-numpy-fenics`](https://github.com/precsim/python-numpy-fenics).
It exists to prove that the producer's public consumer interface is sufficient
for a bridge shaped like `precsim/python-matlab-octave-bridge`, without carrying
that bridge's private implementation.

The repository keeps only the bridge surface needed for the integration proof:

- a host-neutral MEX entry point with dynamically resolved GNU Octave/MATLAB
  host functions;
- runtime-relative dynamic CPython loading and isolated embedding;
- a tiny Python backend with scalar, NumPy, and FEniCS probes;
- one GNU Octave smoke fixture;
- a source-selection `bridge-build.json` consumed by the producer kit.

Generic runtime acquisition, verification, compilation, native-boundary audit,
test layout, and qualification logic is not reimplemented here. The complete
producer `consumer-kit/` is vendored under `vendor/python-runtime-consumer-kit/`
and identified by `vendor/python-runtime-consumer-kit.upstream.json`.

## Pinned inputs

The tooling pin and runtime pin are intentionally independent.

- Tooling: producer commit `4be16e955706a5860daee8e29f710f19e4b205ab`,
  consumer-kit tree SHA-256
  `9a6eeaa80cce26a401476e0ef1810f45f4ad79a894b5c474fd379d26a25aa767`.
- Runtime: `locks/consumer/python-runtime-cp314.json`, containing the immutable
  `runtime-v0.1.0-rc3` CPython 3.14.10 core/NumPy inputs and the producer-bound
  FEniCS overlay/base identities for all four supported targets.

Changing the vendored kit does not change the runtime receipt, and changing the
runtime receipt does not silently update the kit.

## Local contract checks

These checks are network-free and do not require a compiler or GNU Octave:

```text
python tools/check_consumer_kit.py
python -m unittest discover -s tests -v
```

They verify the vendored kit identity, the full bridge's three-export MEX ABI,
complete runtime pin matrix, deliberately small source surface, MEX-directory
runtime layout, and the deterministic scalar backend behavior.

## End-to-end qualification

`.github/workflows/qualify-consumer.yml` follows the same downstream shape the
full bridge is expected to use:

1. stage and re-attest the exact producer `core` runtime;
2. compile one MEX candidate per target from `bridge-build.json`;
3. reuse that exact candidate for `core`, `numpy`, and optionally `fenics`;
4. stage and re-attest each selected runtime profile;
5. copy the verified runtime into a disposable package, place the exact MEX
   beside the producer runtime (matching the full bridge's runtime-root model),
   and run the real GNU Octave -> MEX -> embedded CPython -> backend path;
6. write qualification evidence bound to the MEX, runtime receipt, and native
   audit identities.

Pull requests and pushes qualify `core+numpy`. A manual workflow dispatch can
select `core`, `core+numpy`, or `core+numpy+fenics`.

The resulting evidence qualifies this mock consumer only. Its purpose is to
catch producer/consumer contract regressions before the full bridge adopts the
same vendored kit and runtime receipt interface.
