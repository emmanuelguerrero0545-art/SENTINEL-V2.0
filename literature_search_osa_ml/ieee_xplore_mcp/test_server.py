"""Pruebas sin red: se sustituye la llamada HTTP por respuestas simuladas.
Ejecutar: python3 -m unittest test_server -v"""
import asyncio, io, json, os, unittest, urllib.error
from unittest import mock

import server

SAMPLE = {"total_records": 3, "articles": [{
    "article_number": "8952673", "title": "Deep sleep apnea detection", "doi": "10.1109/JBHI.2019.2951346",
    "authors": {"authors": [{"full_name": "A. Uno"}, {"full_name": "B. Dos"}]}, "publication_title": "IEEE JBHI",
    "publication_year": 2020, "content_type": "Journals", "access_type": "OPEN_ACCESS", "citing_paper_count": 12,
    "html_url": "https://ieeexplore.ieee.org/document/8952673/", "pdf_url": "https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=8952673",
    "abstract": "x" * 900, "index_terms": {"ieee_terms": {"terms": ["Sleep apnea"]}, "author_terms": {"terms": ["ECG", "Sleep apnea"]}}}]}


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"IEEE_API_KEY": "k"}); self.env.start()
    def tearDown(self):
        self.env.stop()

    def _search(self, **kw):
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(json.dumps(SAMPLE).encode())) as u:
            out = json.loads(server.ieee_search_articles(**kw))
        return out, u.call_args[0][0]

    def test_search_formats_and_paginates(self):
        out, url = self._search(query='"sleep apnea" AND ECG', limit=1, offset=0, start_year=2019, open_access_only=True, sort_by="newest")
        self.assertEqual((out["total"], out["count"], out["has_more"], out["next_offset"]), (3, 1, True, 1))
        a = out["articles"][0]
        self.assertEqual(a["authors"], ["A. Uno", "B. Dos"])
        self.assertTrue(a["open_access"]); self.assertEqual(a["keywords"], ["ECG", "Sleep apnea"])
        self.assertEqual(a["doi_url"], "https://doi.org/10.1109/JBHI.2019.2951346")
        self.assertLessEqual(len(a["abstract"]), server.ABSTRACT_PREVIEW + 1)
        for part in ("apikey=k", "start_record=1", "max_records=1", "start_year=2019", "open_access=True", "sort_order=desc", "format=json"):
            self.assertIn(part, url)

    def test_offset_maps_to_start_record_and_last_page(self):
        out, url = self._search(title="apnea", limit=1, offset=2)
        self.assertIn("start_record=3", url); self.assertFalse(out["has_more"]); self.assertIsNone(out["next_offset"])

    def test_requires_a_criterion(self):
        self.assertIn("error", json.loads(server.ieee_search_articles()))

    def test_missing_key_is_actionable(self):
        with mock.patch.dict(os.environ, {"IEEE_API_KEY": ""}):
            self.assertIn("IEEE_API_KEY", json.loads(server.ieee_search_articles(query="x"))["error"])

    def test_http_403_is_explained(self):
        err = urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b"<h1>Developer Inactive</h1>"))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            self.assertIn("Developer Inactive", json.loads(server.ieee_search_articles(query="x"))["error"])

    def test_get_article_by_doi_and_validation(self):
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(json.dumps(SAMPLE).encode())) as u:
            a = json.loads(server.ieee_get_article(doi="https://doi.org/10.1109/JBHI.2019.2951346"))
        self.assertEqual(len(a["abstract"]), 900); self.assertIn("doi=10.1109%2FJBHI.2019.2951346", u.call_args[0][0])
        self.assertIn("error", json.loads(server.ieee_get_article()))
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(b'{"total_records":0}')):
            self.assertIn("error", json.loads(server.ieee_get_article(article_number="1")))

    def test_tools_are_registered(self):
        tools = server.mcp.list_tools()
        if asyncio.iscoroutine(tools): tools = asyncio.run(tools)
        names = {t.name for t in tools}
        self.assertEqual(names, {"ieee_search_articles", "ieee_get_article"})


if __name__ == "__main__":
    unittest.main()
