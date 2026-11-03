import hashlib
import re
import shutil
from html import escape

from shoggoth.arkham_build.output import export_file, export_url
from shoggoth.files import overlay_dir
from shoggoth.renderer.richtext.tags import parse_tag_attributes

_IMAGE_TAG_PATTERN = re.compile(r"<image(?=\s|>)", re.IGNORECASE)


class ImageAssetExporter:
    def __init__(self, project, url_prefix):
        self.project = project
        self.url_prefix = url_prefix
        self._urls_by_path = {}

    def export(self, source):
        if not self.url_prefix or not source:
            return None

        path = self.project.find_file(source)
        if path is None:
            path = overlay_dir / source

        if not path.is_file():
            return None

        path = path.resolve()
        if path in self._urls_by_path:
            return self._urls_by_path[path]

        with path.open("rb") as image:
            digest = hashlib.file_digest(image, "sha256").hexdigest()

        filename = f"assets/{digest}{path.suffix}"
        destination = export_file(self.project, filename)
        if not destination.exists():
            shutil.copyfile(path, destination)

        url = export_url(self.url_prefix, self.project, filename)
        self._urls_by_path[path] = url
        return url

    def map_tag(self, tag):
        if _IMAGE_TAG_PATTERN.match(tag) is None:
            return None

        attributes = {
            key.lower(): value for key, value in parse_tag_attributes(tag).items()
        }

        url = self.export(attributes.get("src"))
        if url is None:
            return ""

        return (
            f'<img src="{escape(url, quote=True)}" '
            'style="height:1em;vertical-align:middle">'
        )
