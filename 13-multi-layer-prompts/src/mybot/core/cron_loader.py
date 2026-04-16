"""core/cron_loader.py -- Discovers and loads CRON.md job definitions."""
from __future__ import annotations
import re
from pathlib import Path
import yaml
from pydantic import BaseModel


class CronDef(BaseModel):
    """A scheduled cron job definition."""
    id: str
    name: str
    description: str = ""
    agent: str = "my-bot"
    schedule: str         # cron expression e.g. "0 9 * * *"
    prompt: str           # message sent to the agent when the job fires
    one_off: bool = False # if True, delete after first run


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _parse_cron_file(path: Path) -> CronDef | None:
    try:
        text = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return None
        meta = yaml.safe_load(m.group(1)) or {}
        return CronDef(**{k: v for k, v in meta.items() if k in CronDef.model_fields})
    except Exception:
        return None


class CronLoader:
    """Discovers cron job definitions from CRON.md files."""

    def __init__(self, crons_dir: Path) -> None:
        self.crons_dir = crons_dir

    def discover_crons(self) -> list[CronDef]:
        if not self.crons_dir.exists():
            return []
        jobs = []
        for path in sorted(self.crons_dir.rglob("CRON.md")):
            job = _parse_cron_file(path)
            if job is not None:
                jobs.append(job)
        return jobs

    def delete_cron(self, cron_id: str) -> bool:
        """Delete a cron job directory by id. Returns True on success."""
        for path in self.crons_dir.rglob("CRON.md"):
            job = _parse_cron_file(path)
            if job and job.id == cron_id:
                import shutil
                shutil.rmtree(path.parent)
                return True
        return False
