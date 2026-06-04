from __future__ import annotations

import io
import zipfile

import pytest

from interview_app.cv.document_parser import (
    extract_text_from_cv_bytes,
    validate_cv_upload,
)
from interview_app.cv.exceptions import CVFileValidationError


def test_validate_unsupported_extension() -> None:
    with pytest.raises(CVFileValidationError, match="Unsupported"):
        validate_cv_upload(filename="x.txt", data=b"hello", max_bytes=1024)


def test_validate_empty_file() -> None:
    with pytest.raises(CVFileValidationError, match="empty"):
        validate_cv_upload(filename="a.pdf", data=b"", max_bytes=1024)


def test_validate_file_too_large() -> None:
    with pytest.raises(CVFileValidationError, match="too large"):
        validate_cv_upload(filename="a.pdf", data=b"%PDF-1.4" + b"x" * 100, max_bytes=10)


def test_validate_pdf_magic_ok() -> None:
    ext = validate_cv_upload(
        filename="cv.pdf", data=b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n", max_bytes=1024
    )
    assert ext == ".pdf"


def test_validate_docx_magic_ok() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document></w:document>")
    data = buf.getvalue()
    ext = validate_cv_upload(filename="cv.docx", data=data, max_bytes=1024)
    assert ext == ".docx"


def test_validate_pdf_wrong_magic() -> None:
    with pytest.raises(CVFileValidationError, match="valid PDF"):
        validate_cv_upload(filename="x.pdf", data=b"NOTPDF", max_bytes=1024)


def test_extract_text_pdf_empty_pages_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Image-only or empty PDFs yield no text; caller shows a user-facing message."""
    import sys
    from types import ModuleType

    from interview_app.cv import document_parser as dp

    class FakePage:
        def extract_text(self) -> str:
            return ""

    class FakeReader:
        def __init__(self, _buf: object) -> None:
            self.pages = [FakePage(), FakePage()]

    fake_mod = ModuleType("pypdf")
    fake_mod.PdfReader = FakeReader  # type: ignore[assignment]
    monkeypatch.setitem(sys.modules, "pypdf", fake_mod)

    out = dp.extract_text_pdf(b"%PDF-1.4 fake")
    assert out == ""


def test_extract_from_pdf_uses_extractor(monkeypatch: pytest.MonkeyPatch) -> None:
    from interview_app.cv import document_parser as dp

    monkeypatch.setattr(
        dp, "extract_text_pdf", lambda d: "Python developer with 5 years experience."
    )
    out = extract_text_from_cv_bytes(
        filename="a.pdf",
        data=b"%PDF-1.4\n",
        max_bytes=1024,
    )
    assert "developer" in out
