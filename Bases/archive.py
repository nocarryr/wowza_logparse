#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# archive.py
# Copyright (c) 2011 Matthew Reid

import os.path
import traceback
import time
import datetime
import tarfile
from StringIO import StringIO
import csv

from BaseObject import BaseObject
import Serialization


def build_datetime_string(fmt_str, dt=None):
    if dt is None:
        dt = datetime.datetime.now()
    return dt.strftime(fmt_str)
    
def parse_datetime_string(s, fmt_str):
    return datetime.datetime.strptime(s, fmt_str)

class ArchiveMember(BaseObject):
    _saved_class_name = 'ArchiveMember'
    _saved_attributes = ['filename', 'file_created', 'file_modified']
    def __init__(self, **kwargs):
        super(ArchiveMember, self).__init__(**kwargs)
        self.saved_attributes.discard('Index')
        self.name = kwargs.get('name')
        self.path = kwargs.get('path', '/')
        self.filename = kwargs.get('filename')
        self.id = kwargs.get('id', self.full_path)
        self.serialize_method = kwargs.get('serialize_method', 'json')
        self._do_serialize = getattr(self, '_serialize_' + self.serialize_method)
        self._do_deserialize = getattr(self, '_deserialize_' + self.serialize_method)
        self.serialize_obj = kwargs.get('serialize_obj', {})
        self.serialize_kwargs = kwargs.get('serialize_kwargs', {})
        self.deserialize_kwargs = kwargs.get('deserialize_kwargs', {})
        self.csv_columns = kwargs.get('csv_columns')
        self.datetime_format = kwargs.get('datetime_format', '%Y%m%d-%H:%M:%S')
        self.json_preset = kwargs.get('json_preset', 'pretty')
        self.file_created = None
        self.file_modified = None
        
    @property
    def full_path(self):
        return os.path.join(self.path, self.filename)
        
    def save(self):
        if self.file_created is None:
            self.file_created = build_datetime_string(self.datetime_format)
            self.file_modified = self.file_created
        if self.file_modified is None:
            self.file_modified = build_datetime_string(self.datetime_format)
        file = StringIO()
        self._do_serialize(file)
        file.seek(0)
        tinf = tarfile.TarInfo(self.full_path)
        tinf.size = len(file.buf)
        dt = parse_datetime_string(self.file_modified, self.datetime_format)
        tinf.mtime = time.mktime(dt.timetuple())
        return file, tinf
        
    def load(self, tar):
        try:
            tinf = tar.getmember(self.full_path)
            file = tar.extractfile(tinf)
        except KeyError:
            return
        self._do_deserialize(file)
        file.close()
        
    def _deserialize_json(self, file):
        js = ''
        for line in file:
            js += line
        d = Serialization.from_json(js)
        self._load_saved_attr(d)
        for key, objdict in d['serialize_obj'].iteritems():
            obj = self.serialize_obj.get(key)
            if not obj:
                continue
            dskwargs = self.deserialize_kwargs.get(key, {})
            obj._load_saved_attr(objdict, **dskwargs)
        
    def _serialize_json(self, file):
        d = self._get_saved_attr()
        d['serialize_obj'] = {}
        for key, obj in self.serialize_obj.iteritems():
            skwargs = self.serialize_kwargs.get(key, {})
            d['serialize_obj'][key] = obj._get_saved_attr(**skwargs)
        s = Serialization.to_json(d, self.json_preset)
        file.write(s)
        
    def _deserialize_csv(self, file):
        pass
        
    def _serialize_csv(self, file):
        keys = self.csv_columns
        serialize_obj = self.serialize_obj
        if callable(serialize_obj):
            serialize_obj = serialize_obj()
        if keys is None:
            keys = serialize_obj[0].keys()
        headers = self.serialize_kwargs.get('write_headers', True)
        indexed = self.serialize_kwargs.get('add_index', True)
        if indexed:
            keys.insert(0, 'index')
        writer = csv.DictWriter(file, fieldnames=keys)
        
        if headers:
            writer.writerow(dict(zip(keys, [key.title() for key in keys])))
        for i, d in enumerate(serialize_obj):
            d = d.copy()
            if indexed:
                d.setdefault('index', i)
            writer.writerow(d)
        
class Archive(BaseObject):
    _ChildGroups = {'members':{'child_class':ArchiveMember}}
    def __init__(self, **kwargs):
        super(Archive, self).__init__(**kwargs)
        self.compression_format = kwargs.get('compression_format')
        if self.compression_format is None:
            self.compression_format = ''
        
    def add_member(self, **kwargs):
        self.members.add_child(**kwargs)
        
    def save(self, filename, members=None):
        if members is None:
            members = self.members.keys()
        tar = tarfile.open(filename, ':'.join(['w', self.compression_format]))
        files = []
        for key in members:
            member = self.members[key]
            file, tinf = member.save()
            files.append(file)
            tar.addfile(tinf, fileobj=file)
        tar.close()
        for file in files:
            file.close()
            
    def load(self, filename, members=None):
        if members is None:
            members = [self.members.indexed_items[i].id for i in sorted(self.members.indexed_items.keys())]
        try:
            tar = tarfile.open(filename, 'r:')
        except tarfile.TarError:
            tar = tarfile.open(filename, 'r:gz')
        except tarfile.TarError:
            tar = tarfile.open(filename, 'r:bz2')
        except:
            traceback.print_exc()
            return
        for key in members:
            self.members[key].load(tar)
        tar.close()
        
