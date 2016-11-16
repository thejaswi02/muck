# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.
# muck libary functions.

import sys
assert sys.version_info.major == 3 # python 2 is not supported.

import random
import time
import re
import requests
import pithy.meta as meta

from csv import reader as csv_reader
from http import HTTPStatus
from sys import argv
from pithy.path_encode import path_for_url
from pithy.io import errF, errFL, failF
from pithy.fs import make_dirs, path_dir, path_exists, path_ext, path_join, path_stem
from pithy.json_utils import load_json, load_jsonl, load_jsons
from pithy.transform import Transformer
from typing import Optional


# module exports.
__all__ = [
  'HTTPError',
  'add_loader',
  'dst_path',
  'fetch',
  'load',
  'load_url',
  'open_dep',
  'regex_for_wildcard_path',
  'target_var',
  'target_vars',
  'transform',
]


build_dir = '_build'
info_name = '_muck_info.json'

reserved_names = {
  'clean',
  'clean-all',
  'muck',
  'patch',
  build_dir,
  info_name,
}

reserved_exts = {
  '.tmp',
}

ignored_exts = {
  '.err', '.iot', '.out', # iotest extensions.
}


_wildcard_re = re.compile(r'(%+)')

def regex_for_wildcard_path(path):
  '''
  Split by the muck wildcard character, '%'.
  This character was chosen because bash treats it as a plain char.
  Consecutive wildcards indicate required padding.
  '''
  chunks = _wildcard_re.split(path)
  pattern = ''.join('({}+)'.format('.' * len(s)) if s.startswith('%') else re.escape(s) for s in chunks)
  return re.compile(pattern)


def target_vars():
  script_path, output_path = argv
  script_stem = path_stem(script_path)
  r = regex_for_wildcard_path(path_join(build_dir, script_stem))
  m = r.match(output_path)
  return m.groups()


def target_var(): return target_vars()[0]


def dst_path(): return argv[1]


def is_product_path(path):
  return path == build_dir or path.startswith(build_dir + '/')

def product_path_for_target(target_path):
  if is_product_path(target_path):
    raise ValueError('provided target path is prefixed with build dir: {}'.format(target_path))
  return path_join(build_dir, target_path)

def actual_path_for_target(target_path):
  'returns the target_path, if it exists, or else the corresponding product path.'
  if path_exists(target_path):
    return target_path
  return product_path_for_target(target_path)


_open_deps_parameters = { 'binary', 'buffering', 'encoding', 'errors', 'newline' }

def open_dep(target_path, binary=False, buffering=-1, encoding=None, errors=None, newline=None):
  '''
  Open a dependency for reading.

  Muck's static analysis looks specifically for this function to infer dependencies;
  `target_path` must be a string literal.
  '''
  path = actual_path_for_target(target_path)
  try:
    return open(path, mode=('rb' if binary else 'r'), buffering=buffering, encoding=encoding, errors=errors, newline=newline)
  except FileNotFoundError:
    errFL('muck.open_dep cannot open path: {}', path)
    if path != target_path:
      errFL('note: nor does a file exist at source path: {}', target_path)
    raise


_loaders = {}

def add_loader(ext, fn, **open_dep_kwargs):
  '''
  Register a loader function, which will be called by `muck.load` for matching `ext`.
  Any keyword arguments passed here will be used as defaults when calling `open_dep`,
  and will determine which keyword arguments passed to `muck.load` will be passed to open_dep;
  all other keyword arguments will be passed to `fn`.
  '''
  if not ext.startswith('.'):
    raise ValueError("file extension does not start with '.': {!r}".format(ext))
  if ext not in _default_loaders:
    try: existing_fn, _ = _loaders[ext]
    except KeyError: pass
    else: raise Exception('add_loader: extension previously registered: {!r}; fn: {!r}'.format(ext, existing_fn))
  for k, v in sorted(open_dep_kwargs.items()):
    if k not in _open_deps_parameters: raise KeyError(k)
  _loaders[ext] = (fn, open_dep_kwargs)


def load_txt(f): return f

_default_loaders = (
  ('.csv',   csv_reader, dict(newline='')),
  ('.json',  load_json, dict(encoding=None)),
  ('.jsonl', load_jsonl, dict(encoding=None)),
  ('.jsons', load_jsons, dict(encoding=None)),
  ('.txt',   load_txt, dict(binary=False, buffering=-1, encoding=None, errors=None, newline=None)),
)

for ext, fn, args in _default_loaders:
  add_loader(ext, fn, **args)

def load(target_path, ext=None, **kwargs):
  '''
  Select an appropriate loader based on the file extension, or `ext` if specified.

  If a loader is found, then `open_dep` is called with the default `open_dep_kwargs` registered by `add_loader`,
  except updated by any values with matching keys in `kwargs`.
  The remaining `kwargs` are passed to the loader function registered by `add_loader`.
  Thus, keyword arguments passed to `load` get divvied up between `open_dep` and the custom load function.

  If no loader is found, raise an error.

  Muck's static analysis looks specifically for this function to infer dependencies;
  `target_path` must be a string literal.
  '''
  if ext is None:
    ext = path_ext(target_path)
  elif not isinstance(ext, str): raise TypeError(ext)
  try: load_fn, std_open_args = _loaders[ext]
  except KeyError:
    errFL('ERROR: No loader found for target: {!r}', target_path)
    errFL('NOTE: extension: {!r}', ext)
    raise
  open_args = std_open_args.copy()
  # transfer all matching kwargs to open_args.
  for k in _open_deps_parameters:
    try: v = kwargs[k]
    except KeyError: continue
    open_args[k] = v
    del kwargs[k] # only pass this arg to open_deps; del is safe because kwargs has local lifetime.
  file = open_dep(target_path, **open_args)
  return load_fn(file, **kwargs)


class HTTPError(Exception): pass


def _fetch(url, timeout, headers, expected_status_code):
  '''
  wrap the call to `get` with try/except that flattens any exception trace into an HTTPError.
  without this, a backtrace due to a network failure is massive, involves multiple exceptions,
  and is mostly irrelevant to the caller.
  '''
  try:
    msg = None
    r = requests.get(url, timeout=timeout, headers=headers)
  except Exception as e:
    msg = 'fetch failed with exception: {}: {}'.format(
      type(e).__name__, ', '.join(str(a) for a in e.args))
  else:
    if r.status_code != expected_status_code:
      s = HTTPStatus(r.status_code)
      msg = 'fetch failed with HTTP code: {}: {}; {}.'.format(s.value, s.phrase, s.description)
  if msg is not None:
    raise HTTPError(msg)
  return r


def fetch(url, expected_status_code=200, headers={}, timeout=4, delay=0, delay_range=0):
  "Fetch the data at `url` and save it to a path in the '_fetch' directory derived from the URL."
  path = path_join('_fetch', path_for_url(url))
  if not path_exists(path):
    errFL('fetch: {}', url)
    r = _fetch(url, timeout, headers, expected_status_code)
    make_dirs(path_dir(path))
    with open(path, 'wb') as f:
      f.write(r.content)
    sleep_min = delay - delay_range * 0.5
    sleep_max = delay + delay_range * 0.5
    sleep_time = random.uniform(sleep_min, sleep_max)
    if sleep_time > 0:
      time.sleep(sleep_time)
  return path


def load_url(url, ext=None, expected_status_code=200, headers={}, timeout=4, delay=0, delay_range=0, **kwargs):
  'Fetch the data at `url` and then load using `muck.load`.'
  # note: implementing uncached requests efficiently requires new versions of the source functions;
  # these will take a text argument instead of a path argument.
  # alternatively, the source functions could be reimplemented to take text strings,
  # or perhaps streams.
  # in the uncached case, muck would do the open and read.
  path = fetch(url, expected_status_code=expected_status_code, headers=headers,
    timeout=timeout, delay=delay, delay_range=delay_range)
  return load(path, ext=ext, **kwargs)


def transform(target_path, ext=None, **kwargs):
  '''
  Open a dependency using muck.load and then transform it using pithy.Transformer.

  Additional keyword arguments are passed to the specific load function matching `ext`;
  see muck.load for details.

  Muck's static analysis looks specifically for this function to infer dependencies;
  `target_path` must be a string literal.
  '''
  seq = load(target_path, ext=ext, **kwargs)
  return Transformer(seq, log_stem=path_stem(argv[1]) + '.')
