"""Upload adapters for arkham.build exports."""
import json
import mimetypes
import os
import re
import shutil
from io import BytesIO
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, unquote, urlsplit

import requests

from shoggoth.arkham_build.data import ExportedProject
from shoggoth.cloud import client
from shoggoth.files import default_export_folder
from shoggoth.i18n import tr
from shoggoth.project import Project


def export_folder(project: Project) -> Path:
    return default_export_folder(project) / "arkham-build"


class UploadAdapter(Protocol):
    @property
    def images_enabled(self) -> bool: ...

    def export_file(self, filename: str) -> Path: ...

    def image_url(self, filename: str, *, source: Path | None = None) -> str: ...

    def publish(self, path: Path, data: ExportedProject) -> None: ...


def _write_json(path: Path, data: ExportedProject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _export_file(project: Project, filename: str) -> Path:
    destination = export_folder(project) / project.id / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


class ManualUploadAdapter:
    def __init__(self, project: Project, url_prefix: str):
        self.project = project
        self.url_prefix = url_prefix.strip().rstrip("/")

    @property
    def images_enabled(self) -> bool:
        return bool(self.url_prefix)

    def export_file(self, filename: str) -> Path:
        return _export_file(self.project, filename)

    def image_url(self, filename: str, *, source: Path | None = None) -> str:
        if source is not None:
            destination = self.export_file(filename)
            if source.resolve() != destination.resolve():
                shutil.copyfile(source, destination)
        return f"{self.url_prefix}/{self.project.id}/{quote(filename)}"

    def publish(self, path: Path, data: ExportedProject) -> None:
        _write_json(path, data)


class CelaenoUploadAdapter:
    images_enabled = True

    def __init__(self, project: Project, base_url: str, token: str, *, report, check_cancelled):
        self.project = project
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.report = report
        self.check_cancelled = check_cancelled

        check_cancelled()
        report(tr("MSG_PUBLISH_ENSURING_PROJECT"))

        self.project_id, self.public_url = client.ensure_artifact_target(
            self.base_url, token, f"arkham-build/{project.id}",
            project.name or "arkham-build",
        )

        if not self.public_url:
            raise client.PublishError(tr("AB_CLOUD_NO_PUBLIC_URL"))
        self.public_url = self.public_url.rstrip("/")

    def _upload(self, kind: str, name: str, path: Path) -> str:
        self.check_cancelled()
        self.report(tr("MSG_PUBLISH_UPLOADING").format(name=name))
        result = client.upload_file(
            self.base_url, self.token, self.project_id, kind, name, path
        )
        return f"{self.public_url}/download?path=/{quote(result['path'], safe='/')}"

    def export_file(self, filename: str) -> Path:
        return _export_file(self.project, filename)

    def image_url(self, filename: str, *, source: Path | None = None) -> str:
        return self._upload(
            "images", Path(filename).name, source if source is not None else self.export_file(filename),
        )

    def publish(self, path: Path, data: ExportedProject) -> None:
        _write_json(path, data)
        url = self._upload("data", path.name, path)
        # The first response gives the exact public path for this export.
        data["meta"]["url"] = url
        _write_json(path, data)
        self._upload("data", path.name, path)


class CloudinaryUploadAdapter:
    images_enabled = True

    def __init__(self, project: Project, credentials: str, *, report, check_cancelled):
        try:
            url = urlsplit(credentials.strip())
            cloud = url.hostname or ""
            if url.scheme != "cloudinary" or not re.fullmatch(r"[a-z0-9_-]+", cloud):
                raise ValueError
            if not url.username or not url.password:
                raise ValueError
        except ValueError:
            raise ValueError("Set CLOUDINARY_URL to your Cloudinary API environment variable and restart Shoggoth.") from None
        self.project = project
        self.cloud = cloud
        self._auth = (unquote(url.username), unquote(url.password))
        self._namespace = f"shoggoth/arkham-build/{project.id}"
        self.report = report
        self.check_cancelled = check_cancelled

    def export_file(self, filename: str) -> Path:
        return _export_file(self.project, filename)

    def _upload(self, resource_type, filename, public_id, content):
        self.check_cancelled()
        self.report(tr("MSG_PUBLISH_UPLOADING").format(name=filename))
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        try:
            response = requests.post(
                f"https://api.cloudinary.com/v1_1/{self.cloud}/{resource_type}/upload",
                auth=self._auth, files={"file": (filename, content, mime_type)},
                data={"public_id": public_id, "overwrite": "true", "invalidate": "true"},
                timeout=(10, 90), allow_redirects=False,
            )
        except requests.RequestException:
            raise client.PublishError(f"Cloudinary could not upload {filename}. Check the connection and retry.") from None
        if not 200 <= response.status_code < 300:
            raise client.PublishError(f"Cloudinary rejected {filename} (HTTP {response.status_code}).")
        try:
            secure_url = response.json()["secure_url"]
            if not isinstance(secure_url, str) or not secure_url.startswith("https://"):
                raise ValueError
        except (TypeError, KeyError, ValueError):
            raise client.PublishError(f"Cloudinary returned no public HTTPS URL for {filename}.") from None
        return secure_url

    def image_url(self, filename: str, *, source: Path | None = None) -> str:
        path = source if source is not None else self.export_file(filename)
        public_id = f"{self._namespace}/{Path(filename).with_suffix('').as_posix()}"
        with path.open("rb") as content:
            return self._upload("image", Path(filename).name, public_id, content)

    def publish(self, path: Path, data: ExportedProject) -> None:
        public_id = f"{self._namespace}/{path.name}"
        # Use a stable delivery URL so existing arkham.build imports can refresh the export.
        data["meta"]["url"] = f"https://res.cloudinary.com/{self.cloud}/raw/upload/v1/{quote(public_id, safe='/')}"
        with BytesIO(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")) as content:
            self._upload("raw", path.name, public_id, content)
        _write_json(path, data)


def create_upload_adapter(
    project, settings, *, config=None, report=None, check_cancelled=None,
) -> UploadAdapter:
    adapter = settings.get("upload_adapter", "manual")
    if adapter == "manual":
        return ManualUploadAdapter(project, settings.get("url_prefix") or "")
    if adapter == "cloudinary":
        return CloudinaryUploadAdapter(
            project, os.environ.get("CLOUDINARY_URL", ""),
            report=report or _noop, check_cancelled=check_cancelled or _noop,
        )
    if adapter != "celaeno":
        raise ValueError(f"Unknown arkham.build upload adapter: {adapter}")

    if config is None:
        raise client.PublishError(tr("PUBLISH_NOT_LOGGED_IN"))

    token = config.get("Shoggoth", "publish_token", "")
    if not token or not config.getboolean("Shoggoth", "publish_has_access", False):
        raise client.PublishError(tr("PUBLISH_NOT_LOGGED_IN"))

    base_url = config.get("Shoggoth", "publish_base_url", "").strip()
    if not base_url:
        raise client.PublishError(tr("AB_CLOUD_NO_BASE_URL"))

    return CelaenoUploadAdapter(
        project, base_url, token,
        report=report or _noop, check_cancelled=check_cancelled or _noop,
    )


def _noop(*args: object) -> None:
    pass
