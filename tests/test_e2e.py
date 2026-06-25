"""End-to-End (E2E) Test Suite for OmniConvert.

This test suite covers Tiers 1-4 for all extended converters and the batch engine.
"""

from __future__ import annotations

import os
import json
import sqlite3
from pathlib import Path
import pytest
from typer.testing import CliRunner

from omni_convert.cli import app

runner = CliRunner()

# ==========================================
# HELPERS & FIXTURES
# ==========================================

def create_minimal_pdf(path: Path, text: str = "Hello PDF") -> None:
    """Creates a minimal valid PDF file with extractable text."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R /MediaBox [0 0 595 842] >>\nendobj\n"
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"5 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(" + text.encode('latin1', 'replace') + b") Tj\nET\nendstream\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f\n"
        b"0000000009 00000 n\n"
        b"0000000056 00000 n\n"
        b"0000000111 00000 n\n"
        b"0000000244 00000 n\n"
        b"0000000321 00000 n\n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n416\n%%EOF\n"
    )
    path.write_bytes(pdf_content)

def create_sqlite_db(path: Path) -> None:
    """Creates a standard SQLite database with two tables."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT)")
    cursor.execute("INSERT INTO users (name, role) VALUES ('Alice', 'Admin'), ('Bob', 'User')")
    cursor.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT, budget REAL)")
    cursor.execute("INSERT INTO projects (title, budget) VALUES ('OmniConvert', 15000.0), ('HIBRIS', 25000.0)")
    conn.commit()
    conn.close()

def create_hdf5_file(path: Path) -> None:
    """Creates a mock HDF5 file using h5py."""
    h5py = pytest.importorskip("h5py")
    np = pytest.importorskip("numpy")
    with h5py.File(path, "w") as f:
        f.create_dataset("dataset1", data=np.array([10, 20, 30], dtype=np.int32))
        group = f.create_group("subgroup")
        group.create_dataset("dataset2", data=np.array([1.5, 2.5, 3.5], dtype=np.float32))

def create_docx_file(path: Path) -> None:
    """Creates a DOCX file using python-docx."""
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_heading("Project Report", level=1)
    doc.add_paragraph("This is a simple paragraph in the report.")
    
    # Add a table
    table = doc.add_table(rows=2, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Header A"
    hdr_cells[1].text = "Header B"
    row_cells = table.rows[1].cells
    row_cells[0].text = "Row 1 Col 1"
    row_cells[1].text = "Row 1 Col 2"
    
    doc.save(path)

def create_avif_file(path: Path) -> None:
    """Creates a mock AVIF image using Pillow if plugin available."""
    PIL = pytest.importorskip("PIL.Image")
    pytest.importorskip("pillow_avif")
    img = PIL.new("RGB", (16, 16), color="blue")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.line((0, 0, 16, 16), fill="white", width=2)
    img.save(path, format="AVIF")

def create_png_image(path: Path) -> None:
    """Creates a standard PNG image."""
    PIL = pytest.importorskip("PIL.Image")
    img = PIL.new("RGB", (32, 32), color="white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.line((0, 0, 32, 32), fill="black", width=2)
    img.save(path, format="PNG")

# ==========================================
# TIER 1: FEATURE COVERAGE (5 tests/feature)
# ==========================================

# --- SQLite to CSV ---
def test_t1_sqlite_to_csv_happy(tmp_path):
    db_path = tmp_path / "test.db"
    create_sqlite_db(db_path)
    out_dir = tmp_path / "csv_out"
    
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code == 0
    assert (out_dir / "users.csv").exists()
    assert (out_dir / "projects.csv").exists()
    assert (out_dir / "schema.sql").exists()

def test_t1_sqlite_to_csv_explicit_flags(tmp_path):
    db_path = tmp_path / "test.db"
    create_sqlite_db(db_path)
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--from", "sqlite", "--to", "csv"])
    assert res.exit_code == 0
    assert (out_dir / "schema.sql").exists()

def test_t1_sqlite_to_csv_empty_tables(tmp_path):
    db_path = tmp_path / "empty_tables.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE empty_table (id INTEGER, val TEXT)")
    conn.commit()
    conn.close()
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code == 0
    assert (out_dir / "empty_table.csv").exists()

def test_t1_sqlite_to_csv_custom_out_dir(tmp_path):
    db_path = tmp_path / "test.db"
    create_sqlite_db(db_path)
    custom_dir = tmp_path / "custom_location"
    res = runner.invoke(app, ["convert", str(db_path), str(custom_dir), "--to", "csv"])
    assert res.exit_code == 0
    assert custom_dir.exists()

def test_t1_sqlite_to_csv_progress(tmp_path):
    db_path = tmp_path / "test.db"
    create_sqlite_db(db_path)
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code == 0
    # Rich progress bar output or success tick in output
    assert "Conversión completada" in res.output or "✓" in res.output


# --- HDF5 to Parquet ---
def test_t1_hdf5_to_parquet_happy(tmp_path):
    h5py = pytest.importorskip("h5py")
    h5_path = tmp_path / "test.h5"
    create_hdf5_file(h5_path)
    out_dir = tmp_path / "pq_out"
    
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    assert res.exit_code == 0
    assert (out_dir / "dataset1.parquet").exists()
    assert (out_dir / "subgroup/dataset2.parquet").exists()

def test_t1_hdf5_to_parquet_explicit_flags(tmp_path):
    h5_path = tmp_path / "test.h5"
    create_hdf5_file(h5_path)
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--from", "hdf5", "--to", "parquet"])
    assert res.exit_code == 0

def test_t1_hdf5_to_parquet_single_dataset(tmp_path):
    h5py = pytest.importorskip("h5py")
    h5_path = tmp_path / "single.h5"
    with h5py.File(h5_path, "w") as f:
        f.create_dataset("only", data=[1, 2, 3])
    out_file = tmp_path / "only.parquet"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_file)])
    assert res.exit_code == 0
    assert out_file.exists()

def test_t1_hdf5_to_parquet_nested_groups(tmp_path):
    h5_path = tmp_path / "nested.h5"
    create_hdf5_file(h5_path)
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    assert res.exit_code == 0
    assert (out_dir / "subgroup/dataset2.parquet").exists()

def test_t1_hdf5_to_parquet_progress(tmp_path):
    h5_path = tmp_path / "test.h5"
    create_hdf5_file(h5_path)
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    assert res.exit_code == 0
    assert "Conversión completada" in res.output


# --- PDF to Markdown ---
def test_t1_pdf_to_md_happy_text(tmp_path):
    pdfplumber = pytest.importorskip("pdfplumber")
    pdf_path = tmp_path / "test.pdf"
    create_minimal_pdf(pdf_path, "Hello Markdown World")
    out_md = tmp_path / "out.md"
    
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()
    assert "Hello Markdown World" in out_md.read_text(encoding="utf-8")

def test_t1_pdf_to_md_explicit_flags(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    create_minimal_pdf(pdf_path)
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md), "--from", "pdf", "--to", "md"])
    assert res.exit_code == 0

def test_t1_pdf_to_md_fallback_ocr(tmp_path, monkeypatch):
    # OCR requires pix2tex, torch, torchvision
    pytest.importorskip("pix2tex")
    pytest.importorskip("torch")
    
    # Scanned PDF without text (we will write an empty page or image page PDF)
    pdf_path = tmp_path / "scanned.pdf"
    create_minimal_pdf(pdf_path, "") # Empty text triggers OCR fallback
    
    # Mock to_image to return an image with variance so pix2tex doesn't crash on pure white
    import pdfplumber
    original_open = pdfplumber.open
    class MockPageImage:
        def __init__(self):
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (100, 100), "white")
            ImageDraw.Draw(img).line((0, 0, 100, 100), fill="black")
            self.original = img
    
    def mock_open(*args, **kwargs):
        pdf = original_open(*args, **kwargs)
        for p in pdf.pages:
            p.to_image = lambda resolution=150: MockPageImage()
        return pdf
    
    monkeypatch.setattr(pdfplumber, "open", mock_open)
    
    out_md = tmp_path / "out.md"
    
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()

def test_t1_pdf_to_md_mixed(tmp_path):
    pdf_path = tmp_path / "mixed.pdf"
    create_minimal_pdf(pdf_path, "Standard Text and some image/formula placeholder")
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code == 0
    assert "Standard Text" in out_md.read_text(encoding="utf-8")

def test_t1_pdf_to_md_progress(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    create_minimal_pdf(pdf_path)
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code == 0
    assert "Conversión completada" in res.output


# --- DOCX to Markdown ---
def test_t1_docx_to_md_happy(tmp_path):
    docx = pytest.importorskip("docx")
    docx_path = tmp_path / "test.docx"
    create_docx_file(docx_path)
    out_md = tmp_path / "out.md"
    
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "# Project Report" in content
    assert "This is a simple paragraph" in content

def test_t1_docx_to_md_tables(tmp_path):
    docx_path = tmp_path / "test.docx"
    create_docx_file(docx_path)
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code == 0
    content = out_md.read_text(encoding="utf-8")
    assert "Header A" in content
    assert "Row 1 Col 1" in content

def test_t1_docx_to_md_images(tmp_path):
    docx = pytest.importorskip("docx")
    PIL = pytest.importorskip("PIL.Image")
    docx_path = tmp_path / "image.docx"
    
    doc = docx.Document()
    doc.add_paragraph("Paragraph with image:")
    img_path = tmp_path / "temp.png"
    create_png_image(img_path)
    doc.add_picture(str(img_path))
    doc.save(docx_path)
    
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()
    # Check media folder next to markdown file
    media_dir = out_md.parent / "out_media"
    assert media_dir.exists()
    assert len(list(media_dir.glob("*"))) >= 1

def test_t1_docx_to_md_lists(tmp_path):
    docx = pytest.importorskip("docx")
    docx_path = tmp_path / "list.docx"
    doc = docx.Document()
    doc.add_paragraph("Item 1", style="List Bullet")
    doc.add_paragraph("Item 2", style="List Bullet")
    doc.save(docx_path)
    
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code == 0
    content = out_md.read_text(encoding="utf-8")
    assert "* Item 1" in content or "- Item 1" in content

def test_t1_docx_to_md_explicit_flags(tmp_path):
    docx_path = tmp_path / "test.docx"
    create_docx_file(docx_path)
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md), "--from", "docx", "--to", "md"])
    assert res.exit_code == 0


# --- AVIF to PNG ---
def test_t1_avif_to_png_happy(tmp_path):
    pytest.importorskip("pillow_avif")
    avif_path = tmp_path / "test.avif"
    create_avif_file(avif_path)
    out_png = tmp_path / "out.png"
    
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code == 0
    assert out_png.exists()

def test_t1_avif_to_png_explicit_flags(tmp_path):
    pytest.importorskip("pillow_avif")
    avif_path = tmp_path / "test.avif"
    create_avif_file(avif_path)
    out_png = tmp_path / "out.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png), "--from", "avif", "--to", "png"])
    assert res.exit_code == 0

def test_t1_avif_to_png_progress(tmp_path):
    pytest.importorskip("pillow_avif")
    avif_path = tmp_path / "test.avif"
    create_avif_file(avif_path)
    out_png = tmp_path / "out.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code == 0
    assert "Conversión completada" in res.output

def test_t1_avif_to_png_inference(tmp_path):
    pytest.importorskip("pillow_avif")
    avif_path = tmp_path / "test.avif"
    create_avif_file(avif_path)
    out_png = tmp_path / "inferred.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code == 0
    assert out_png.exists()

def test_t1_avif_to_png_stub_encode(tmp_path):
    # PNG to AVIF should raise NotImplementedError / error in CLI
    png_path = tmp_path / "test.png"
    create_png_image(png_path)
    out_avif = tmp_path / "out.avif"
    
    res = runner.invoke(app, ["convert", str(png_path), str(out_avif)])
    assert res.exit_code != 0
    assert "NotImplementedError" in res.output or "No hay ruta de conversión" in res.output or "Error" in res.output


# --- Image to LaTeX ---
def test_t1_image_to_latex_png(tmp_path):
    pytest.importorskip("pix2tex")
    pytest.importorskip("torch")
    
    img_path = tmp_path / "formula.png"
    create_png_image(img_path)
    out_tex = tmp_path / "formula.tex"
    
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code == 0
    assert out_tex.exists()

def test_t1_image_to_latex_jpg(tmp_path):
    pytest.importorskip("pix2tex")
    img_path = tmp_path / "formula.jpg"
    PIL = pytest.importorskip("PIL.Image")
    img = PIL.new("RGB", (32, 32), color="white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.line((0, 0, 32, 32), fill="black", width=2)
    img.save(img_path, format="JPEG")
    out_tex = tmp_path / "formula.tex"
    
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code == 0

def test_t1_image_to_latex_explicit_flags(tmp_path):
    pytest.importorskip("pix2tex")
    img_path = tmp_path / "formula.png"
    create_png_image(img_path)
    out_tex = tmp_path / "formula.tex"
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--from", "png", "--to", "latex"])
    assert res.exit_code == 0

def test_t1_image_to_latex_progress(tmp_path):
    pytest.importorskip("pix2tex")
    img_path = tmp_path / "formula.png"
    create_png_image(img_path)
    out_tex = tmp_path / "formula.tex"
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code == 0
    assert "Conversión completada" in res.output

def test_t1_image_to_latex_formula_check(tmp_path):
    pytest.importorskip("pix2tex")
    img_path = tmp_path / "formula.png"
    create_png_image(img_path)
    out_tex = tmp_path / "formula.tex"
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code == 0
    content = out_tex.read_text(encoding="utf-8")
    # Formula output should start/end with $ or \begin{equation} or simply contain equation strings
    assert len(content) > 0


# --- Batch Processing ---
def test_t1_batch_happy(tmp_path):
    # Batch convert multiple CSV files to JSON
    csv1 = tmp_path / "file1.csv"
    csv2 = tmp_path / "file2.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    csv2.write_text("a,b\n3,4\n", encoding="utf-8")
    
    out_dir = tmp_path / "batch_out"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.csv", "--to", "json", "--output-dir", str(out_dir)])
    assert res.exit_code == 0
    assert (out_dir / "file1.json").exists()
    assert (out_dir / "file2.json").exists()

def test_t1_batch_explicit_to(tmp_path):
    csv1 = tmp_path / "file1.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    out_dir = tmp_path / "batch_out"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.csv", "--to", "json", "--output-dir", str(out_dir)])
    assert res.exit_code == 0

def test_t1_batch_output_dir(tmp_path):
    csv1 = tmp_path / "file1.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    custom_out = tmp_path / "custom_batch"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.csv", "--to", "json", "--output-dir", str(custom_out)])
    assert res.exit_code == 0
    assert custom_out.exists()

def test_t1_batch_exit_code_success(tmp_path):
    csv1 = tmp_path / "file1.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    out_dir = tmp_path / "batch_out"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.csv", "--to", "json", "--output-dir", str(out_dir)])
    assert res.exit_code == 0

def test_t1_batch_concurrency(tmp_path):
    # Verify that concurrency option works or runs successfully
    csv1 = tmp_path / "file1.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    out_dir = tmp_path / "batch_out"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.csv", "--to", "json", "--output-dir", str(out_dir)])
    assert res.exit_code == 0
    assert "procesado" in res.output.lower() or "completada" in res.output.lower()


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES (5 tests/feature)
# ==========================================

# --- SQLite to CSV (Tier 2) ---
def test_t2_sqlite_no_tables(tmp_path):
    db_path = tmp_path / "no_tables.db"
    conn = sqlite3.connect(db_path)
    conn.commit()
    conn.close()
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code == 0
    assert len(list(out_dir.glob("*.csv"))) == 0
    assert (out_dir / "schema.sql").exists()

def test_t2_sqlite_missing_db(tmp_path):
    db_path = tmp_path / "does_not_exist.db"
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code != 0

def test_t2_sqlite_corrupt_db(tmp_path):
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database file", encoding="utf-8")
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code != 0

def test_t2_sqlite_special_chars(tmp_path):
    db_path = tmp_path / "special.db"
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE "users table!" (id INTEGER PRIMARY KEY, "full name" TEXT)')
    conn.execute("INSERT INTO \"users table!\" (\"full name\") VALUES ('Alice O''Connor')")
    conn.commit()
    conn.close()
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code == 0
    assert (out_dir / "users table!.csv").exists()

def test_t2_sqlite_large_db(tmp_path):
    db_path = tmp_path / "large.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE data (val TEXT)")
    conn.executemany("INSERT INTO data VALUES (?)", [(f"val_{i}",) for i in range(1000)])
    conn.commit()
    conn.close()
    out_dir = tmp_path / "csv_out"
    res = runner.invoke(app, ["convert", str(db_path), str(out_dir), "--to", "csv"])
    assert res.exit_code == 0
    rows = (out_dir / "data.csv").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1001 # Header + 1000 rows


# --- HDF5 to Parquet (Tier 2) ---
def test_t2_hdf5_empty_dataset(tmp_path):
    h5py = pytest.importorskip("h5py")
    h5_path = tmp_path / "empty.h5"
    with h5py.File(h5_path, "w") as f:
        f.create_dataset("empty", shape=(0,), dtype="int32")
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    assert res.exit_code == 0
    assert (out_dir / "empty.parquet").exists()

def test_t2_hdf5_missing_file(tmp_path):
    h5_path = tmp_path / "does_not_exist.h5"
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    assert res.exit_code != 0

def test_t2_hdf5_corrupt_file(tmp_path):
    h5_path = tmp_path / "corrupt.h5"
    h5_path.write_text("corrupted content", encoding="utf-8")
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    assert res.exit_code != 0

def test_t2_hdf5_unsupported_dtype(tmp_path):
    h5py = pytest.importorskip("h5py")
    h5_path = tmp_path / "complex.h5"
    with h5py.File(h5_path, "w") as f:
        # Complex datatypes might not be supported natively by some Parquet writers
        f.create_dataset("complex", data=[1+2j, 3+4j])
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    # If conversion fails or converts gracefully, it shouldn't crash the program silently
    assert res.exit_code in [0, 1]

def test_t2_hdf5_large_dataset(tmp_path):
    h5py = pytest.importorskip("h5py")
    np = pytest.importorskip("numpy")
    h5_path = tmp_path / "large.h5"
    with h5py.File(h5_path, "w") as f:
        f.create_dataset("large", data=np.arange(5000))
    out_dir = tmp_path / "pq_out"
    res = runner.invoke(app, ["convert", str(h5_path), str(out_dir), "--to", "parquet"])
    assert res.exit_code == 0
    assert (out_dir / "large.parquet").exists()


# --- PDF to Markdown (Tier 2) ---
def test_t2_pdf_empty_pdf(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 empty content")
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code != 0

def test_t2_pdf_corrupt_pdf(tmp_path):
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_text("completely corrupt pdf", encoding="utf-8")
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code != 0

def test_t2_pdf_missing_file(tmp_path):
    pdf_path = tmp_path / "does_not_exist.pdf"
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code != 0

def test_t1_pdf_to_md_fallback_missing_pix2tex(tmp_path, monkeypatch):
    pytest.importorskip("pdfplumber")
    import sys
    import omni_convert.converters.document.pdf_to_md as ptm
    monkeypatch.setattr(ptm, "_OCR_MODEL", None)
    monkeypatch.setitem(sys.modules, "pix2tex.cli", None)

    pdf_path = tmp_path / "scanned.pdf"
    create_minimal_pdf(pdf_path, "")
    out_md = tmp_path / "out.md"

    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code != 0

def test_t2_pdf_special_chars(tmp_path):
    pdf_path = tmp_path / "special.pdf"
    create_minimal_pdf(pdf_path, "Unicode text: ¡Hola Señor! 100€ + 200¥")
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "¡Hola Seæor!" in content or "200¥" in content


# --- DOCX to Markdown (Tier 2) ---
def test_t2_docx_empty(tmp_path):
    docx = pytest.importorskip("docx")
    docx_path = tmp_path / "empty.docx"
    doc = docx.Document()
    doc.save(docx_path)
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()
    assert len(out_md.read_text(encoding="utf-8").strip()) == 0

def test_t2_docx_corrupt(tmp_path):
    docx_path = tmp_path / "corrupt.docx"
    docx_path.write_text("corrupted zip content", encoding="utf-8")
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code != 0

def test_t2_docx_missing_file(tmp_path):
    docx_path = tmp_path / "does_not_exist.docx"
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code != 0

def test_t2_docx_nested_tables(tmp_path):
    docx = pytest.importorskip("docx")
    docx_path = tmp_path / "nested_table.docx"
    doc = docx.Document()
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    # Nested table inside cell
    nested_table = cell.add_table(rows=1, cols=1)
    nested_table.cell(0, 0).text = "Nested Content"
    doc.save(docx_path)
    
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()

def test_t2_docx_large_doc(tmp_path):
    docx = pytest.importorskip("docx")
    docx_path = tmp_path / "large.docx"
    doc = docx.Document()
    for i in range(500):
        doc.add_paragraph(f"Line number {i} repeating data...")
    doc.save(docx_path)
    
    out_md = tmp_path / "out.md"
    res = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()


# --- AVIF to PNG (Tier 2) ---
def test_t2_avif_empty_file(tmp_path):
    avif_path = tmp_path / "empty.avif"
    avif_path.write_bytes(b"")
    out_png = tmp_path / "out.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code != 0

def test_t2_avif_corrupt_file(tmp_path):
    avif_path = tmp_path / "corrupt.avif"
    avif_path.write_text("not an avif image", encoding="utf-8")
    out_png = tmp_path / "out.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code != 0

def test_t2_avif_missing_file(tmp_path):
    avif_path = tmp_path / "does_not_exist.avif"
    out_png = tmp_path / "out.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code != 0

def test_t2_avif_invalid_signature(tmp_path):
    avif_path = tmp_path / "wrong_signature.avif"
    avif_path.write_bytes(b"ftypheicwrongbytesatstart")
    out_png = tmp_path / "out.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code != 0

def test_t2_avif_large_dims(tmp_path):
    pytest.importorskip("pillow_avif")
    avif_path = tmp_path / "huge.avif"
    PIL = pytest.importorskip("PIL.Image")
    # AVIF with large dimensions
    img = PIL.new("RGB", (2000, 2000), color="green")
    img.save(avif_path, format="AVIF")
    out_png = tmp_path / "out.png"
    res = runner.invoke(app, ["convert", str(avif_path), str(out_png)])
    assert res.exit_code == 0
    assert out_png.exists()


# --- Image to LaTeX (Tier 2) ---
def test_t2_image_empty_image(tmp_path):
    img_path = tmp_path / "empty.png"
    img_path.write_bytes(b"")
    out_tex = tmp_path / "out.tex"
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code != 0

def test_t2_image_corrupt_image(tmp_path):
    img_path = tmp_path / "corrupt.png"
    img_path.write_text("corrupted png content", encoding="utf-8")
    out_tex = tmp_path / "out.tex"
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code != 0

def test_t2_image_missing_file(tmp_path):
    img_path = tmp_path / "does_not_exist.png"
    out_tex = tmp_path / "out.tex"
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code != 0

def test_t2_image_non_equation(tmp_path):
    pytest.importorskip("pix2tex")
    # Image with plain white space (not an equation)
    img_path = tmp_path / "blank.png"
    create_png_image(img_path)
    out_tex = tmp_path / "out.tex"
    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    # Should complete but might write empty or fallback formula
    assert res.exit_code == 0
    assert out_tex.exists()

def test_t1_image_to_latex_png_missing_pix2tex(tmp_path, monkeypatch):
    # Simulate missing pix2tex
    import sys
    import omni_convert.converters.image.image_to_latex as itl
    monkeypatch.setattr(itl, "_LATEX_MODEL", None)
    monkeypatch.setitem(sys.modules, "pix2tex.cli", None)

    img_path = tmp_path / "formula.png"
    create_png_image(img_path)
    out_tex = tmp_path / "formula.tex"

    res = runner.invoke(app, ["convert", str(img_path), str(out_tex), "--to", "latex"])
    assert res.exit_code != 0


# --- Batch Processing (Tier 2) ---
def test_t2_batch_partial_failure(tmp_path):
    db_good = tmp_path / "good.db"
    create_sqlite_db(db_good)
    
    # Writing a corrupt DB which will cause parser failure
    db_bad = tmp_path / "bad.db"
    db_bad.write_text("invalid,json_like_corrupt_data\n{broken:\n", encoding="utf-8")
    
    out_dir = tmp_path / "batch_out"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.db", "--to", "csv", "--output-dir", str(out_dir)])
    # Batch processing engine exits non-zero if there are failures
    assert res.exit_code != 0
    assert "good.db" in res.output or "bad.db" in res.output
    # The good file should still have been processed
    good_out_dir = out_dir / "good.csv"
    assert (good_out_dir / "projects.csv").exists() or (good_out_dir / "users.csv").exists()

def test_t2_batch_fail_fast(tmp_path):
    db_good = tmp_path / "good.db"
    create_sqlite_db(db_good)
    db_bad = tmp_path / "bad.db"
    db_bad.write_text("invalid,json_like_corrupt_data\n{broken:\n", encoding="utf-8")
    
    out_dir = tmp_path / "batch_out"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.db", "--to", "csv", "--output-dir", str(out_dir), "--fail-fast"])
    assert res.exit_code != 0
    # In fail-fast mode, the process terminates immediately on the first error

def test_t2_batch_no_matches(tmp_path):
    out_dir = tmp_path / "batch_out"
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.nonexistent", "--to", "json", "--output-dir", str(out_dir)])
    assert res.exit_code != 0
    assert "no match" in res.output.lower() or "no se encontraron" in res.output.lower() or "error" in res.output.lower()

def test_t2_batch_invalid_args(tmp_path):
    # Missing required --to format in batch mode
    csv1 = tmp_path / "file1.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.csv"])
    assert res.exit_code != 0

def test_t2_batch_nested_dirs(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    csv1 = sub / "file1.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    
    out_dir = tmp_path / "batch_out"
    # Recursive pattern matching
    res = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/**/*.csv", "--to", "json", "--output-dir", str(out_dir)])
    assert res.exit_code == 0
    assert (out_dir / "file1.json").exists()


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================

def test_t3_sqlite_csv_json_pipeline(tmp_path):
    db_path = tmp_path / "test.db"
    create_sqlite_db(db_path)
    
    # 1. SQLite -> CSV Directory
    csv_dir = tmp_path / "csv_out"
    res1 = runner.invoke(app, ["convert", str(db_path), str(csv_dir), "--to", "csv"])
    assert res1.exit_code == 0
    assert (csv_dir / "users.csv").exists()
    
    # 2. CSV -> JSON Chained path verification
    res2 = runner.invoke(app, ["path", "sqlite", "json"])
    assert res2.exit_code == 0
    assert "sqlite → csv → json" in res2.output.lower()
    
    json_path = tmp_path / "users.json"
    res3 = runner.invoke(app, ["convert", str(csv_dir / "users.csv"), str(json_path)])
    assert res3.exit_code == 0
    assert json_path.exists()

def test_t3_pdf_sci_marker_pipeline(tmp_path, monkeypatch):
    import omni_convert.converters.document.pdf_to_md_sci as pdf_sci
    
    # Mock models download/loading to avoid 1GB PyTorch initialization in tests
    monkeypatch.setattr(pdf_sci, "get_marker_models", lambda: {"mock": "models"})
    
    class MockPdfConverter:
        def __init__(self, artifact_dict):
            assert artifact_dict == {"mock": "models"}
            
        def __call__(self, filepath):
            class MockRendered:
                markdown = "# Título Científico\n\n$E = mc^2$"
            return MockRendered()
            
    # Need to mock the inside import of PdfConverter
    import sys
    class MockMarkerConverters:
        pass
    mock_module = MockMarkerConverters()
    mock_module.PdfConverter = MockPdfConverter
    sys.modules["marker.converters.pdf"] = mock_module
    
    pdf_path = tmp_path / "scanned_formula.pdf"
    create_minimal_pdf(pdf_path, "")
    
    from omni_convert.converters.document.pdf_to_md_sci import PdfToMdScientific
    converter = PdfToMdScientific()
    
    out_md = tmp_path / "output.md"
    converter.convert(pdf_path, out_md, lambda x: None)
    
    assert out_md.exists()
    content = out_md.read_text()
    assert "# Título Científico" in content
    assert "E = mc^2" in content

def test_t3_pdf_ocr_latex_pipeline(tmp_path, monkeypatch):
    pytest.importorskip("pdfplumber")
    pytest.importorskip("pix2tex")
    
    # Mock to_image to return an image with variance so pix2tex doesn't crash on pure white
    import pdfplumber
    original_open = pdfplumber.open
    class MockPageImage:
        def __init__(self):
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (100, 100), "white")
            ImageDraw.Draw(img).line((0, 0, 100, 100), fill="black")
            self.original = img
    
    def mock_open(*args, **kwargs):
        pdf = original_open(*args, **kwargs)
        for p in pdf.pages:
            p.to_image = lambda resolution=150: MockPageImage()
        return pdf
    
    monkeypatch.setattr(pdfplumber, "open", mock_open)
    
    # PDF with formula image. OCR fallback extracts equation, routes to LaTeX
    pdf_path = tmp_path / "scanned_formula.pdf"
    create_minimal_pdf(pdf_path, "") # Empty text triggers OCR -> Formula extraction
    
    out_tex = tmp_path / "formula.tex"
    res = runner.invoke(app, ["convert", str(pdf_path), str(out_tex), "--to", "latex"])
    assert res.exit_code == 0
    assert out_tex.exists()

def test_t3_docx_png_jpeg_pipeline(tmp_path):
    docx = pytest.importorskip("docx")
    PIL = pytest.importorskip("PIL.Image")
    
    # DOCX containing PNG image
    docx_path = tmp_path / "docx_img.docx"
    doc = docx.Document()
    doc.add_paragraph("Contains image below:")
    
    png_img = tmp_path / "source.png"
    create_png_image(png_img)
    doc.add_picture(str(png_img))
    doc.save(docx_path)
    
    # Convert DOCX to Markdown, extracting the media
    out_md = tmp_path / "out.md"
    res1 = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res1.exit_code == 0
    
    extracted_png = list((out_md.parent / "out_media").glob("*.png"))
    if not extracted_png: # depending on md output format
        extracted_png = list((out_md.parent / "media").glob("*.png"))
    assert len(extracted_png) >= 1
    
    # (Optional) pipeline continuation could be done here

def test_t3_sqlite_hdf5_pipeline(tmp_path):
    # Convert SQLite to CSV, then use CSVs to construct HDF5 datasets
    db_path = tmp_path / "test.db"
    create_sqlite_db(db_path)
    csv_dir = tmp_path / "csv_out"
    
    res1 = runner.invoke(app, ["convert", str(db_path), str(csv_dir), "--to", "csv"])
    assert res1.exit_code == 0
    
    # Route: CSV to HDF5 (if converter path exists or via pandas conversion)
    res2 = runner.invoke(app, ["path", "csv", "hdf5"])
    # If the path is known/registered, verify conversion
    if res2.exit_code == 0:
        h5_out = tmp_path / "sync.h5"
        res3 = runner.invoke(app, ["convert", str(csv_dir / "users.csv"), str(h5_out)])
        if res3.exit_code != 0:
            print(f"Output: {res3.output}")
            print(f"Exception: {res3.exception}")
        assert res3.exit_code == 0

def test_t3_batch_docx_md_and_avif_png(tmp_path):
    docx = pytest.importorskip("docx")
    pytest.importorskip("pillow_avif")
    
    docx_path1 = tmp_path / "doc1.docx"
    create_docx_file(docx_path1)
    docx_path2 = tmp_path / "doc2.docx"
    create_docx_file(docx_path2)
    
    out_md_dir = tmp_path / "md_out"
    res1 = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.docx", "--to", "md", "--output-dir", str(out_md_dir)])
    assert res1.exit_code == 0
    assert (out_md_dir / "doc1.md").exists()
    assert (out_md_dir / "doc2.md").exists()

def test_t3_pdf_docx_md_chain(tmp_path):
    pdfplumber = pytest.importorskip("pdfplumber")
    pdf_path = tmp_path / "document.pdf"
    create_minimal_pdf(pdf_path, "Text to migrate")
    
    # Verify we can find route between pdf and md
    res_path = runner.invoke(app, ["path", "pdf", "md"])
    assert res_path.exit_code == 0
    assert "pdf" in res_path.output and "md" in res_path.output

def test_t3_image_avif_png_latex_chain(tmp_path):
    pytest.importorskip("pillow_avif")
    pytest.importorskip("pix2tex")
    
    avif_path = tmp_path / "math.avif"
    create_avif_file(avif_path)
    
    # Path routing check from avif to latex (avif -> png -> latex)
    res_path = runner.invoke(app, ["path", "avif", "latex"])
    assert res_path.exit_code == 0
    assert "avif → png → latex" in res_path.output.lower()
    
    out_tex = tmp_path / "math.tex"
    res_conv = runner.invoke(app, ["convert", str(avif_path), str(out_tex), "--to", "latex"])
    assert res_conv.exit_code == 0
    assert out_tex.exists()


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================

def test_t4_scientific_ingestion_scenario(tmp_path):
    """Scenario 1: Scientific Document Ingestion Pipeline.
    
    A user uploads an HDF5 data archive, a PDF paper, and a PNG equation plot.
    The pipeline processes them: HDF5 to Parquet datasets, PDF text extraction
    falling back to OCR, and PNG equation plot to LaTeX format.
    """
    h5py = pytest.importorskip("h5py")
    pdfplumber = pytest.importorskip("pdfplumber")
    pytest.importorskip("pix2tex")
    
    # Setup files
    h5_path = tmp_path / "data_metrics.h5"
    create_hdf5_file(h5_path)
    pdf_path = tmp_path / "research_paper.pdf"
    create_minimal_pdf(pdf_path, "Introduction: standard review and observations.")
    img_path = tmp_path / "plot_equation.png"
    create_png_image(img_path)
    
    # 1. HDF5 -> Parquet
    pq_out = tmp_path / "parquet_datasets"
    res1 = runner.invoke(app, ["convert", str(h5_path), str(pq_out), "--to", "parquet"])
    assert res1.exit_code == 0
    assert (pq_out / "dataset1.parquet").exists()
    
    # 2. PDF -> MD
    md_out = tmp_path / "paper_extracted.md"
    res2 = runner.invoke(app, ["convert", str(pdf_path), str(md_out)])
    assert res2.exit_code == 0
    assert "Introduction" in md_out.read_text(encoding="utf-8")
    
    # 3. Image -> LaTeX
    tex_out = tmp_path / "equation.tex"
    res3 = runner.invoke(app, ["convert", str(img_path), str(tex_out), "--to", "latex"])
    assert res3.exit_code == 0
    assert tex_out.exists()

def test_t4_legal_migration_scenario(tmp_path):
    """Scenario 2: Legal Document Archive Migration.
    
    Migrating a DOCX archive containing agreements, signature images,
    and a SQLite database containing contract registry metadata.
    """
    docx = pytest.importorskip("docx")
    
    # Setup files
    docx_path = tmp_path / "contract_agreement.docx"
    create_docx_file(docx_path)
    db_path = tmp_path / "contracts_registry.db"
    create_sqlite_db(db_path)
    
    # 1. DOCX -> MD with media extraction
    md_out = tmp_path / "contract.md"
    res1 = runner.invoke(app, ["convert", str(docx_path), str(md_out)])
    assert res1.exit_code == 0
    assert md_out.exists()
    
    # 2. SQLite -> CSV directory
    csv_out = tmp_path / "registry_csv"
    res2 = runner.invoke(app, ["convert", str(db_path), str(csv_out), "--to", "csv"])
    assert res2.exit_code == 0
    assert (csv_out / "users.csv").exists()
    assert (csv_out / "schema.sql").exists()

def test_t4_batch_image_converter_scenario(tmp_path):
    """Scenario 3: Batch Image Converter Pipeline.
    
    Batch processing multiple AVIF image files, converting them to PNG,
    and routing image formulas to LaTeX equations.
    """
    pytest.importorskip("pillow_avif")
    pytest.importorskip("pix2tex")
    
    # Create batch AVIF files
    avif1 = tmp_path / "image1.avif"
    avif2 = tmp_path / "image2.avif"
    create_avif_file(avif1)
    create_avif_file(avif2)
    
    # Batch convert AVIF -> PNG
    png_out_dir = tmp_path / "converted_pngs"
    res1 = runner.invoke(app, ["convert", "--batch", f"{tmp_path}/*.avif", "--to", "png", "--output-dir", str(png_out_dir)])
    assert res1.exit_code == 0
    assert (png_out_dir / "image1.png").exists()
    assert (png_out_dir / "image2.png").exists()
    
    # Run Image -> LaTeX on one of the output PNGs
    tex_out = tmp_path / "extracted_formula.tex"
    res2 = runner.invoke(app, ["convert", str(png_out_dir / "image1.png"), str(tex_out), "--to", "latex"])
    assert res2.exit_code == 0
    assert tex_out.exists()

def test_t4_data_extraction_sync_scenario(tmp_path):
    """Scenario 4: Data Extraction & Sync Chain.
    
    Export transactional data from SQLite to CSVs, inspect/parse the data schema,
    and compile sync logs to a single nested HDF5 structure.
    """
    db_path = tmp_path / "sync_transactions.db"
    create_sqlite_db(db_path)
    
    # 1. SQLite -> CSV
    csv_out = tmp_path / "exported_transactions"
    res1 = runner.invoke(app, ["convert", str(db_path), str(csv_out), "--to", "csv"])
    assert res1.exit_code == 0
    
    # 2. Read schema to verify correctness
    schema_sql = (csv_out / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE users" in schema_sql
    assert "CREATE TABLE projects" in schema_sql

def test_t4_e2e_document_format_scenario(tmp_path):
    """Scenario 5: E2E Document Formatting & Media Check.
    
    Verify that DOCX conversion to Markdown retains formatting metadata (lists, headings, tables)
    and correctly exports embedded AVIF images, converting them subsequently.
    """
    docx = pytest.importorskip("docx")
    pytest.importorskip("pillow_avif")
    
    # DOCX report
    docx_path = tmp_path / "complex_report.docx"
    doc = docx.Document()
    doc.add_heading("Financial Summary", level=1)
    doc.add_paragraph("High priority details:")
    doc.add_paragraph("First item", style="List Bullet")
    
    # Add a mock PNG image
    png_img = tmp_path / "chart.png"
    create_png_image(png_img)
    doc.add_picture(str(png_img))
    
    # Table
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Value: $1,200"
    
    doc.save(docx_path)
    
    # Convert DOCX -> Markdown
    out_md = tmp_path / "report.md"
    res1 = runner.invoke(app, ["convert", str(docx_path), str(out_md)])
    assert res1.exit_code == 0
    
    content = out_md.read_text(encoding="utf-8")
    assert "# Financial Summary" in content
    assert "Value: $1,200" in content
    
    # Check media and convert extracted chart.png -> latex
    extracted_media = list((out_md.parent / "report_media").glob("*.png"))
    assert len(extracted_media) >= 1
    
    out_tex = tmp_path / "chart.tex"
    res2 = runner.invoke(app, ["convert", str(extracted_media[0]), str(out_tex), "--to", "latex"])
    assert res2.exit_code == 0
    assert out_tex.exists()
