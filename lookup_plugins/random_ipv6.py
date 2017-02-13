#
# (c) 2016, Martin Verges <martin@verges.cc>
#
# ---
# Please note, that I took a look and some code from password.py to get this done.
# 
# Therefore thanks to 
#     Daniel Hokka Zakrisson <daniel@hozac.com>
#     Javier Candeira <javier@candeira.com>
#     Maykel Moya <mmoya@speedyrails.com>
# ---

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

from random import seed, getrandbits
from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.lookup import LookupBase
from ansible.parsing.splitter import parse_kv
from ansible.module_utils._text import to_bytes,to_text
from ansible.utils.path import makedirs_safe


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

DEFAULT_LENGTH = 64
VALID_PARAMS = frozenset(('length'))


def _parse_parameters(term):
    """Hacky parsing of params
    See https://github.com/ansible/ansible-modules-core/issues/1968#issuecomment-136842156
    and the first_found lookup For how we want to fix this later
    """
    first_split = term.split(' ', 1)
    if len(first_split) <= 1:
        # Only a single argument given, therefore it's a path
        relpath = term
        params = dict()
    else:
        relpath = first_split[0]
        params = parse_kv(first_split[1])
        if '_raw_params' in params:
            # Spaces in the path?
            relpath = u' '.join((relpath, params['_raw_params']))
            del params['_raw_params']

            # Check that we parsed the params correctly
            if not term.startswith(relpath):
                # Likely, the user had a non parameter following a parameter.
                # Reject this as a user typo
                raise AnsibleError('Unrecognized value after key=value parameters given to lookup')
        # No _raw_params means we already found the complete path when
        # we split it initially

    # Check for invalid parameters.  Probably a user typo
    invalid_params = frozenset(params.keys()).difference(VALID_PARAMS)
    if invalid_params:
        raise AnsibleError('Unrecognized parameter(s) given to password lookup: %s' % ', '.join(invalid_params))

    # Set defaults
    params['length'] = int(params.get('length', DEFAULT_LENGTH))

    return relpath, params


def _gen_random_ipv6(i_len=64):
    seed();
    return "fd%02x:%04x:%04x:%04x::/64" % (getrandbits(8), getrandbits(16), getrandbits(16), getrandbits(16)) 

def _write_to_file(b_path, content):
    b_pathdir = os.path.dirname(b_path)
    makedirs_safe(b_pathdir, mode=0o700)

    with open(b_path, 'wb') as f:
        os.chmod(b_path, 0o600)
        b_content = to_bytes(content, errors='surrogate_or_strict') + b'\n'
        f.write(b_content)

def _read_from_file(b_path):
    """Read the contents of a file and return it
    :arg b_path: A byte string containing the path to the file
    :returns: a text string containing the contents of the file or
        None if no file was present.
    """
    content = None

    if os.path.exists(b_path):
        with open(b_path, 'rb') as f:
            b_content = f.read().rstrip()
        content = to_text(b_content, errors='surrogate_or_strict')

    return content


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        ret = []

        for term in terms:
            relpath, params = _parse_parameters(term)
            path = self._loader.path_dwim(relpath)
            b_path = to_bytes(path, errors='surrogate_or_strict')
            
            content = _read_from_file(b_path)
            if content is None:
                random_ip = _gen_random_ipv6(params['length'])
                _write_to_file(b_path, random_ip)
                ret.append(random_ip)
            else:
                ret.append(content)

        return ret


