import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from docx import Document
import nfra_site
from nfra_attachments import tables


class AttachmentTests(unittest.TestCase):
    def test_docx_uses_same_fields_as_html(self):
        document = Document()
        table = document.add_table(rows=3, cols=2)
        for cells, values in zip(table.rows, [('被处罚当事人', '甲银行'), ('主要违法违规事实', '违规放贷'), ('行政处罚决定', '罚款10万元')]):
            for cell, value in zip(cells.cells, values):
                cell.text = value
        output = BytesIO()
        document.save(output)
        extracted = nfra_site.table_rows(tables(output.getvalue(), '.docx'))
        html = '<table><tr><td>被处罚当事人</td><td>甲银行</td></tr><tr><td>主要违法违规事实</td><td>违规放贷</td></tr><tr><td>行政处罚决定</td><td>罚款10万元</td></tr></table>'
        soup = nfra_site.BeautifulSoup(html, 'lxml')
        self.assertEqual(extracted, nfra_site.table_rows([nfra_site.grid(soup.table)]))
        self.assertEqual(extracted[0]['party_name'], '甲银行')

    @patch.object(nfra_site, 'attachment_tables')
    @patch.object(nfra_site, 'request')
    @patch.object(nfra_site, 'get')
    def test_pdf_is_backup_for_same_word_attachment(self, get, download, extract):
        get.return_value = {'docClob': '<a href="/DOC/1.doc">Word</a><a href="/PDF/1.pdf">PDF</a>'}
        download.return_value = Mock(content=b'file')
        extract.side_effect = [ValueError('bad Word'), [[['被处罚当事人', '处罚决定'], ['甲银行', '罚款10万元']]]]
        import tempfile
        with tempfile.TemporaryDirectory() as directory, patch.object(nfra_site, 'cache', Path(directory)):
            rows, issue = nfra_site.parse('1', (4113, {'publishDate': '2026-11-12'}), True)
        self.assertIsNone(issue)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['doc_id'], '1')
        self.assertEqual(download.call_count, 2)

    @patch.object(nfra_site, 'attachment_tables')
    @patch.object(nfra_site, 'request')
    @patch.object(nfra_site, 'get')
    def test_successful_word_does_not_duplicate_pdf(self, get, download, extract):
        get.return_value = {'docClob': '<a href="/DOC/1.doc">Word</a><a href="/PDF/1.pdf">PDF</a>'}
        download.return_value = Mock(content=b'file')
        extract.return_value = [[['当事人', '处罚决定'], ['甲银行', '罚款1万元']]]
        import tempfile
        with tempfile.TemporaryDirectory() as directory, patch.object(nfra_site, 'cache', Path(directory)):
            rows, issue = nfra_site.parse('1', (4113, {'publishDate': '2026-11-12'}), True)
        self.assertIsNone(issue)
        self.assertEqual(len(rows), 1)
        self.assertEqual(download.call_count, 1)

    def test_pdf_continuation_rows(self):
        rows = nfra_site.table_rows([[['当事人', '处罚决定'], ['甲银行', '罚款1万元'], ['当事人', '处罚决定'], ['乙银行', '罚款2万元']]])
        self.assertEqual(len(rows), 2)
