from pathlib import Path
from urllib.parse import quote

from shoggoth.files import default_export_folder
from shoggoth.project import Project


def export_folder(project: Project) -> Path:
    return default_export_folder(project) / "arkham-build"


def export_file(project: Project, path: str) -> Path:
    destination = export_folder(project) / project.id / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def export_url(url_prefix: str, project: Project, path: str) -> str:
    return f"{url_prefix}/{project.id}/{quote(path)}"
