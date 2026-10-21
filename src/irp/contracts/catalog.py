"""The tool catalog: one named contract per operation, in workflow order.

Both adapters bind handlers to these contracts by name. Catalog order is for
reading only; it never selects an operation or a schema.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from irp.contracts import inputs

Effect = str  # reads_study | writes_study | network | runs_code | paid_compute


@dataclass(frozen=True)
class ToolContract:
    name: str
    title: str
    stage: str
    summary: str
    description: str
    input_model: type[BaseModel]
    effects: tuple[Effect, ...]
    read_only: bool
    open_world: bool = False
    returns_image: bool = False


CATALOG: tuple[ToolContract, ...] = (
    ToolContract(
        name="fetch_paper",
        title="Fetch paper",
        stage="Intake",
        summary="Downloads the arXiv LaTeX source or the PDF, hashes it, splits it into sections",
        description=(
            "Create the study directory and fetch the paper into it: arXiv LaTeX source first (exact "
            "equations), the PDF as fallback and for page images. Records arXiv ID and version, file "
            "hashes and an outline of sections, tables, figures, equations and algorithms. Call this "
            "first; a study holds one paper."
        ),
        input_model=inputs.FetchPaperInput,
        effects=("writes_study", "network"),
        read_only=False,
        open_world=True,
    ),
    ToolContract(
        name="get_section",
        title="Read a section",
        stage="Intake",
        summary="Returns one section's text with file and line numbers",
        description=(
            "Read part of the paper with its original file and line numbers: a section, a table, figure, "
            "equation or algorithm, a LaTeX label, the abstract, a PDF page, a line range, or 'index' for "
            "the full outline. Use the shown file:line when recording claims and method map entries."
        ),
        input_model=inputs.GetSectionInput,
        effects=("reads_study",),
        read_only=True,
    ),
    ToolContract(
        name="get_page_image",
        title="Look at a page",
        stage="Intake",
        summary="Returns one page as an image for equations and figures",
        description=(
            "Render one page of the paper PDF as a PNG image, for equations, figures and tables that text "
            "extraction loses. Saved under paper/pages/."
        ),
        input_model=inputs.GetPageImageInput,
        effects=("reads_study", "writes_study"),
        read_only=True,
        returns_image=True,
    ),
    ToolContract(
        name="add_claim",
        title="Record a claim",
        stage="Claims",
        summary="Records each claim: metric, value, where it appears, and the success bar",
        description=(
            "Record one number the paper claims, before writing any code (rule 5): the metric, the value as "
            "printed, where it appears and the success bar. The value is checked against the paper text. "
            "Claims recorded after code exists are flagged in the report."
        ),
        input_model=inputs.AddClaimInput,
        effects=("writes_study",),
        read_only=False,
    ),
    ToolContract(
        name="list_claims",
        title="List claims",
        stage="Claims",
        summary="Lists recorded claims with their current verdicts",
        description="List every recorded claim with its success bar and current verdict.",
        input_model=inputs.ListClaimsInput,
        effects=("reads_study",),
        read_only=True,
    ),
    ToolContract(
        name="add_guess",
        title="Record a guess",
        stage="Plan",
        summary="Records a missing detail, the choice made, and why",
        description=(
            "Record a detail the paper left out, the choice made and why (rule 2: never change the method to "
            "make a run succeed; record a guess instead). Every guess appears in the report."
        ),
        input_model=inputs.AddGuessInput,
        effects=("writes_study",),
        read_only=False,
    ),
    ToolContract(
        name="map_method",
        title="Map method to code",
        stage="Plan",
        summary="Links an equation or algorithm step to a file and line",
        description=(
            "Link an equation or algorithm step in the paper to the file and line in code/ that implements "
            "it. The file's hash is recorded so the report flags mappings whose code changed later."
        ),
        input_model=inputs.MapMethodInput,
        effects=("reads_study", "writes_study"),
        read_only=False,
    ),
    ToolContract(
        name="create_env",
        title="Create environment",
        stage="Build",
        summary="Makes a uv environment or Docker image and writes the lock file",
        description=(
            "Build a pinned environment for the study's code: a uv virtual environment (fast, not a "
            "sandbox) or a Docker image (isolated). Writes the lock file and records its hash. Requires "
            "recorded claims (rule 5)."
        ),
        input_model=inputs.CreateEnvInput,
        effects=("writes_study", "network", "runs_code"),
        read_only=False,
        open_world=True,
    ),
    ToolContract(
        name="run",
        title="Run a command",
        stage="Run",
        summary="Runs one command locally; saves output, exit code, time, memory and files",
        description=(
            "Run one command in code/ with the named environment. Saves stdout and stderr, exit code, time, "
            "peak memory, seed, the code commit and the hash of every file the run writes. Only scope "
            "'full' can count toward a verdict (rule 4). Use wait=false and run_status for long runs."
        ),
        input_model=inputs.RunInput,
        effects=("writes_study", "runs_code", "network"),
        read_only=False,
        open_world=True,
    ),
    ToolContract(
        name="run_status",
        title="Run status",
        stage="Run",
        summary="Reports a run's status and the tail of its output",
        description="Report a run's status, exit code and the last lines of its output; optionally wait for it to finish.",
        input_model=inputs.RunStatusInput,
        effects=("reads_study",),
        read_only=True,
    ),
    ToolContract(
        name="run_remote",
        title="Run on a GPU cloud",
        stage="Run",
        summary="Same on Modal, RunPod or Hugging Face Jobs, after a cost estimate and approval",
        description=(
            "Run one command on a paid GPU provider (Modal today; RunPod and Hugging Face Jobs planned). "
            "Returns a cost estimate and refuses until the person approves it (rule 6) and the estimate "
            "fits the budget a person set with `irp budget`. The time limit equals the estimated hours."
        ),
        input_model=inputs.RunRemoteInput,
        effects=("writes_study", "runs_code", "network", "paid_compute"),
        read_only=False,
        open_world=True,
    ),
    ToolContract(
        name="extract_metrics",
        title="Extract metrics",
        stage="Measure",
        summary="Pulls numbers from logs and result files, with file and line",
        description=(
            "Pull numbers from a completed run's stdout, stderr or the files it wrote, by key, regex, JSON "
            "pointer or CSV column. Each measurement keeps its file, line and file hash. Numbers from any "
            "other source are refused (rule 1)."
        ),
        input_model=inputs.ExtractMetricsInput,
        effects=("reads_study", "writes_study"),
        read_only=False,
    ),
    ToolContract(
        name="compare",
        title="Compare and judge",
        stage="Judge",
        summary="Puts claim and measurement side by side and gives one of four verdicts",
        description=(
            "Put a claim beside its measurements and record one of four verdicts: reproduced, close, not "
            "reproduced, or could not run. Measurements must come from full-scope runs that exited 0; "
            "'could not run' needs the blocking error (rule 3)."
        ),
        input_model=inputs.CompareInput,
        effects=("reads_study", "writes_study"),
        read_only=False,
    ),
    ToolContract(
        name="add_note",
        title="Record a note",
        stage="Judge",
        summary="Records a limitation, deviation, unchecked item or author contact",
        description="Record a limitation, a forced deviation from the paper, something not checked, or an author contact.",
        input_model=inputs.AddNoteInput,
        effects=("writes_study",),
        read_only=False,
    ),
    ToolContract(
        name="report",
        title="Write the report",
        stage="Report",
        summary="Writes report.md and report.json from the log",
        description=(
            "Write report.md and report.json from the evidence log only: claim table, verdicts, guesses, "
            "method map and provenance. Refuses until every claim has a verdict with evidence (the "
            "completion gate) unless draft=true."
        ),
        input_model=inputs.ReportInput,
        effects=("reads_study", "writes_study"),
        read_only=False,
    ),
    ToolContract(
        name="verify",
        title="Verify the evidence",
        stage="Report",
        summary="Rechecks the hash chain and every recorded file hash",
        description="Recheck the evidence log's hash chain and the hash of every recorded file; reports each problem.",
        input_model=inputs.VerifyInput,
        effects=("reads_study",),
        read_only=True,
    ),
    ToolContract(
        name="study_status",
        title="Study status",
        stage="Report",
        summary="Shows what is recorded and what still blocks the report",
        description=(
            "Show the study at a glance: paper, claims and verdicts, guesses, environments, runs, and what "
            "still blocks a final report. Use it to resume work."
        ),
        input_model=inputs.StudyStatusInput,
        effects=("reads_study",),
        read_only=True,
    ),
)

BY_NAME: dict[str, ToolContract] = {contract.name: contract for contract in CATALOG}
