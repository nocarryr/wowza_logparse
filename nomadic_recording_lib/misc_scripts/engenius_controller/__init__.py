from telnet_io import TelnetIO, TelnetThread
from cli_commands import build_tree
from conf import parse_conf

def do_build(config, threaded=False):
    if threaded:
        cls = TelnetThread
        config['commands']['threaded'] = True
    else:
        cls = TelnetIO
    tn_io = cls(**config['telnet'])
    tn_io.commands = build_tree(**config['commands'])
    tn_io.run()
    return tn_io

def main(**kwargs):
    conf_fn = kwargs.get('conf_file')
    config = kwargs.get('config')
    if conf_fn:
        config = parse_conf(conf_fn)
    if config.get('access_points') is not None:
        for a_id, aconfig in config['access_points']:
            do_build(aconfig, threaded=True)
    else:
        do_build(**config)
