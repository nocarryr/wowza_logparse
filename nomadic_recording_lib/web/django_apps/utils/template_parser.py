
class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
        
class ParsedVar(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.child_vars = {}
        self.parent_var = kwargs.get('parent_var')
        child_str = kwargs.get('child_str')
        if child_str:
            child_var = self.parse_child(child_str)
    def parse_child(self, parse_str):
        print '%s parsing child. str=%s' % (self, parse_str)
        parse_list = parse_str.split('.')
        name = parse_list[0]
        if len(parse_list):
            parse_list = parse_list[1:]
        child_str = '.'.join(parse_list)
        cvar = self.child_vars.get(name)
        if cvar is not None:
            print 'child found: %s' % (cvar)
            if not len(parse_list):
                print 'nothing left to parse. %s exists' % (cvar)
                return cvar
            new_cvar = cvar.parse_child(child_str)
            print '%s built: %s' % (cvar, new_cvar)
            return new_cvar
        cvar = ParsedVar(name, parent_var=self)
        print 'built own child: %s' % (cvar)
        self.child_vars[cvar.name] = cvar
        if child_str:
            return cvar.parse_child(child_str)
        return cvar
    @classmethod
    def parse(cls, parse_str, **kwargs):
        parse_list = parse_str.split('.')
        parent_var = kwargs.get('parent_var')
        root_var = kwargs.get('root_var')
        if parent_var is not None:
            print 'cls parse with parent var %s' % (parent_var)
            name = parse_list[0]
            if len(parse_list):
                parse_list = parse_list[1:]
            return parent_var.parse(name, child_str='.'.join(parse_list), parent_var=parent_var)
        if root_var is not None:
            cvar = root_var.parse_child(parse_str)
            print 'root returning %s' % (cvar)
            return cvar
        return cls(name, child_str=child_str)
    def get_root_obj(self):
        p = self.parent_var
        if p is None:
            return self
        return p.get_root_obj()
    def search_for_child(self, names=[]):
        if self.container is None:
            return None
        if not len(names):
            return None
        if names[0] != self.name:
            return None
        if len(names) == 1:
            return self, names
        names = names[1:]
        cvar = self.child_vars.get(names[0])
        if cvar is None:
            return None
        return cvar.search_for_child(names)
    def get_parsed(self):
        if self.child_var is not None:
            return {self.name:self.child_var.get_parsed()}
        return self.name
    def get_parsed_str(self, separator='.'):
        s = self.name
        p = self.parent_var
        if p is not None and p.parent_var is not None:
            s = separator.join([p.get_parsed_str(separator), s])
        return s
    def __repr__(self):
        return 'ParsedVar: %s' % (self)
    def __str__(self):
        return self.get_parsed_str()
        
class ParsedObject(object):
    def __init__(self, **kwargs):
        self.template = kwargs.get('template')
        self.start_index = kwargs.get('start_index')
        self.end_index = kwargs.get('end_index')
        self.parsed_var = self.build_parsed_var()
        print kwargs
        print '[%s]' % (self.template_chunk)
    @classmethod
    def parse(cls, **kwargs):
        template = kwargs.get('template')
        start = kwargs.get('start_index')
        end = None
        new_cls = None
        chunk = template.template_string[start:]
        if len(chunk) >= 2 and chunk[:3] == '{{ ':
            if ' }}' not in chunk:
                raise ParseError('no end tag found')
            new_cls = TaggedObject
            end = chunk.index(' }}') + 2 + start
        else:
            new_cls = UnTaggedObject
            if '{{ ' in chunk:
                end = chunk.find('{{ ') + start - 1
            else:
                end = len(template.template_string) - 1
        if new_cls is None or end is None:
            raise ParseError('could not figure stuff out')
        new_kwargs = dict(template=template, start_index=start, end_index=end)
        return new_cls(**new_kwargs)
    @property
    def template_chunk(self):
        tmp_str = self.template.template_string
        if not tmp_str:
            return None
        return tmp_str[self.start_index:self.end_index+1]
    def build_parsed_var(self):
        return None
    def get_parsed_var(self):
        if isinstance(self.parsed_var, ParsedVar):
            return self.parsed_var.get_parsed()
        return None
    def __repr__(self):
        return '%s: (%s, %s)' % (self.__class__.__name__, self.start_index, self.end_index)
        
class UnTaggedObject(ParsedObject):
    pass
    
class TaggedObject(ParsedObject):
    def __init__(self, **kwargs):
        super(TaggedObject, self).__init__(**kwargs)
        
    def build_parsed_var(self):
        chunk = self.template_chunk
        chunk = chunk.lstrip('{{ ').rstrip(' }}')
        return ParsedVar.parse(chunk, root_var=self.template.parsed_vars)
        
class Template(object):
    def __init__(self, template_str=None, **kwargs):
        self._template_string = None
        self.parsed_vars = ParsedVar('')
        self.parsed_objects = {}
        self.template_string = template_str
    @property
    def template_string(self):
        return self._template_string
    @template_string.setter
    def template_string(self, value):
        if value == self._template_string:
            return
        self._template_string = value
        self.parse_template()
    def parse_template(self):
        self.parsed_objects.clear()
        tmp_str = self.template_string
        i = 0
        while i <= len(tmp_str) - 1:
            print i
            obj = ParsedObject.parse(template=self, start_index=i)
            #if obj.start_index in self.parsed_objects:
            #    break
            self.parsed_objects[obj.start_index] = obj
            i = obj.end_index + 1
    def get_parsed_vars(self):
        d = {'single':set(), 'complex':[]}
        for i, obj in self.parsed_objects.iteritems():
            v = obj.parsed_var
            vdata = obj.get_parsed_var()
            if vdata is None:
                continue
            if isinstance(vdata, basestring):
                d['single'].add(vdata)
            else:
                d['single'].add(v.name)
                d['complex'].append(vdata)
        return d

class ValueObject(object):
    def __init__(self, **kwargs):
        self.start_index = None
        self.end_index = None
        self.parser = kwargs.get('parser')
        self.parsed_object = kwargs.get('parsed_object')
    @classmethod
    def new(cls, **kwargs):
        obj = kwargs.get('parsed_object')
        new_cls = UnTaggedValueObject
        if isinstance(obj, TaggedObject):
            new_cls = TaggedValueObject
        return new_cls(**kwargs)
    def get_chunk(self):
        s = self.parser.string_to_parse
        start = self.start_index
        end = self.end_index
        if end is None:
            end = len(s) - 1
        return s[start:end+1]
    def get_parsed_value(self):
        return self.parsed_object.parsed_var, self.get_chunk()
    def calc_indecies(self, allow_str_search=False):
        start = self.start_index
        end = self.end_index
        if None not in [start, end]:
            return True
        last_key, next_key = self.get_neighbor_keys()
        if start is None:
            start = self.start_index = self.calc_start_index(last_key, 
                                                             next_key, 
                                                             allow_str_search)
        if end is None:
            end = self.end_index = self.calc_end_index(last_key, 
                                                       next_key, 
                                                       allow_str_search)
        if last_key is not None and start is None:
            return False
        if next_key is not None and end is None:
            return False
        return True
    def calc_start_index(self, last_key, next_key, allow_str_search=False):
        if last_key is None:
            return 0
        last_obj = self.parser.value_objects[last_key]
        if last_obj.end_index is None:
            return None
        return last_obj.end_index + 1
    def get_neighbor_keys(self):
        start = self.parsed_object.start_index
        all_keys = sorted(self.parser.value_objects.keys())
        i = all_keys.index(start)
        if i == 0:
            last_key = None
        else:
            last_key = all_keys[i-1]
        if i+1 >= len(all_keys):
            next_key = None
        else:
            next_key = all_keys[i+1]
        return last_key, next_key
    def __repr__(self):
        return '%s: (%s, %s)' % (self.__class__.__name__, self.start_index, self.end_index)
class UnTaggedValueObject(ValueObject):
    def calc_start_index(self, last_key, next_key, allow_str_search=False):
        start = super(UnTaggedValueObject, self).calc_start_index(last_key, 
                                                                  next_key, 
                                                                  allow_str_search)
        if start is not None:
            return start
        if not allow_str_search:
            return start
        def raise_exc():
            raise ParseError('Un-tagged string %s does not exist' % (search_str))
        search_str = self.parsed_object.template_chunk
        parse_str = self.parser.string_to_parse
        if search_str not in parse_str:
            raise_exc()
        highest_known = 0
        for vkey in sorted(self.parser.value_objects.keys()):
            vobj = self.parser.value_objects[vkey]
            if vobj == self:
                break
            if vobj.end_index is not None and vobj.end_index > highest_known:
                highest_known = vobj.end_index
                continue
            if vobj.start_index is not None and vobj.start_index > highest_known:
                highest_known = vobj.start_index
        start = parse_str.find(search_str, highest_known)
        if start < 0:
            raise_exc()
        return start
    def calc_end_index(self, last_key, next_key, allow_str_search=False):
        if next_key is None:
            return None
        pobj = self.parsed_object
        if None in [self.start_index, pobj.start_index, pobj.end_index]:
            return None
        return self.start_index + (pobj.end_index - pobj.start_index)
class TaggedValueObject(ValueObject):
    def calc_end_index(self, last_key, next_key, allow_str_search=False):
        if next_key is None:
            return None
        next_obj = self.parser.value_objects[next_key]
        if next_obj.start_index is None:
            return None
        return next_obj.start_index - 1
    
        
class TemplatedStringParser(object):
    def __init__(self, **kwargs):
        self.value_objects = {}
        self._template = None
        self._string_to_parse = None
        self.parse_success = None
        self.template = kwargs.get('template')
        self.string_to_parse = kwargs.get('string_to_parse')
    @property
    def template(self):
        return self._template
    @template.setter
    def template(self, value):
        if value == self._template:
            return
        if isinstance(value, basestring):
            value = Template(value)
        self._template = value
        self._rebuild_objects()
    @property
    def string_to_parse(self):
        return self._string_to_parse
    @string_to_parse.setter
    def string_to_parse(self, value):
        if value == self._string_to_parse:
            return
        self._string_to_parse = value
        self._rebuild_objects()
    def _rebuild_objects(self):
        if None in [self.template, self.string_to_parse]:
            return
        self.value_objects.clear()
        self.build_value_obj()
        r = self.calc_value_obj_indecies()
        if not r:
            r = self.calc_value_obj_indecies(allow_str_search=True)
        self.parse_success = r
    def build_value_obj(self):
        parsed_objects = self.template.parsed_objects
        value_objects = self.value_objects
        last_vobj = None
        for i in sorted(parsed_objects.keys()):
            pobj = parsed_objects[i]
            vobj = ValueObject.new(parser=self, parsed_object=pobj)
            value_objects[i] = vobj
        last_index = len(self.string_to_parse) - 1
        value_objects[max(value_objects.keys())].end_index = last_index
    def calc_value_obj_indecies(self, allow_str_search=False):
        value_objects = self.value_objects
        keys = sorted(value_objects.keys())
        loop_max = 10
        i = 0
        print 'calculating indecies...'
        while i <= loop_max:
            print 'loop iter:', i
            calc_complete = True
            for key in keys:
                vobj = value_objects[key]
                r = vobj.calc_indecies(allow_str_search)
                print '%r calc result: %s' % (vobj, r)
                if r is False:
                    calc_complete = False
            if calc_complete:
                print 'calculation complete. exiting at iteration:', i
                break
            i += 1
        print 'loop exit. iter=%s, result=%s' % (i, calc_complete)
        return calc_complete
    def get_parsed_values(self):
        d = {}
        for i, vobj in self.value_objects.iteritems():
            if isinstance(vobj, UnTaggedValueObject):
                continue
            pvar, pval = vobj.get_parsed_value()
            qstr = pvar.get_parsed_str()
            if qstr in d:
                if d[qstr] == pval:
                    continue
                raise ParseError('unmatched values for %s: [%s, %s]' % (qstr, d[qstr], pval))
            d[qstr] = pval
        return d
        
def test():
    import traceback
    template_string = '{{ a_variable.a_attribute }} some text {{ b_variable.b_attribute }} more text {{ c_variable }}'
    parse_string = 'AVal some text BVal more text CVal'
    parser = TemplatedStringParser(template=template_string)
    try:
        parser.string_to_parse = parse_string
    except:
        traceback.print_exc()
        return parser
    return parser
