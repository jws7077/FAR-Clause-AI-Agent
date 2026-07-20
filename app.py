from far_clause_ai_agent.render import render_markdown

from fastapi.concurrency import run_in_threadpool

from datetime import datetime

import json

from far_clause_ai_agent.main import (
    _load_document,
    _build_report,
)


from far_clause_ai_agent.config import load_config
from far_clause_ai_agent.llm_client import LLMClient

from pathlib import Path
import shutil

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="templates")
LATEST_OUTPUT = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )

@app.post("/analyze")
async def analyze(
    request: Request,
    solicitation: UploadFile = File(...),
    proposal: UploadFile = File(...),
):
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)

    solicitation_path = upload_dir / solicitation.filename
    proposal_path = upload_dir / proposal.filename

    with solicitation_path.open("wb") as buffer:
        shutil.copyfileobj(solicitation.file, buffer)

    with proposal_path.open("wb") as buffer:
        shutil.copyfileobj(proposal.file, buffer)

    solicitation_doc = _load_document(solicitation_path)
    proposal_doc = _load_document(proposal_path)

    config = load_config()
    client = LLMClient(config)

    report = await run_in_threadpool(
    _build_report,
    [solicitation_doc],
    [proposal_doc],
    config,
    client,
)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("output") / timestamp
    output_dir.mkdir(exist_ok=True)

    global LATEST_OUTPUT
    LATEST_OUTPUT = output_dir

    (output_dir / "report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)

    (output_dir / "report.md").write_text(
    render_markdown(report),
    encoding="utf-8",
)
    return templates.TemplateResponse(
    request=request,
    name="result.html",
    context={
    "clauses": len(report["rfp_clause_index"]),
    "obligations": len(report["obligations"]),
    "coverage": len(report["coverage_results"]),
    "flags": len(report["flags"]),
    "coverage_percent": round(
        (
            len(report["coverage_results"])
            / max(len(report["obligations"]), 1)
        ) * 100
    ),
    "report": report,

    "top_flags": report["flags"][:10],
    "coverage_results": report["coverage_results"][:10],
    "obligations_list": report["obligations"][:10],
    "clauses_list": report["rfp_clause_index"][:10],
},
)
@app.get("/download/report.md")
async def download_markdown():
    if LATEST_OUTPUT is None:
        return {"error": "No report has been generated yet."}

    return FileResponse(
        path=LATEST_OUTPUT / "report.md",
        filename="report.md",
        media_type="text/markdown",
    )


@app.get("/download/report.json")
async def download_json():
    if LATEST_OUTPUT is None:
        return {"error": "No report has been generated yet."}

    return FileResponse(
        path=LATEST_OUTPUT / "report.json",
        filename="report.json",
        media_type="application/json",
    )