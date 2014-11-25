#! /usr/bin/env python
from ConfigParser import SafeConfigParser
import git

class SubtreeConfFile(object):
    def __init__(self, **kwargs):
        self.filename = kwargs.get('filename', '.gitsubtrees')
        self.parser = SafeConfigParser()
        self.subtrees = {}
        
class SubtreeConfFileWriter(SubtreeConfFile):
    def __init__(self, **kwargs):
        super(SubtreeConfFile, self).__init__(**kwargs)
        
    
class SubTreeConfFileReader(SubtreeConfFile):
    def __init__(self, **kwargs):
        super(SubTreeConfFileReader, self).__init__(**kwargs)
        self.parse_subtrees()
    def parse_subtrees(self):
        p = self.parser
        p.read(self.filename)
        keys = ['remote', 'branch', 'url']
        for section in p.sections():
            if 'subtree' not in section:
                continue
            d = {}
            prefix = section.split('subtree')[1].strip().strip('"')
            d.update(dict(zip(keys, [p.get(section, key) for key in keys])))
            subtree_id = SubtreeConf.build_id(**d)
            subtree = self.subtrees.get(subtree_id)
            if subtree is None:
                subtree = SubtreeConf(**d)
                self.subtrees[subtree.id] = subtree
            subtree.prefixes.add(prefix)
    def add_remotes(self):
        repo = git.Repo()
        for subtree in self.subtrees.itervalues():
            try:
                remote = repo.remote(subtree.remote)
                remote.fetch()
            except git.GitCommandError:
                print 'adding remote: %s' % (remote)
                remote = repo.create_remote(subtree.remote, subtree.url)
                #remote.fetch()
            except ValueError:
                remote = repo.create_remote(subtree.remote, subtree.url)
                #remote.fetch()
        
        
class SubtreeConf(object):
    def __init__(self, **kwargs):
        self.remote = kwargs.get('remote')
        self.url = kwargs.get('url')
        self.branch = kwargs.get('branch')
        self.prefixes = set()
        self.id = self.build_id(**kwargs)
        for prefix in kwargs.get('prefixes', []):
            self.prefixes.add(prefix)
    @staticmethod
    def build_id(**kwargs):
        return '/'.join([kwargs['remote'], kwargs['branch']])
        
def add_remotes(**kwargs):
    conf_reader = SubTreeConfFileReader(**kwargs)
    conf_reader.add_remotes()
    return conf_reader
    
if __name__ == '__main__':
    add_remotes()
