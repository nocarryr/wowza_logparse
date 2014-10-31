

class ScriptBase(object):
    def __init__(self, **kwargs):
        '''
        parameters:
            name: str
            raw_value: str, if not None, this will override all other functionality
        '''
        self.name = kwargs.get('name')
        self.parent_obj = kwargs.get('_InitScript_Parent_Obj_')
        self.raw_value = kwargs.get('raw_value')
    def add_child(self, **kwargs):
        '''Used by subclasses to update init kwargs for child objects
        '''
        kwargs.setdefault('_InitScript_Parent_Obj_', self)
        return kwargs
    def get_value(self):
        '''Primary method for data retreival.  Subclasses should not override this.
        '''
        v = self.raw_value
        if v is not None:
            return v
        return self.build_value()
    def build_value(self):
        '''Method used by subclasses to build properly formatted data.
        '''
        return ''
        
class InitScript(ScriptBase):
    '''Main class used to generate a cloud-init script.  I realize this is
    merely creating a yaml document and there are libraries for this, but
    it seemed to be overkill (maybe).
    '''
    def __init__(self, **kwargs):
        super(InitScript, self).__init__(**kwargs)
        self.script_type = kwargs.get('script_type', 'cloud_config')
        self.script_options = kwargs.get('script_options', {})
        self.script = None
        self.sections = {}
        self.section_order = []
        section_data = kwargs.get('sections', {})
        for key, val in section_data.iteritems():
            val.setdefault('name', key)
            self.add_section(**val)
    def add_section(self, **kwargs):
        kwargs = self.add_child(**kwargs)
        s = ScriptSection(**kwargs)
        self.sections[s.name] = s
        if s.name not in self.section_order:
            self.section_order.append(s.name)
        return s
    def build_script_obj(self, **kwargs):
        skwargs = self.script_options.copy()
        skwargs.update(kwargs)
        skwargs['script_obj'] = self
        cls = SCRIPT_TYPES[self.script_type]
        s = self.script = cls(**skwargs)
        return s
    def build_script(self, **kwargs):
        s = self.script
        if s is None:
            s = self.build_script_obj(**kwargs)
        return s.build_script()
    def build_value(self):
        lines = []
        sections = self.sections
        for sname in self.section_order:
            section = sections.get(sname)
            if section is None:
                continue
            lines.append(section.get_text())
        return '\n'.join(lines)

class ScriptWithItems(ScriptBase):
    '''Base class for objects that can include items using 'ScriptItem'
    '''
    def __init__(self, **kwargs):
        super(ScriptWithItems, self).__init__(**kwargs)
        self.items = []
        items = kwargs.get('items', [])
        for item_data in items:
            self.add_item(**item_data)
    def add_item(self, **kwargs):
        kwargs = self.add_child(**kwargs)
        item = ScriptItem(**kwargs)
        self.items.append(item)
        return item
        
class ScriptSection(ScriptWithItems):
    def __init__(self, **kwargs):
        super(ScriptSection, self).__init__(**kwargs)
    def build_value(self):
        lines = []
        lines.append('%s:' % (self.name))
        prefix = '  '
        for item in self.items:
            lines.append(prefix + item.get_text())
        return '\n'.join(lines)
        
class ScriptItem(ScriptWithItems):
    def __init__(self, **kwargs):
        super(ScriptItem, self).__init__(**kwargs)
        self.value = kwargs.get('value')
    def build_value(self):
        lines = []
        if len(self.items):
            for i, item in enumerate(self.items):
                if i == 0:
                    prefix = '- '
                else:
                    prefix = '  '
                lines.append(prefix + item.get_text())
        else:
            lines.append('- %s: %s' % (self.name, self.value))
        return '\n'.join(lines)
        
class ScriptType(object):
    def __init__(self, **kwargs):
        self.script_obj = kwargs.get('script_obj')
    def build_script(self):
        s = self.first_line + '\n'
        s += self.script_obj.get_text()
        return s
    
class ScriptTypeUserData(ScriptType):
    name = 'user_data'
    mime_type = 'text/x-shellscript'
    first_line = '#!/bin/sh'
    
class ScriptTypeInclude(ScriptType):
    name = 'include'
    mime_type = 'text/x-include-url'
    first_line = '#include'
    
class ScriptTypeCloudConfig(ScriptType):
    name = 'cloud_config'
    mime_type = 'text/cloud-config'
    first_line = '#cloud-config'
    
    
SCRIPT_TYPES = {}
def build_script_types(*args):
    global SCRIPT_TYPES
    default_cls = [ScriptTypeUserData, ScriptTypeInclude, ScriptTypeCloudConfig]
    if not SCRIPT_TYPES:
        for cls in default_cls:
            SCRIPT_TYPES[cls.name] = cls
    for cls in args:
        SCRIPT_TYPES[cls.name] = cls
    
build_script_types()
