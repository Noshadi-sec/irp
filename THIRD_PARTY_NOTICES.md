# Third-party notices

IRP-authored code is licensed under [MIT](LICENSE). Third-party material
keeps its own copyright, license and notice requirements. Project names
identify integrations; they do not imply affiliation or endorsement.

This inventory covers IRP's direct runtime dependencies, its optional
extras, and the external tools it drives. A listed tool is not bundled unless
the table says so. Each installed package carries its own license file; keep
those notices when you redistribute an environment that contains them.

## Runtime dependencies (installed with IRP)

| Package | Version | License | Role |
| --- | --- | --- | --- |
| [mcp](https://github.com/modelcontextprotocol/python-sdk) | 2.3.0 | MIT | Official MCP Python SDK: the stdio server |
| [typer](https://github.com/fastapi/typer) | 0.26.8 | MIT | Command-line interface |
| [pydantic](https://github.com/pydantic/pydantic) | 2.14.1 | MIT | Tool input contracts and schemas |
| [httpx](https://github.com/encode/httpx) | 0.28.1 | BSD-3-Clause | arXiv and PyPI downloads |
| [pypdf](https://github.com/py-pdf/pypdf) | 6.21.1 | BSD-3-Clause | PDF text extraction |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | 5.14.0 | BSD-3-Clause and Apache-2.0, with PDFium's bundled dependency licenses | Page images; ships a PDFium binary |
| [Pillow](https://github.com/python-pillow/Pillow) | 12.3.0 | MIT-CMU | PNG encoding of page images |
| [tomlkit](https://github.com/python-poetry/tomlkit) | 0.15.2 | MIT | Comment-preserving edits of Codex configuration |

Transitive dependencies (for example anyio, click, pydantic-core, starlette)
are resolved by your installer; their licenses ship inside each installed
distribution's metadata.

PyMuPDF and MinerU were considered for page images and equation extraction and
are not used because they are AGPL-licensed.

## Optional extras

| Extra | Package | License | Role |
| --- | --- | --- | --- |
| `irp-agents[docling]` | [Docling](https://github.com/docling-project/docling) 2.141.0 | MIT | Structured PDF text and tables |
| `irp-agents[modal]` | [modal](https://github.com/modal-labs/modal-client) 1.6.2 | Apache-2.0 | Experimental GPU sandboxes for `run_remote` |

Docling downloads model weights on first use; those weights carry their own
licenses.

## External tools IRP drives (bring your own)

| Tool | Role | Notes |
| --- | --- | --- |
| [uv](https://github.com/astral-sh/uv) | Virtual environments and lock files | MIT or Apache-2.0; never installed by IRP |
| [git](https://git-scm.com/) | Code commits for provenance | GPL-2.0; never installed by IRP |
| [Docker](https://www.docker.com/) | Isolated environments and runs | Docker's own terms apply; never installed by IRP |
| Base images (for example `python:3.11-slim`) | Docker environments | Each image carries its own licenses |
| [Modal](https://modal.com/) | Paid GPU compute | A commercial service with its own terms and pricing |

## Papers and datasets

IRP downloads papers from arXiv for the user's own reading and never
redistributes them: study bundles exclude the `paper/` directory, and reports
link to the source instead. Papers and datasets keep their authors' licenses;
check them before sharing derived material. arXiv's API terms ask clients to
identify themselves and to space requests; IRP sends an IRP User-Agent
and waits three seconds between arXiv requests.
