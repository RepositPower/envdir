import glob
import os
import subprocess

try:
    from UserDict import IterableUserDict as UserDict
except ImportError:
    from collections import UserDict


def isenvvar(name):
    root, name = os.path.split(name)
    return '=' not in name


class Env(UserDict):
    """
    An dict-like object to represent an envdir environment with extensive
    API, can be used as context manager, too.
    """
    def __init__(self, path):
        self.path = path
        self.data = {}
        self.originals = {}
        self.created = {}
        self._load()

    def __repr__(self):
        return "<envdir.Env '%s'>" % self.path

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.clear()

    def __getitem__(self, name):
        return self._get(name)

    def __setitem__(self, name, value):
        self._write(**{name: value})
        self._set(name, value)
        self.created[name] = value

    def __delitem__(self, name):
        os.remove(os.path.join(self.path, name))
        self._delete(name)

    def __contains__(self, name):
        return (name in self.data or
                os.path.exists(os.path.join(self.path, name)))

    def _load(self):
        for path in filter(isenvvar, glob.glob(os.path.join(self.path, '*'))):
            root, name = os.path.split(path)
            value = self._get(name)
            self._set(name, value)

    def _open(self, name, mode='r'):
        return open(os.path.join(self.path, name), mode)

    def _get(self, name, default=None):
        path = os.path.join(self.path, name)
        if not os.path.exists(path):
            return default
        with self._open(name) as var:
            return var.read().strip('\n').replace('\x00', '\n')

    def _set(self, name, value):
        if name in os.environ:
            self.originals[name] = os.environ[name]
        self.data[name] = value
        if value:
            os.environ[name] = value
        elif name in os.environ:
            del os.environ[name]

    def _delete(self, name):
        if name in self.originals:
            os.environ[name] = self.originals[name]
        elif name in os.environ:
            del os.environ[name]
        if name in self.data:
            del self.data[name]

    def _write(self, **values):
        for name, value in values.items():
            with self._open(name, 'w') as env:
                env.write(value)

    def clear(self):
        """
        Clears the envdir by resetting the os.environ items to the
        values it had before opening this envdir (or removing them
        if they didn't exist). Doesn't delete the envdir files.
        """
        for name in list(self.data.keys()):
            self._delete(name)


class EnvFile(Env):
    def __repr__(self):
        return "<envdir.EnvFile '%s'>" % self.path

    def _load(self):
        proc = subprocess.Popen([
            os.environ.get('SHELL', 'sh'), '-c', 'source {0} && env'.format(
                self.path)], stdout=subprocess.PIPE
        )

        for name, value in [export.strip().split('=', 1)
                            for export in proc.stdout]:
            self._set(name.strip(), value.strip())
