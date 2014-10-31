import os.path
import argparse

from virtualenvhandlers import VirtualEnv
from dependency.packagelist import build_from_list, parse_from_file, parse_from_string

def do_build(**kwargs):
    pkg_list = kwargs.get('pkg_list')
    venv_path = kwargs.get('venv_path')
    dry_run = kwargs.get('dry_run')
    pkg_mgr = build_from_list(*pkg_list)
    pkg_mgr.run(virtualenv_path=venv_path, dry_run=dry_run)
    
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--venv', dest='venv_path', help='virtualenv path')
    p.add_argument('--pkg-list', dest='pkg_list', help='list of packages, separated by comma')
    p.add_argument('--pkg-file', dest='pkg_file', help='file with package data')
    p.add_argument('--pkg-file-fmt', dest='pkg_file_fmt', help='data format of file (csv or json)', 
                   default='csv')
    p.add_argument('--dry-run', dest='dry_run', help='test mode - disables installation', action='store_true')
    args, remaining = p.parse_known_args()
    o = vars(args)
    venv = VirtualEnv(path=o['venv_path'], enable_creation=o['dry_run'] is not True)
    if o['pkg_file']:
        pkg_list = parse_from_file(o['pkg_file'], fmt=o['pkg_file_fmt'])
    else:
        pkg_list = [s.strip() for s in o['pkg_list'].split(',')]
    do_build(venv_path=venv.path, pkg_list=pkg_list, dry_run=o['dry_run'])
