"""Extract attachment tables; business field interpretation lives in nfra_site."""
from io import BytesIO
from pathlib import Path
import os
import shutil
import subprocess
import tempfile


def tables(content, suffix):
    if suffix == '.pdf':
        import pdfplumber
        with pdfplumber.open(BytesIO(content)) as document:
            # Keep consecutive page tables together for repeated/continued headers.
            yield [row for page in document.pages for table in page.extract_tables()
                   for row in table]
        return
    if suffix == '.docx':
        from docx import Document
        for table in Document(BytesIO(content)).tables:
            yield [[cell.text for cell in row.cells] for row in table.rows]
        return
    if suffix == '.doc':
        executable = os.environ.get('SOFFICE_PATH') or shutil.which('soffice')
        if not executable:
            raise RuntimeError('DOC parsing requires LibreOffice (soffice)')
        with tempfile.TemporaryDirectory(prefix='nfra-doc-') as directory:
            root = Path(directory)
            source = root / 'notice.doc'
            source.write_bytes(content)
            subprocess.run([executable, '-env:UserInstallation=' + (root/'profile').as_uri(),
                            '--headless', '--convert-to', 'docx', '--outdir', directory,
                            str(source)], check=True, timeout=90, capture_output=True)
            converted = root / 'notice.docx'
            if not converted.exists():
                raise ValueError('LibreOffice produced no DOCX')
            yield from tables(converted.read_bytes(), '.docx')
        return
    raise ValueError(f'Unsupported attachment format: {suffix}')
