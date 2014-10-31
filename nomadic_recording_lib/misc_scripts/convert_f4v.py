#! /usr/bin/env python

import os.path
import subprocess
import argparse

def LOG(*args):
    entry = ' '.join([str(arg) for arg in args])
    print entry

def handle_filenames(**kwargs):
    infile = kwargs.get('infile')
    inpath = os.path.dirname(infile)
    infile = os.path.basename(infile)
    outfile = kwargs.get('outfile')
    outext = kwargs.get('outext')
    if not outext:
        outext = 'mp4'
    if outfile is None:
        outfile = '.'.join([os.path.splitext(infile)[0], outext])
        outpath = kwargs.get('outpath')
        if outpath is None:
            outpath = inpath
    else:
        outpath = os.path.dirname(outfile)
        outfile = os.path.basename(outfile)
    kwargs.update({
        'infile':infile,
        'inpath':inpath,
        'infile_full':os.path.join(inpath, infile),
        'outfile':outfile,
        'outpath':outpath,
        'outfile_full':os.path.join(outpath, outfile),
    })
    return kwargs

def build_avconv_str(**kwargs):
    kwargs.setdefault('libav_opts', '-vcodec copy -acodec copy')
    kwargs['libav_opts'] = kwargs.get('libav_opts')
    s = 'avconv -i "%(infile_full)s" %(libav_opts)s %(outfile_full)s'
    return s % (kwargs)


class FilePreprocessor(object):
    def __init__(self, **kwargs):
        self.infile = kwargs.get('infile')
        self.tempfn = '_temp'.join(os.path.splitext(self.infile))
        self.cmd_str = 'f4vpp -i %s -o %s' % (self.infile, self.tempfn)
    def __enter__(self, **kwargs):
        try:
            cmd_out = subprocess.check_output(self.cmd_str, shell=True)
            LOG(cmd_out)
        except subprocess.CalledProcessError:
            self.tempfn = self.infile
    def __exit__(self, *args, **kwargs):
        if self.tempfn != self.infile:
            os.remove(self.tempfn)
    
def convert_file(**kwargs):
    kwargs = handle_filenames(**kwargs)
    def handle_return(r, **rkwargs):
        if rkwargs.get('return_outfile'):
            return r, rkwargs['outfile_full']
    if os.path.exists(kwargs.get('outfile_full')) and not kwargs.get('overwrite'):
        LOG('%s exists.. skipping' % (kwargs.get('outfile')))
        return handle_return(False, **kwargs)
    pre_proc = FilePreprocessor(**kwargs)
    with pre_proc:
        avkwargs = kwargs.copy()
        avkwargs['infile'] = pre_proc.tempfn
        cmd_str = build_avconv_str(**avkwargs)
        try:
            cmd_out = subprocess.check_output(cmd_str, shell=True)
            LOG(cmd_out)
            r = True
        except subprocess.CalledProcessError:
            r = False
        return handle_return(r, **avkwargs)
    

def convert_dir(**kwargs):
    inpath = kwargs.get('inpath')
    outpath = kwargs.get('outpath')
    outext = kwargs.get('outext')
    if not outext:
        outext = 'mp4'
    if not outpath:
        outpath = inpath
    for fn in os.listdir(inpath):
        try:
            fext = os.path.splitext(fn)[1]
        except:
            fext = ''
        if 'f4v' not in fext:
            continue
        fkwargs = {'infile':os.path.join(inpath, fn), 'outpath':outpath, 'outext':outext}
        LOG('converting: ', fkwargs)
        convert_file(**fkwargs)

def main():
    p = argparse.ArgumentParser()
    for arg in ['infile', 'inpath', 'outfile', 'outpath', 'outext']:
        p.add_argument('--%s' % (arg), dest=arg)
    p.add_argument('--convert-dir', dest='convert_dir', action='store_true')
    p.add_argument('--overwrite', dest='overwrite', action='store_true')
    args, remaining = p.parse_known_args()
    o = vars(args)
    if o.get('convert_dir'):
        if not o.get('inpath'):
            o['inpath'] = os.getcwd()
        convert_dir(**o)
    else:
        if o.get('infile') and ',' in o.get('infile'):
            ckwargs = o.copy()
            for infile in o['infile'].split(','):
                ckwargs['infile'] = infile.strip()
                convert_file(**ckwargs)
        else:
            convert_file(**o)

if __name__ == '__main__':
    main()


