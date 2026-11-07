# The Raiker beta

Raiker is in **beta**. It is ready for people who are comfortable reporting
problems, and not yet for anyone who needs it to be dependable. This page says
what the beta covers, what it does not, what is known to be wrong, how to tell
us, and what happens if a beta release has to be withdrawn.

The release criteria behind this page are in the
[first beta release plan](../plans/BETA_RELEASE_PLAN.md#beta-release-criteria).

## Supported systems

| Your computer | Supported in beta | Notes |
|---|---|---|
| Windows 11, and Windows 10 22H2 (1809 or later installs), x86-64 | Yes | Windows on Arm runs the x86-64 build under emulation |
| macOS 12 or later on Apple silicon | Yes | Intel Macs are not supported by this beta |
| Linux x86-64 and ARM64 with glibc 2.35+ (Ubuntu 22.04+, Debian 12+, Fedora 36+) | Yes | Command execution needs Bubblewrap; see below |

| | Minimum | Comfortable |
|---|---|---|
| Memory | 4 GB | 8 GB with a hosted provider; 16 GB or more for local models |
| Free storage | 2 GB | 20 GB or more if you will download local models |
| Graphics | Not required | An NVIDIA, AMD or Intel GPU, or Apple silicon, speeds up local models |

## What is in the beta

| Feature | Status | What that means |
|---|---|---|
| Chat, Tasks, Schedule, Memory, Models, Settings | **Included** | — |
| Hosted providers (Anthropic, OpenAI, OpenRouter) and local runtimes (Ollama, LM Studio) | **Included** | Other providers still connect, and are marked *Experimental* in **Models › Add** |
| Local GGUF models on the llama.cpp engine Raiker installs | **Included** | See [The llama.cpp engine Raiker manages](connecting-a-model.md#the-llamacpp-engine-raiker-manages) |
| Build (coding agent) | **Included, limited** | Works in an isolated copy of your project. If you edit a file the copy also changed, **Apply** shows both versions and waits until you choose **Overwrite** for it |
| Running commands | **Included where confirmed** | Raiker checks its sandbox on your computer at start. Where any protection cannot be confirmed, commands are turned off: the composer says *Commands unavailable here* and Build's **Run** waits, while Plan and Propose still work. Commands never fall back to running unprotected |
| Voice dictation and read-aloud | **Included, limited** | On-device only. Until the managed speech engines land, dictation needs a local transcription server you set up yourself |
| Talking with Raiker (hands-free conversation) | **Preview** | Off by default; see the [voice plan](../plans/VOICE_CONVERSATION_SPEC.md) |
| Design documents and exports | **Included** | Image generation is **Preview** until a real provider round trip is verified |
| Supported connections (GitHub, email, calendar, web search, local MCP) | **Included** | Others are marked *Experimental* and ask for an extra confirmation |
| Remote access from another device | **Preview** | Verified live on Linux only |

## Known issues

These are open at the time of the beta and tracked in
[TO_BE_FIXED](../plans/TO_BE_FIXED.md). The full list of deliberate limits is in
[Known limits](../architecture/KNOWN_LIMITS.md).

- **Builds may be unsigned.** Until release signing is configured, Windows
  SmartScreen and macOS Gatekeeper will warn you. On macOS, open the app the
  first time with **Control-click → Open**. On Windows, choose
  **More info → Run anyway**. The release notes say whether a beta build is
  signed.
- **Commands may be unavailable on your computer.**
  - On Windows, the restricted-account sandbox still has open gaps, so
    commands stay off unless every check passes.
  - macOS enforcement checks passed on `macos-15` and `macos-15-intel` for
    the current source commit; signed-installer, upgrade and fresh-machine
    release evidence is still required.
  - On Linux, install Bubblewrap (`sudo apt install bubblewrap`,
    `sudo dnf install bubblewrap`). **Settings → Advanced → Runtime → Command sandbox** shows each check.
- **Plugins and local MCP servers see only their own folder** and have no
  network. A server that needs to read your project cannot yet.
- **Model conversion** (safetensors to GGUF) works only on Linux with a
  llama.cpp you installed yourself. Download a GGUF instead where one exists.
- **Managed llama.cpp passes its cross-platform CI path.** PR #246 corrected
  source-only stable-release selection, and its live jobs passed on Windows,
  macOS, and Linux. Remaining beta evidence is an owner-machine CUDA run, an
  owner-machine Vulkan run, and fresh signed-installer validation on the
  release candidate.
- **Release proof is still being completed.** The beta requires an exact-commit
  credential/privacy canary, destructive recovery drill, and 30-minute
  local-only egress recording before sign-off.
- **The workspace encryption key cannot be rotated** in place yet.
- **Windows window size at 150% display scaling** can drift by a few pixels
  between restarts.

## Sending feedback

**Settings → General → Beta feedback** opens a short form on GitHub, already
filled in with your Raiker build and operating system. Raiker sends nothing
itself; you see every field before you submit, and the issue is public.

- **Report a problem** — something broke or behaved wrongly.
- **Suggest an improvement** — something could be clearer or easier.
- **Copy diagnostics** — copies Raiker's redacted support bundle, for you to
  paste into the form if you choose. Read it first.

You can also open the forms directly from the
[repository's issues page](https://github.com/sharRahul/Raiker/issues/new/choose).
**Never report a security problem in a public issue**; follow
[SECURITY.md](../../SECURITY.md).

## Updating and going back

- Updates arrive on the beta channel and are installed from
  **Settings → About & updates**. Raiker verifies each download before replacing any
  file. If an update changes the database, Raiker backs it up first.
- To return to the previous beta, use **Roll back** on the same page when it is
  offered, or reinstall the previous installer from the
  [releases page](https://github.com/sharRahul/Raiker/releases). Your data is
  kept. A build refuses to open data written by a newer build rather than
  misreading it. In that case, restore the backup taken before the update
  (**Settings → General → Backups**).

## If a beta release is withdrawn

If a beta release turns out to lose data, leak a credential, or let something
escape the sandbox, it is withdrawn:

1. The release is removed from the releases page and the update channel stops
   offering it, normally within an hour of the problem being confirmed.
2. An advisory is posted on the releases page and in SECURITY.md, saying
   what happened, which builds are affected, and what to do.
3. A copy of Raiker that has the withdrawn build installed shows the advisory
   when it next starts, with **Roll back** where a rollback is possible.

A less serious problem that breaks a main feature is fixed in the next beta
within about a week, or the release is withdrawn if that is not possible.

## Uninstalling

See [Uninstall](managing-the-host.md#uninstall). Removing Raiker's data also
removes the llama.cpp engine and any voice models Raiker installed, since they
live inside its data folder. Your own model files and other tools are not
touched.
