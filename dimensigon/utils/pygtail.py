# -*- coding: utf-8 -*-

# pygtail - a python "port" of logtail2
# Copyright (C) 2011 Brad Greenlee <brad@footle.org>
#
# Derived from logcheck <http://logcheck.org>
# Copyright (C) 2003 Jonathan Middleton <jjm@ixtab.org.uk>
# Copyright (C) 2001 Paul Slootman <paul@debian.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from __future__ import print_function

import glob
import gzip
import os
import sys
import typing as t
from os import fstat, stat
from os.path import exists, getsize

from dimensigon.utils.mixins import LoggerMixin

PY3 = sys.version_info[0] == 3
MAX_LINE_SIZE = 250 * 1024 * 1024

if PY3:
    text_type = str
else:
    text_type = unicode


def force_text(s, encoding='utf-8', errors='strict'):
    if isinstance(s, text_type):
        return s
    return s.decode(encoding, errors)


class Pygtail(LoggerMixin):
    """
    Creates an iterable object that returns only unread lines.

    Parameters
    ----------
    offset_file:
       File to which offset data is written (default: <logfile>.offset).
    offset_mode:
       Sets when the offset is updated.
            'manual' updates the offset when set_offset called.
            'every' updates the offset file every n'th line. Parameter every_n must be given.
            'paranoid' updates the offset file every time we read a line.
            'endfile' updates the offset when we reach the end of the file.
    every_n:
        number of lines until the offset will be updated when 'every' offset mode set.
    copytruncate:
        Support copytruncate-style log rotation (default: True)
    on_update:
        Execute this function when offset data is written (default None)
    read_from_end:
        starts reading the file from the end discarding initial content
    log_patterns:
        List of custom rotated log patterns to match (default: None)
    full_lines:
        Only log when line ends in a newline (default: False)
    new_line:
        characters of new line. If None sets according to the OS
    binary:
        reads the file in binary mode.
    encoding:
        sets the encoding for the file
    errors:
        The errors argument specifies the response when the input string can’t be converted according to the
        encoding’s rules. See built-in open function for more details

    """

    def __init__(self, file, offset_file=None, offset_mode='endfile', copytruncate=True,
                 on_update: t.Callable = None, read_from_end=False, log_patterns=None, full_lines=False,
                 binary=False, encoding=None, errors=None, every_n=None):
        self.file = file
        if offset_mode in ('manual', 'every', 'paranoid', 'endfile'):
            if offset_mode == 'every':
                try:
                    self.every_n = int(every_n)
                except TypeError:
                    raise AttributeError("Parameter 'every_n' must be an integer when offset_mode in every")
            else:
                self.every_n = None
        else:
            raise AttributeError(f"invalid offset_mode '{offset_mode}'. See docstring for more details")
        self.offset_mode = offset_mode
        self.on_update = on_update
        self.copytruncate = copytruncate
        self.read_from_end = read_from_end
        self.log_patterns = log_patterns
        self.binary = binary
        self.encoding = encoding
        self.errors = errors
        self._full_lines = full_lines
        self._offset_file = offset_file or "%s.offset" % self.file
        self._offset_file_inode = 0
        self._offset = 0
        self._since_update = 0
        self._fh = None
        self._rotated_logfile = None

        # if offset file exists and non-empty, open and parse it
        if exists(self._offset_file) and getsize(self._offset_file):
            with open(self._offset_file, "r") as offset_fh:
                (self._offset_file_inode, self._offset) = [int(line.strip()) for line in offset_fh]
            if self._offset_file_inode != self.file_id or \
                    stat(self.file).st_size < self._offset:
                # The inode has changed or filesize has reduced so the file
                # might have been rotated.
                # Look for the rotated file and process that if we find it.
                self._rotated_logfile = self._determine_rotated_logfile()

    @property
    def file_id(self):
        data = stat(self.file)
        return data.st_ino or data.st_ctime_ns

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.file_id == self.file_id

    def __del__(self):
        if self._filehandle():
            self._filehandle().close()

    def __iter__(self):
        return self

    def next(self):
        """
        Return the next line in the file, updating the offset.
        """
        try:
            line = self._get_next_line()
        except StopIteration:
            # we've reached the end of the file; if we're processing the
            # rotated log file or the file has been renamed, we can continue with the actual file; otherwise
            # update the offset file
            if self._is_new_file():
                self._rotated_logfile = None
                self._fh.close()
                self._offset = 0
                # open up current logfile and continue
                try:
                    line = self._get_next_line()
                except StopIteration:  # oops, empty file
                    if self.offset_mode == 'endfile':
                        self._update_offset_file()
                        raise
            else:
                if self.offset_mode == 'endfile':
                    self._update_offset_file()
                raise

        if self.offset_mode == 'paranoid':
            self._update_offset_file()
        elif self.offset_mode == 'every' and self.every_n and self.every_n <= self._since_update:
            self._update_offset_file()

        return line

    def __next__(self):
        """`__next__` is the Python 3 version of `next`"""
        return self.next()

    def readline(self):
        try:
            return next(self)
        except StopIteration:
            return b'' if self.binary else ''

    def readlines(self, max_lines=None) -> t.List:
        """
        Read in all unread lines and return them as a list.
        """
        lines = []
        line = '\n'
        while (max_lines is None or len(lines) < max_lines) and len(line) != 0:
            line = self.readline()
            if line:
                lines.append(line)
        return lines

    def read(self, max_lines=None):
        """
        Read in all unread lines and return them as a single string.
        """
        lines = self.readlines(max_lines)
        if lines:
            # try:
            #     return ''.join(lines)
            # except TypeError:
            #     return ''.join(force_text(line) for line in lines)
            return b''.join(lines) if self.binary else ''.join(lines)
        else:
            return b'' if self.binary else ''

    def _is_closed(self):
        if not self._fh:
            return True
        try:
            return self._fh.closed
        except AttributeError:
            if isinstance(self._fh, gzip.GzipFile):
                # python 2.6
                return self._fh.fileobj is None
            else:
                raise

    def _filehandle(self):
        """
        Return a filehandle to the file being tailed, with the position set
        to the current offset.
        """
        if not self._fh or self._is_closed():
            file = self._rotated_logfile or self.file
            if file.endswith('.gz'):
                self._fh = gzip.open(file, 'rb' if self.binary else 'rt', encoding=self.encoding,
                                     errors=self.errors)
            else:
                self._fh = open(file, 'rb' if self.binary else 'r', 1, encoding=self.encoding, errors=self.errors)
            if self.read_from_end and not exists(self._offset_file):
                self._fh.seek(0, os.SEEK_END)
            else:
                self._fh.seek(self._offset)

        return self._fh

    def _update_offset_file(self):
        """
        Update the offset file with the current inode and offset.
        """
        if self.on_update:
            self.on_update()
        offset = self._filehandle().tell()
        fh = open(self._offset_file, "w")
        fh.write("%s\n%s\n" % (self.file_id, offset))
        fh.close()
        self._since_update = 0

    def update_offset_file(self):
        self._update_offset_file()

    def _determine_rotated_logfile(self):
        """
        We suspect the logfile has been rotated, so try to guess what the
        rotated file is, and return it.
        """
        rotated_filename = self._check_rotated_filename_candidates()
        if rotated_filename and exists(rotated_filename):
            data = stat(rotated_filename)
            if (data.st_ino or data.st_ctime_ns) == self._offset_file_inode:
                return rotated_filename

            # if the inode hasn't changed, then the file shrank; this is expected with copytruncate,
            # otherwise print a warning
            if self.file_id == self._offset_file_inode:
                if self.copytruncate:
                    return rotated_filename
                else:
                    sys.stderr.write(
                        "[pygtail] [WARN] file size of %s shrank, and copytruncate support is "
                        "disabled (expected at least %d bytes, was %d bytes).\n" %
                        (self.file, self._offset, stat(self.file).st_size))

        return None

    def _check_rotated_filename_candidates(self):
        """
        Check for various rotated logfile file patterns and return the first
        match we find.
        """
        # savelog(8)
        candidate = "%s.0" % self.file
        if (exists(candidate) and exists("%s.1.gz" % self.file) and
                (stat(candidate).st_mtime > stat("%s.1.gz" % self.file).st_mtime)):
            return candidate

        # logrotate(8)
        # with delaycompress
        candidate = "%s.1" % self.file
        if exists(candidate):
            return candidate

        # without delaycompress
        candidate = "%s.1.gz" % self.file
        if exists(candidate):
            return candidate

        rotated_filename_patterns = [
            # logrotate dateext rotation scheme - `dateformat -%Y%m%d` + with `delaycompress`
            "%s-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]",
            # logrotate dateext rotation scheme - `dateformat -%Y%m%d` + without `delaycompress`
            "%s-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].gz",
            # logrotate dateext rotation scheme - `dateformat -%Y%m%d-%s` + with `delaycompress`
            "%s-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]",
            # logrotate dateext rotation scheme - `dateformat -%Y%m%d-%s` + without `delaycompress`
            "%s-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].gz",
            # for TimedRotatingFileHandler
            "%s.[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]",
        ]
        if self.log_patterns:
            rotated_filename_patterns.extend(self.log_patterns)

        # break into directory and file components to support cases where
        # the file is prepended as part of rotation
        file_dir, rel_filename = os.path.split(self.file)
        for rotated_filename_pattern in rotated_filename_patterns:
            candidates = glob.glob(os.path.join(file_dir, rotated_filename_pattern % rel_filename))
            if candidates:
                candidates.sort()
                return candidates[-1]  # return most recent

        # no match
        return None

    def _is_new_file(self):
        # Processing rotated logfile or at the end of current file which has been renamed
        data = fstat(self._filehandle().fileno())
        return self._rotated_logfile or \
               self._filehandle().tell() == data.st_size and (data.st_ino or data.st_ctime_ns) != self.file_id

    def _get_next_line(self) -> t.Union[str, bytes]:

        curr_offset = self._filehandle().tell()
        line = self._filehandle().readline(MAX_LINE_SIZE)
        if self._full_lines:
            if self.binary and not line.endswith(self.new_line or os.linesep):
                self._filehandle().seek(curr_offset)
                if len(line) == MAX_LINE_SIZE:
                    self.logger.warning(f"Max Line Size reached while trying to get line from file '{self.file}' "
                                        f"at position {curr_offset}")
                raise StopIteration
            elif not line.endswith('\n'):
                self._filehandle().seek(curr_offset)
                if len(line) == MAX_LINE_SIZE:
                    self.logger.warning(f"Max Line Size reached while trying to get line from file '{self.file}' "
                                        f"at position {curr_offset}")
                raise StopIteration
        if not line:
            raise StopIteration
        self._since_update += 1
        return line
