import os
import json

def parse_interface(**kwargs):
    string = kwargs.get('string')
    filename = kwargs.get('filename')
    if not string:
        file = open(filename, 'r')
        l = file.readlines()
        file.close()
        string = ''.join([line.strip() for line in l])
        
    script, j = find_pages(string)
    pages = parse_json(j)
    return dict(script=script, jsonstring=j, pages=pages)
    
def find_pages(string):
    i = string.find('pages')
    script = string[:i]
    s = string[i:]
    i = s.find('[')
    j = s[i:].strip(';')
    return script, j
    
def parse_json(string):
    return json.loads(string)
    
def build_json(obj, **kwargs):
    js_kwargs = kwargs.get('js_kwargs', dict(separators=(',', ':')))
    s = json.dumps(obj, **js_kwargs)
    return "'".join(s.split('"'))
    

def build_interface(**kwargs):
    script = kwargs.get('script')
    pages = kwargs.get('pages')
    j = 'pages=%s;' % (build_json(pages, **kwargs))
    
    return ''.join([script, j])
    
def set_script_vars(script, **kwargs):
    for key, val in kwargs.iteritems():
        if key in script:
            start = script.find(key)
            end = script.find(';', start)
            s1 = script[:start]
            s2 = script[end+1:]
            script = '%s%s="%s";%s' % (s1, key, val, s2)
        else:
            script = '%s%s=%s;' % (script, key, val)
    return script

def load_template(filename=None):
    if not filename:
        filename = os.path.join(os.path.dirname(__file__), 'template.js')
    return parse_interface(filename=filename)
    


if __name__ == '__main__':
    dir = os.path.dirname(__file__)
    d = parse_interface(filename=os.path.join(dir, 'template.js'))
#    d['pages'][0].append(dict(name='testbutton',
#                              type='Button',
#                              mode='momentary', 
#                              address='/DWT-iPad/testbutton', 
#                              x=0,y=0,width=.25,height=.25))
    s = build_interface(**d)
    
    file = open(os.path.join(dir, 'test_template.js'), 'w')
    file.write(s)
    file.close()
    
    
    
