# Personal beta scope — owner decision, 2026-11-09

This records the owner's explicit clarification during Linux beta work and
supersedes broader distribution assumptions in earlier release plans.

- **Audience:** personal use, at most five users. This is the supported scale,
  not a new account-count lock silently introduced into existing workspaces.
- **Devices:** the owner's own PC first; phone and iPad app access later.
  A future mobile client can use the PC's authenticated service. Native app,
  web app and store delivery choices are not decided by this clarification.
- **Distribution:** no mass production or commercial-grade publisher/signing
  infrastructure is required. Unsigned personal test packages with verified
  hashes are acceptable. Existing beta signatures/pins can be kept for
  integrity; purchased certificates, notarization and public release/market
  delivery are not personal-beta prerequisites.
- **Speech:** remove Piper engines and voices. Every managed TTS profile uses
  Kokoro-82M: int8 for Lite/Balanced, fp32 for High quality. The OS local-voice
  fallback remains. Piper's dataset/voice licence ambiguity and JSON sidecar
  are removed work, not pending acceptance gates.
- **Keep:** authentication and user isolation, approved connector authority,
  safe Apply/rollback, backup/recovery, stop/limits, digest verification and
  truthful capability states. Small scale does not waive these safeguards.
- **Acceptance:** focus PC journeys on the owner's actual chosen model and
  enabled connections. A broad five-repeat all-model/all-platform matrix,
  three-person novice study and public distribution programme are later
  general-release evidence, not blockers to a private personal trial.
  Do not claim untested mobile access, OAuth revocation, packaged speech or
  full-feature local-only traffic as passed.

## Kokoro licence and runtime evidence

The [Kokoro-82M model card](https://huggingface.co/hexgrad/Kokoro-82M)
classifies the model as Apache-2.0. The [kokoro-onnx implementation](https://github.com/thewh1teagle/kokoro-onnx)
is MIT; its runtime depends on phonemizer/espeak-ng. Those retain their own
licences and notices. Removing Piper removes the ambiguous per-voice review;
it is not evidence that every Kokoro runtime dependency is permissive or
already bundled. No licence policy is broadened by assumption.

Real int8 synthesis using verified catalogue assets and `kokoro-onnx==0.6.1`
passed: 24 kHz nonzero PCM, 1.877-second clip, 295,440 KiB peak RSS, and no IP
destination observations during direct inference. The managed live test
correctly refused under the host's available-memory guard (less than its
2 GiB reserve free); that refusal is retained. This proves direct synthesis,
not full managed-service or frozen-package acceptance.

The earlier signed candidate and 31-minute scoped audit identify runtime
`6c211b60`. They precede Piper removal and are historical qualification
receipts. New artifacts must name the later runtime commit; do not relabel
those earlier outputs as containing this change.

## Personal packaged TTS

The opt-in `--bundle-voice` Linux freeze has passed a real worker test using
catalogue-verified assets: loopback token authentication, nonzero 24 kHz WAV,
and clean stop. This is distinct from the full-profile admission refusal above.
The build checks exact runtime versions from `requirements/voice.txt`, retains
licence metadata and [voice notices](../licensing/voice/README.md), and does
not enable a public distribution/signing requirement.

Example private build, in a Python 3.12 build environment:

```bash
python -m pip install --require-hashes -r requirements/release-build.txt
python -m pip install --require-hashes -r requirements/voice.txt
python -m pip install --no-deps -e .
python scripts/build_desktop_app.py --version 0.9.0 --channel beta \
  --target linux-x86_64 --commit "$(git rev-parse HEAD)" --bundle-voice \
  --out output/personal-beta
```

Use a clean committed source revision for candidate provenance. The ordinary
public workflow does not opt into this private runtime bundle. A later mobile
client does not need to run the speech model on the phone/iPad to use the PC's
authenticated service.

The 13 exact optional runtime dependency versions were also queried against
OSV on 2026-11-09: no advisory IDs were returned. This is a dated dependency
check, not a permanent safety assertion.
