"""Input contracts for every tool, shared verbatim by the MCP server and the CLI.

The MCP input schema is generated from these models and the CLI validates its
options through them, so the two adapters cannot accept different inputs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LocationKind = Literal["table", "figure", "section", "equation", "algorithm", "text", "appendix"]
Comparator = Literal["approx", "at_least", "at_most"]
Scope = Literal["full", "shortened", "smoke"]
Reduce = Literal["last", "first", "max", "min", "mean"]
NoteKind = Literal["limitation", "deviation", "not_checked", "author_contact", "other"]

STUDY_DESCRIPTION = (
    "Absolute path of the study directory. fetch_paper creates it; every other tool "
    "reads and appends to its evidence log."
)


class StudyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study: str = Field(description=STUDY_DESCRIPTION, min_length=1)


class FetchPaperInput(StudyInput):
    paper: str = Field(
        description="arXiv ID or URL (e.g. '2501.12345' or '2501.12345v2'), a direct PDF URL, or a "
        "local path to a PDF, a LaTeX source directory, or a .tar.gz/.zip source archive.",
        min_length=1,
    )
    prefer: Literal["latex", "pdf"] = Field(
        "latex",
        description="Read LaTeX source when it exists (exact equations), else the PDF.",
    )
    parser: Literal["auto", "pypdf", "docling"] = Field(
        "auto",
        description="PDF text parser when no LaTeX is used. 'auto' uses Docling when installed, else pypdf.",
    )
    with_pdf: bool = Field(
        True,
        description="Also download the PDF so get_page_image can show figures, tables and equations.",
    )


class GetSectionInput(StudyInput):
    id: str = Field(
        description="What to read: a section id ('sec:3', 'sec:3.2'), an item id ('tab:2', 'fig:1', "
        "'eq:4', 'alg:1'), a LaTeX label ('eq:loss'), a section title, 'abstract', 'index' for the "
        "outline, 'page:5' for one PDF page, or a line range 'lines:120-180'.",
        min_length=1,
    )
    offset: int = Field(0, ge=0, description="Skip this many lines of the selection (paging).")
    max_lines: int = Field(300, ge=1, le=2000, description="Return at most this many lines.")


class GetPageImageInput(StudyInput):
    page: int = Field(ge=1, description="1-based page number of the paper PDF.")
    dpi: int = Field(
        110, ge=50, le=300, description="Rendering resolution; raise it for small math."
    )


class AddClaimInput(StudyInput):
    statement: str = Field(
        description="Short name of the claim, e.g. 'Test accuracy on CIFAR-10'.",
        min_length=1,
        max_length=200,
    )
    metric: str = Field(
        description="Metric name, e.g. 'test_accuracy'.", min_length=1, max_length=100
    )
    value: str = Field(
        description="The paper's number exactly as printed, e.g. '94.1%', '0.31' or '2.0x'. Only the "
        "paper's own number belongs here, never a result.",
        min_length=1,
        max_length=60,
    )
    where: str = Field(
        description="Where the claim appears, as a reader would say it: 'Table 2, row 3', 'Figure 4', "
        "'Section 5.2'.",
        min_length=1,
        max_length=200,
    )
    where_kind: LocationKind = Field("table", description="Kind of place the claim appears.")
    source_file: str | None = Field(
        None,
        description="Paper file of the printed value, as get_section shows it (e.g. 'main.tex' or "
        "'paper.pdf#page=7'). With source_line, the value is checked at that line.",
    )
    source_line: int | None = Field(
        None, ge=1, description="Line of the printed value in source_file."
    )
    page: int | None = Field(None, ge=1, description="PDF page where the claim appears, if known.")
    comparator: Comparator = Field(
        "approx",
        description="'approx' for 'about this value', 'at_least' for lower bounds such as speed-ups, "
        "'at_most' for upper bounds such as error rates.",
    )
    tolerance_rel: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Reproduced if within this fraction of the paper's value (0.01 = 1%).",
    )
    tolerance_abs: float | None = Field(
        None, ge=0, description="Reproduced if within this absolute difference."
    )
    close_rel: float | None = Field(None, ge=0, le=1, description="Close if within this fraction.")
    close_abs: float | None = Field(
        None, ge=0, description="Close if within this absolute difference."
    )
    seeds_in_paper: int | None = Field(
        None, ge=1, description="Runs or seeds the paper averaged over, if stated."
    )
    notes: str | None = Field(
        None, max_length=2000, description="Anything a reader should know about this claim."
    )


class ListClaimsInput(StudyInput):
    pass


class AddGuessInput(StudyInput):
    missing: str = Field(
        description="The detail the paper left out, e.g. 'Warmup length not stated'.", min_length=1
    )
    choice: str = Field(description="What was chosen, e.g. '5 epochs'.", min_length=1)
    why: str = Field(description="Why, e.g. 'as in cited paper [12]'.", min_length=1)
    source: str | None = Field(
        None, description="Where the choice comes from: a citation, a URL or 'common default'."
    )
    claims: list[str] = Field(default_factory=list, description="Claim ids this guess can affect.")


class MapMethodInput(StudyInput):
    paper_element: str = Field(
        description="The paper element, e.g. 'Eq. 3 (loss)' or 'Algorithm 1, line 4'.", min_length=1
    )
    paper_ref: str | None = Field(
        None,
        description="Index id or LaTeX label of that element, e.g. 'eq:3' or 'eq:loss'; checked against the paper.",
    )
    code_file: str = Field(
        description="File inside the study's code/ directory, e.g. 'src/loss.py'.", min_length=1
    )
    code_line: int = Field(ge=1, description="First line that implements the element.")
    end_line: int | None = Field(
        None, ge=1, description="Last line, when the implementation spans several."
    )
    note: str | None = Field(
        None, max_length=1000, description="Why this line implements the element, if not obvious."
    )


class CreateEnvInput(StudyInput):
    name: str = Field(
        "main", pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$", description="Environment name; never reused."
    )
    backend: Literal["uv", "docker"] = Field(
        "uv",
        description="'uv' builds a virtual environment (not a sandbox); 'docker' builds an image runs are isolated in.",
    )
    python: str = Field(
        "3.11", pattern=r"^3\.\d{1,2}(\.\d{1,2})?$", description="Python version, e.g. '3.11'."
    )
    requirements: str | None = Field(
        None,
        description="Requirements file inside code/. Defaults to code/requirements.txt when it exists.",
    )
    packages: list[str] = Field(
        default_factory=list, description="Extra packages, e.g. ['numpy==2.1.0']."
    )
    base_image: str | None = Field(
        None, description="Docker base image; default python:<python>-slim."
    )
    system_packages: list[str] = Field(
        default_factory=list, description="Debian packages for the Docker image."
    )
    gpu: bool = Field(False, description="Docker runs request all GPUs (--gpus all).")


class RunInput(StudyInput):
    command: str = Field(
        description="Shell command to run inside the environment, e.g. 'python train.py --epochs 30'.",
        min_length=1,
    )
    env: str | None = Field(
        "main",
        description="Environment from create_env; null uses the host environment (no lock file).",
    )
    scope: Scope = Field(
        "full",
        description="'full' is the faithful configuration and is the only scope that can count; "
        "'shortened' (fewer steps or data) and 'smoke' never count.",
    )
    seed: int | None = Field(
        None, description="Seed, passed as IRP_SEED and PYTHONHASHSEED and recorded."
    )
    cwd: str = Field(".", description="Working directory inside code/.")
    timeout_s: int = Field(
        1800, ge=1, le=7 * 24 * 3600, description="Stop the run after this many seconds."
    )
    wait: bool = Field(
        True,
        description="Wait for the run to finish. For runs longer than your client's tool timeout, pass "
        "false and poll run_status.",
    )
    network: bool = Field(True, description="Docker only: allow network access during the run.")
    memory_limit: str | None = Field(None, description="Docker only: memory cap such as '8g'.")
    commit: bool = Field(
        True, description="Commit code/ to git before the run so the report names the exact code."
    )
    note: str | None = Field(
        None, max_length=1000, description="What this run is for, shown in the report."
    )


class RunStatusInput(StudyInput):
    run_id: str = Field(description="Run id, e.g. 'r3'.")
    wait_s: int = Field(
        0, ge=0, le=600, description="Wait up to this many seconds for the run to finish."
    )
    tail_lines: int = Field(20, ge=0, le=500, description="Lines of stdout and stderr to return.")


class RunRemoteInput(StudyInput):
    command: str = Field(description="Shell command to run in the remote sandbox.", min_length=1)
    env: str = Field(
        "main", description="Environment whose requirements and Python version the sandbox uses."
    )
    provider: Literal["modal", "runpod", "hf_jobs"] = Field(
        "modal", description="Compute provider."
    )
    gpu: str = Field(description="GPU type, e.g. 'A10G', 'A100', 'H100'.")
    gpu_count: int = Field(1, ge=1, le=8, description="Number of GPUs; multiplies the estimate.")
    hours: float = Field(
        gt=0, le=72, description="Time limit in hours; also the basis of the cost estimate."
    )
    approved: bool = Field(
        False,
        description="Set true only after showing the person the cost estimate and receiving their approval.",
    )
    scope: Scope = Field("full", description="'full' is the only scope that can count; see run.")
    seed: int | None = Field(None, description="Seed, passed as IRP_SEED and recorded.")
    outputs: list[str] = Field(
        default_factory=list, description="Files under code/ to copy back after the run."
    )
    wait: bool = Field(
        False, description="Wait for completion; remote runs usually outlast tool timeouts."
    )
    note: str | None = Field(
        None, max_length=1000, description="What this run is for, shown in the report."
    )


class MetricSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Measurement name, usually the claim's metric.", min_length=1)
    source: str = Field(
        "stdout",
        description="'stdout', 'stderr', or a file the run wrote, by its study path, e.g. 'code/results.json'.",
    )
    key: str | None = Field(
        None, description="Read 'key: 0.93', 'key=0.93' or '\"key\": 0.93' lines."
    )
    regex: str | None = Field(
        None,
        description="Regex with one capture group (or a group named 'value') around the number.",
    )
    json_pointer: str | None = Field(
        None, description="JSON pointer into a JSON file, e.g. '/test/accuracy'."
    )
    csv_column: str | None = Field(None, description="Column of a CSV file.")
    reduce: Reduce = Field(
        "last", description="Which occurrence: last, first, max, min, or mean of all."
    )

    @model_validator(mode="after")
    def exactly_one_selector(self) -> MetricSpec:
        chosen = [
            x for x in (self.key, self.regex, self.json_pointer, self.csv_column) if x is not None
        ]
        if len(chosen) != 1:
            raise ValueError("Give exactly one of key, regex, json_pointer or csv_column.")
        return self


class ExtractMetricsInput(StudyInput):
    run_id: str = Field(description="Completed run to read, e.g. 'r3'.")
    specs: list[MetricSpec] = Field(
        min_length=1, max_length=50, description="One spec per number to extract."
    )


class CompareInput(StudyInput):
    claim_id: str = Field(description="Claim to judge, e.g. 'c1'.")
    measurement_ids: list[str] = Field(
        default_factory=list,
        description="Measurements from extract_metrics, one per seed or run; their mean is compared.",
    )
    unit_scale: float = Field(
        1.0,
        gt=0,
        description="Power of ten to convert units, e.g. 100 when the log prints 0.938 and the paper 93.8%.",
    )
    could_not_run: bool = Field(
        False, description="Record 'could not run' instead of a measured verdict."
    )
    reason: str | None = Field(
        None, description="Could not run: short reason, e.g. 'needs 8 GPUs for 2 days'."
    )
    blocking_error: str | None = Field(
        None, description="Could not run: the exact blocking error or constraint."
    )
    failed_run_id: str | None = Field(
        None, description="Could not run: the run that failed, if any."
    )
    context_measurement_ids: list[str] = Field(
        default_factory=list,
        description="Measurements shown for context that do not count, e.g. from a shortened run.",
    )
    note: str | None = Field(
        None, max_length=2000, description="Context for the verdict, shown in the report."
    )


class ReportInput(StudyInput):
    draft: bool = Field(
        False, description="Write report.draft.md/json even if the completion gate has not passed."
    )
    bundle: str | None = Field(
        None,
        description="Absolute path of a new directory to receive a shareable bundle (report, evidence, code, "
        "locks, logs; never the paper PDF or source).",
    )


class VerifyInput(StudyInput):
    pass


class StudyStatusInput(StudyInput):
    pass


class AddNoteInput(StudyInput):
    kind: NoteKind = Field(
        description="limitation, deviation (a forced change from the paper), not_checked, author_contact or other."
    )
    text: str = Field(min_length=1, max_length=4000, description="The note itself, in plain words.")
    claims: list[str] = Field(default_factory=list, description="Claim ids the note concerns.")
