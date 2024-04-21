"""Unit tests for ids.py."""
from unittest.mock import patch

from activitypub import ActivityPub
from atproto import ATProto
from flask_app import app
from ids import translate_handle, translate_object_id, translate_user_id
from models import Target
from .testutil import Fake, TestCase
from web import Web


class IdsTest(TestCase):
    def test_translate_user_id(self):
        Web(id='user.com',
            copies=[Target(uri='did:plc:123', protocol='atproto')]).put()
        ActivityPub(id='https://inst/user',
                    copies=[Target(uri='did:plc:456', protocol='atproto')]).put()
        Fake(id='fake:user',
             copies=[Target(uri='did:plc:789', protocol='atproto')]).put()

        # DID doc and ATProto, used to resolve handle in bsky.app URL
        did = self.store_object(id='did:plc:123', raw={
            'id': 'did:plc:123',
            'alsoKnownAs': ['at://user.com'],
        })
        ATProto(id='did:plc:123', obj_key=did.key).put()

        for from_, id, to, expected in [
            (ActivityPub, 'https://inst/user', ActivityPub, 'https://inst/user'),
            (ActivityPub, 'https://inst/user', ATProto, 'did:plc:456'),
            (ActivityPub, 'https://inst/user', Fake, 'fake:u:https://inst/user'),
            (ActivityPub, 'https://inst/user', Web, 'https://inst/user'),
            (ActivityPub, 'https://bsky.app/profile/user.com', ATProto, 'did:plc:123'),
            (ActivityPub, 'https://bsky.app/profile/did:plc:123',
             ATProto, 'did:plc:123'),
            (ATProto, 'did:plc:456', ATProto, 'did:plc:456'),
            # copies
            (ATProto, 'did:plc:123', Web, 'user.com'),
            (ATProto, 'did:plc:456', ActivityPub, 'https://inst/user'),
            (ATProto, 'did:plc:789', Fake, 'fake:user'),
            # no copies
            (ATProto, 'did:plc:x', Web, 'https://bsky.brid.gy/web/did:plc:x'),
            (ATProto, 'did:plc:x', ActivityPub, 'https://bsky.brid.gy/ap/did:plc:x'),
            (ATProto, 'did:plc:x', Fake, 'fake:u:did:plc:x'),
            (ATProto, 'https://bsky.app/profile/user.com', ATProto, 'did:plc:123'),
            (ATProto, 'https://bsky.app/profile/did:plc:123', ATProto, 'did:plc:123'),
            (Fake, 'fake:user', ActivityPub, 'https://fa.brid.gy/ap/fake:user'),
            (Fake, 'fake:user', ATProto, 'did:plc:789'),
            (Fake, 'fake:user', Fake, 'fake:user'),
            (Fake, 'fake:user', Web, 'https://fa.brid.gy/web/fake:user'),
            (Web, 'user.com', ActivityPub, 'http://localhost/user.com'),
            (Web, 'https://user.com/', ActivityPub, 'http://localhost/user.com'),
            (Web, 'user.com', ATProto, 'did:plc:123'),
            (Web, 'https://user.com', ATProto, 'did:plc:123'),
            (Web, 'https://bsky.app/profile/user.com', ATProto, 'did:plc:123'),
            (Web, 'https://bsky.app/profile/did:plc:123', ATProto, 'did:plc:123'),
            (Web, 'user.com', Fake, 'fake:u:user.com'),
            (Web, 'user.com', Web, 'user.com'),
            (Web, 'https://user.com/', Web, 'user.com'),
        ]:
            with self.subTest(from_=from_.LABEL, to=to.LABEL):
                self.assertEqual(expected, translate_user_id(
                    id=id, from_=from_, to=to))

    def test_translate_user_id_no_copy_did_stored(self):
        for proto, id in [
            (Web, 'user.com'),
            (ActivityPub, 'https://instance/user'),
            (Fake, 'fake:user'),
        ]:
            with self.subTest(proto=proto.LABEL):
                self.assertIsNone(translate_user_id(id=id, from_=proto, to=ATProto))

    def test_translate_user_id_use_instead(self):
        did = Target(uri='did:plc:123', protocol='atproto')
        user = self.make_user('user.com', cls=Web, copies=[did])
        self.make_user('www.user.com', cls=Web, use_instead=user.key)

        for proto, expected in [
            (ATProto, 'did:plc:123'),
            (ActivityPub, 'http://localhost/user.com'),
            (Fake, 'fake:u:user.com'),
        ]:
            with self.subTest(proto=proto.LABEL):
                self.assertEqual(expected, translate_user_id(
                    id='www.user.com', from_=Web, to=proto))
                self.assertEqual(expected, translate_user_id(
                    id='https://www.user.com/', from_=Web, to=proto))

    @patch('ids._FED_SUBDOMAIN_SITES', new={'on-fed.com'})
    def test_translate_user_id_web_ap_subdomain_fed(self):
        for base_url in ['https://web.brid.gy/', 'https://fed.brid.gy/']:
            with app.test_request_context('/', base_url=base_url):
                self.assertEqual('https://web.brid.gy/on-web.com', translate_user_id(
                    id='on-web.com', from_=Web, to=ActivityPub))
                self.assertEqual('https://fed.brid.gy/on-fed.com', translate_user_id(
                    id='on-fed.com', from_=Web, to=ActivityPub))

    def test_translate_handle(self):
        for from_, handle, to, expected in [
            # basic
            (Web, 'user.com', ActivityPub, '@user.com@web.brid.gy'),
            (Web, 'user.com', ATProto, 'user.com.web.brid.gy'),
            (Web, 'user.com', Fake, 'fake:handle:user.com'),
            (Web, 'user.com', Web, 'user.com'),

            (ActivityPub, '@user@instance', ActivityPub, '@user@instance'),
            (ActivityPub, '@user@instance', ATProto, 'user.instance.ap.brid.gy'),
            (ActivityPub, '@user@instance', Fake, 'fake:handle:@user@instance'),
            (ActivityPub, '@user@instance', Web, 'https://instance/@user'),

            (ATProto, 'user.com', ActivityPub, '@user.com@bsky.brid.gy'),
            (ATProto, 'user.com', ATProto, 'user.com'),
            (ATProto, 'user.com', Fake, 'fake:handle:user.com'),
            (ATProto, 'user.com', Web, 'user.com'),

            (Fake, 'fake:handle:user', ActivityPub, '@fake:handle:user@fa.brid.gy'),
            (Fake, 'fake:handle:user', ATProto, 'fake:handle:user.fa.brid.gy'),
            (Fake, 'fake:handle:user', Fake, 'fake:handle:user'),
            (Fake, 'fake:handle:user', Web, 'fake:handle:user'),
        ]:
            with self.subTest(from_=from_.LABEL, to=to.LABEL):
                self.assertEqual(expected, translate_handle(
                    handle=handle, from_=from_, to=to, enhanced=False))

    def test_translate_handle_enhanced(self):
        for from_, handle, to, expected in [
            (Web, 'user.com', ActivityPub, '@user.com@user.com'),
            (Web, 'user.com', Fake, 'fake:handle:user.com'),
            (ActivityPub, '@user@instance', Web, 'https://instance/@user'),
            (ActivityPub, '@user@user', Web, 'https://user'),
            (ActivityPub, '@user@instance', Fake, 'fake:handle:@user@instance'),
            (ATProto, 'user.com', ActivityPub, '@user.com@user.com'),
        ]:
            with self.subTest(from_=from_.LABEL, to=to.LABEL):
                self.assertEqual(expected, translate_handle(
                    handle=handle, from_=from_, to=to, enhanced=True))

    def test_translate_object_id(self):
        self.store_object(id='http://po.st',
                          copies=[Target(uri='at://did/web/post', protocol='atproto')])
        self.store_object(id='https://inst/post',
                          copies=[Target(uri='at://did/ap/post', protocol='atproto')])
        self.store_object(id='fake:post',
                          copies=[Target(uri='at://did/fa/post', protocol='atproto')])

        # DID doc and ATProto, used to resolve handle in bsky.app URL
        did = self.store_object(id='did:plc:123', raw={
            'id': 'did:plc:123',
            'alsoKnownAs': ['at://user.com'],
        })
        ATProto(id='did:plc:123', obj_key=did.key).put()

        for from_, id, to, expected in [
            (ActivityPub, 'https://inst/post', ActivityPub, 'https://inst/post'),
            (ActivityPub, 'https://inst/post', ATProto, 'at://did/ap/post'),
            (ActivityPub, 'https://inst/post', Fake, 'fake:o:ap:https://inst/post'),
            (ActivityPub, 'https://inst/post',
             Web, 'https://ap.brid.gy/convert/web/https://inst/post'),
            (ATProto, 'at://did/atp/post', ATProto, 'at://did/atp/post'),
            # copies
            (ATProto, 'at://did/web/post', Web, 'http://po.st'),
            (ATProto, 'at://did/ap/post', ActivityPub, 'https://inst/post'),
            (ATProto, 'at://did/fa/post', Fake, 'fake:post'),
            # no copies
            (ATProto, 'did:plc:x', Web, 'https://bsky.brid.gy/convert/web/did:plc:x'),
            (ATProto, 'did:plc:x', ActivityPub, 'https://bsky.brid.gy/convert/ap/did:plc:x'),
            (ATProto, 'did:plc:x', Fake, 'fake:o:bsky:did:plc:x'),
            (ATProto, 'https://bsky.app/profile/user.com/post/456',
             ATProto, 'at://did:plc:123/app.bsky.feed.post/456'),
            (ATProto, 'https://bsky.app/profile/did:plc:123/post/456',
             ATProto, 'at://did:plc:123/app.bsky.feed.post/456'),
            (Fake, 'fake:post',
             ActivityPub, 'https://fa.brid.gy/convert/ap/fake:post'),
            (Fake, 'fake:post', ATProto, 'at://did/fa/post'),
            (Fake, 'fake:post', Fake, 'fake:post'),
            (Fake, 'fake:post', Web, 'https://fa.brid.gy/convert/web/fake:post'),
            (Web, 'http://po.st', ActivityPub, 'http://localhost/r/http://po.st'),
            (Web, 'http://po.st', ATProto, 'at://did/web/post'),
            (Web, 'http://po.st', Fake, 'fake:o:web:http://po.st'),
            (Web, 'http://po.st', Web, 'http://po.st'),
        ]:
            with self.subTest(from_=from_.LABEL, to=to.LABEL):
                self.assertEqual(expected, translate_object_id(
                    id=id, from_=from_, to=to))

    @patch('ids._FED_SUBDOMAIN_SITES', new={'on-fed.com'})
    def test_translate_object_id_web_ap_subdomain_fed(self):
        for base_url in ['https://web.brid.gy/', 'https://fed.brid.gy/']:
            with app.test_request_context('/', base_url=base_url):
                got = translate_object_id(id='http://on-fed.com/post', from_=Web,
                                          to=ActivityPub)
                self.assertEqual('https://fed.brid.gy/r/http://on-fed.com/post', got)

                got = translate_object_id(id='http://on-web.com/post', from_=Web,
                                          to=ActivityPub)
                self.assertEqual('https://web.brid.gy/r/http://on-web.com/post', got)
