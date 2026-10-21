# Environments

`create_env` builds a pinned environment for the study's code and writes its
lock file. It refuses until claims are recorded (rule 5). Environments are
never rebuilt in place: create a new name when requirements change, so earlier
runs keep the lock they used.

Requirements come from `requirements` (a file inside `code/`), else from
`code/requirements.txt` when present, plus any `packages`. Pin exact versions.

## uv (default)

```json
{ "study": "/abs/study", "backend": "uv", "python": "3.11" }
```

IRP runs `uv venv` (uv downloads the Python version when it is missing),
installs the requirements with `uv pip install`, and records `uv pip freeze` as
`envs/<name>/lock.txt`. Runs put the environment's `bin` first on `PATH` and
set `VIRTUAL_ENV`.

A virtual environment is **not a sandbox**: code in it runs with your
permissions and network access.

## Docker

```json
{ "study": "/abs/study", "backend": "docker", "python": "3.12", "system_packages": ["libgl1"] }
```

IRP writes `envs/<name>/Dockerfile` from `python:<version>-slim` (or
`base_image`), pulls the base image and records its digest, builds the image,
and records `pip freeze` from inside it as the lock file. Before the first run
it checks that the container can see `code/`.

Runs use:

```text
docker run --rm --init -v <study>/code:/work -w /work --user <uid>:<gid> [--network none] [--gpus all] [--memory 8g] <image> sh -c "<command>"
```

Only `code/` is mounted. `network: false` disables networking for a run;
`gpu: true` on the environment requests all GPUs; `memory_limit` caps memory.

### Docker on macOS

Docker on macOS runs inside a VM (Colima, Docker Desktop, OrbStack) that shares
only some host folders. Colima shares your home directory by default. If the
study lives elsewhere, IRP refuses the run with `provider_unavailable`
instead of letting the container see an empty `/work`. Keep studies under your
home directory, or add the folder to the VM's mounts.

## Which to use

| Situation | Backend |
| --- | --- |
| Code you wrote from the paper, small dependencies | uv |
| Code you did not write, or a paper whose dependencies you do not trust | docker |
| System libraries the paper needs (OpenGL, ffmpeg) | docker with `system_packages` |
| A CUDA base image | docker with `base_image` and `gpu: true` |

## Running without an environment

`run` with `env: null` uses the host environment. Provenance then has no lock
file; prefer a named environment for any run that counts.
