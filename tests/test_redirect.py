"""Unit tests for redirect.py.
"""
import copy
from unittest.mock import patch

from oauth_dropins.webutil.testutil import requests_response

from app import app, cache
import common
from models import MagicKey
from .test_webmention import REPOST_HTML, REPOST_AS2
from . import testutil

client = app.test_client()


class RedirectTest(testutil.TestCase):

    def setUp(self):
        super(RedirectTest, self).setUp()
        app.testing = True
        cache.clear()
        MagicKey.get_or_create('foo.com')

    def test_redirect(self):
        got = client.get('/r/https://foo.com/bar?baz=baj&biff')
        self.assertEqual(301, got.status_code)
        self.assertEqual('https://foo.com/bar?baz=baj&biff=', got.headers['Location'])

    def test_redirect_scheme_missing(self):
        got = client.get('/r/foo.com')
        self.assertEqual(400, got.status_code)

    def test_redirect_url_missing(self):
        got = client.get('/r/')
        self.assertEqual(404, got.status_code)

    def test_redirect_no_magic_key_for_domain(self):
        got = client.get('/r/http://bar.com/baz')
        self.assertEqual(404, got.status_code)

    def test_redirect_single_slash(self):
        got = client.get('/r/https:/foo.com/bar')
        self.assertEqual(301, got.status_code)
        self.assertEqual('https://foo.com/bar', got.headers['Location'])

    def test_as2(self):
        self._test_as2(common.CONTENT_TYPE_AS2)

    def test_as2_ld(self):
        self._test_as2(common.CONTENT_TYPE_AS2_LD)

    @patch('requests.get')
    def _test_as2(self, accept, mock_get):
        """Currently mainly for Pixelfed.

        https://github.com/snarfed/bridgy-fed/issues/39
        """
        as2 = copy.deepcopy(REPOST_AS2)
        as2.update({
            'cc': [common.AS2_PUBLIC_AUDIENCE],
            'object': 'http://orig/post',
        })

        mock_get.return_value = requests_response(
            REPOST_HTML, content_type=common.CONTENT_TYPE_HTML)

        got = client.get('/r/https://foo.com/bar', headers={'Accept': accept})

        args, kwargs = mock_get.call_args
        self.assertEqual(('https://foo.com/bar',), args)

        self.assertEqual(200, got.status_code)
        self.assertEqual(as2, got.json)
