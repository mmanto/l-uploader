import shutil
import tempfile
import zipfile
from pathlib import Path

PAGES_ROOT = Path("/srv/pages")

WEB_EXTS = {
    ".html", ".htm", ".css", ".js", ".json", ".svg",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".xml",
    ".txt", ".webmanifest",
}


class InvalidZipError(Exception):
    pass


def page_dir(slug: str) -> Path:
    return PAGES_ROOT / slug


def extract_zip_to_page(slug: str, zip_bytes: bytes) -> int:
    """Extrae zip_bytes a page_dir(slug), reemplazando el contenido web existente.

    Devuelve la cantidad de archivos publicados. Levanta InvalidZipError en caso
    de zip corrupto o con rutas no permitidas (path traversal).
    """
    target_dir = page_dir(slug)

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "upload.zip"
        zip_path.write_bytes(zip_bytes)

        try:
            with zipfile.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    if name.startswith("/") or ".." in name:
                        raise InvalidZipError("El zip contiene rutas no permitidas")
                extract_dir = Path(tmp) / "extracted"
                zf.extractall(extract_dir)
        except zipfile.BadZipFile as exc:
            raise InvalidZipError("Archivo zip inválido") from exc

        entries = list(extract_dir.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            source = entries[0]
        else:
            source = extract_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        for existing in target_dir.rglob("*"):
            if existing.is_file() and existing.suffix.lower() in WEB_EXTS:
                existing.unlink()

        shutil.copytree(source, target_dir, dirs_exist_ok=True)

    return sum(1 for f in target_dir.rglob("*") if f.is_file())


def delete_page_dir(slug: str) -> None:
    target_dir = page_dir(slug)
    if target_dir.exists():
        shutil.rmtree(target_dir)
