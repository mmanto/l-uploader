import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path

PAGES_ROOT = Path("/srv/pages")
PROPOSALS_ROOT = Path("/srv/proposals")

INDEX_NAME = "index.html"

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


def proposal_dir(token: str) -> Path:
    return PROPOSALS_ROOT / token


def _reset_dir(target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)


def _count_files(target_dir: Path) -> int:
    return sum(1 for f in target_dir.rglob("*") if f.is_file())


@contextmanager
def _zip_source(zip_bytes: bytes):
    """Extrae el zip en un tmp y entrega el directorio que contiene el sitio.

    Levanta InvalidZipError en caso de zip corrupto o con rutas no permitidas
    (path traversal). El directorio entregado solo vive dentro del contexto.
    """
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
            yield entries[0]
        else:
            yield extract_dir


def extract_zip_to_page(slug: str, zip_bytes: bytes) -> int:
    """Extrae zip_bytes a page_dir(slug), reemplazando el contenido web existente.

    Devuelve la cantidad de archivos publicados. Levanta InvalidZipError en caso
    de zip corrupto o con rutas no permitidas (path traversal).
    """
    target_dir = page_dir(slug)

    with _zip_source(zip_bytes) as source:
        target_dir.mkdir(parents=True, exist_ok=True)
        for existing in target_dir.rglob("*"):
            if existing.is_file() and existing.suffix.lower() in WEB_EXTS:
                existing.unlink()

        shutil.copytree(source, target_dir, dirs_exist_ok=True)

    return _count_files(target_dir)


def publish_proposal_html(token: str, html_bytes: bytes) -> int:
    """Publica un único archivo .html como portada de la propuesta."""
    target_dir = proposal_dir(token)
    _reset_dir(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / INDEX_NAME).write_bytes(html_bytes)

    return _count_files(target_dir)


def publish_proposal_zip(token: str, zip_bytes: bytes) -> int:
    """Publica un zip (html + css + assets) en proposal_dir(token), reemplazando lo anterior.

    El zip debe traer un index.html en la raíz (o dentro de una única carpeta de
    primer nivel). Si no lo trae pero tiene un único .html, ese archivo se usa
    como portada.
    """
    target_dir = proposal_dir(token)

    with _zip_source(zip_bytes) as source:
        if not (source / INDEX_NAME).is_file():
            htmls = sorted(p for p in source.glob("*.htm*") if p.is_file())
            if len(htmls) != 1:
                raise InvalidZipError("El zip debe incluir un index.html")
            shutil.copyfile(htmls[0], source / INDEX_NAME)

        _reset_dir(target_dir)
        shutil.copytree(source, target_dir, dirs_exist_ok=True)

    return _count_files(target_dir)


def delete_page_dir(slug: str) -> None:
    _reset_dir(page_dir(slug))


def delete_proposal_dir(token: str) -> None:
    _reset_dir(proposal_dir(token))
