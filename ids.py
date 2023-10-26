"""Translates user ids, handles, and object ids between protocols.

https://fed.brid.gy/docs#translate
"""
import re

from common import subdomain_wrap, SUPERDOMAIN


def translate_user_id(*, id, from_proto, to_proto):
    """Translate a user id from one protocol to another.

    Args:
      id (str)
      from_proto (protocol.Protocol)
      to_proto (protocol.Protocol)

    Returns:
      str: the corresponding id in ``to_proto``
    """
    assert id and from_proto and to_proto
    assert from_proto.owns_id(id) is not False

    if from_proto == to_proto:
        return id

    match (from_proto.LABEL, to_proto.LABEL):
        case (_, 'atproto'):
            user = from_proto.get_by_id(id)
            return user.atproto_did if user else None
        case ('atproto', _):
            user = from_proto.get_for_copy(id)
            return user.key.id() if user else None
        case (_, 'activitypub'):
            return subdomain_wrap(from_proto, f'/ap/{id}')
        case ('activitypub', 'web'):
            return id
        # fake protocol is only for unit tests
        case (_, 'fake'):
            return f'fake:{id}'
        case ('fake', _):
            return id

    assert False, (id, from_proto, to_proto)


def translate_handle(*, handle, from_proto, to_proto):
    """Translates a user handle from one protocol to another.

    Args:
      handle (str)
      from_proto (protocol.Protocol)
      to_proto (protocol.Protocol)

    Returns:
      str: the corresponding handle in ``to_proto``
    """
    assert handle and from_proto and to_proto
    assert from_proto.owns_handle(handle) is not False

    if from_proto == to_proto:
        return handle

    match (from_proto.LABEL, to_proto.LABEL):
        case (_, 'activitypub'):
            if True:  # basic
                return f'@{handle}@{from_proto.ABBREV}{SUPERDOMAIN}'
            else:  # enhanced (TODO)
                return f'@{handle}@{handle}'
        case (_, 'atproto' | 'nostr'):
            handle = handle.lstrip('@').replace('@', '.')
            if True:  # basic
                return f'{handle}.{from_proto.ABBREV}{SUPERDOMAIN}'
            else:  # enhanced (TODO)
                return handle
        case ('activitypub', 'web'):
            user, instance = handle.lstrip('@').split('@')
            return f'instance/@user'  # TODO
        case (_, 'web'):
            return handle
        case (_, 'fake'):
            return f'fake:handle:{handle}'

    assert False, (id, from_proto, to_proto)
