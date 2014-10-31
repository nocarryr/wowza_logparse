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
# category.py
# Copyright (c) 2010 - 2011 Matthew Reid

from BaseObject import BaseObject
from misc import setID

class Category(BaseObject):
    _saved_class_name = 'Category'
    _saved_attributes = ['name', 'id', 'parent_id', 'members_id']
    _saved_child_objects = ['subcategories']
    def __init__(self, **kwargs):
        self.subcategories = {}
        self.parent = kwargs.get('parent')
        super(Category, self).__init__(**kwargs)
        self.register_signal('obj_update_needed', 'member_update', 'subcategory_added')
        
        if 'deserialize' not in kwargs:
            self.name = kwargs.get('name')
            self.id = setID(kwargs.get('id'))
            self.members_id = kwargs.get('members_id', set())
        if not hasattr(self, 'members'):
            self.members = set()
        if not hasattr(self, 'members_id'):
            self.members_id = set()
        
    @property
    def parent_id(self):
        if self.parent:
            return self.parent.id
        return self._parent_id
    @parent_id.setter
    def parent_id(self, value):
        self._parent_id = value
        
#    def _check_member_obj(self):
#        obj_ids = set()
#        for member in self.members:
#            obj_ids.add(member.id)
#        for id in set(self.members_id):
#            if id not in obj_ids:
#                self.emit('obj_update_needed', category_id=self.id, obj_id=id, 
#                          callback=self._obj_update_return)
    def add_subcategory(self, **kwargs):
        kwargs.setdefault('parent', self)
        category = Category(**kwargs)
        self.subcategories.update({category.id:category})
        self.emit('subcategory_added', category=self, subcategory=category)
        return category
        
    def del_subcategory(self, **kwargs):
        category = kwargs.get('category')
        id = kwargs.get('id')
        if not category:
            category = self.find_category(id=id)
        for member in category.members.copy():
            category.del_member(member)
        for subcat in category.subcategories.values()[:]:
            category.del_subcategory(category=subcat)

    def add_member(self, obj=None, **kwargs):
        id = kwargs.get('id', None)
        if obj is not None:
            self.members.add(obj)
            #self.members_id.add(obj.id)
            if self.name not in obj.categories:
                obj.add_category(self)
            self.emit('member_update', category_id=self.id, category=self, obj=obj, state=True)
        else:
            #self.members_id.add(id)
            self.emit('obj_update_needed', category_id=self.id, obj_id=id, callback=self._obj_update_return)
            
    def del_member(self, obj=None, **kwargs):
        id = kwargs.get('id', None)
        if obj is None:
            for member in self.members:
                if member.id == id:
                    obj = member
        self.members.discard(obj)
        #self.members_id.discard(obj.id)
        if self.id in obj.categories:
            obj.remove_category(self)
        self.emit('member_update', category_id=self.id, obj_id=obj.id, state=False)
        
    def find_category(self, **kwargs):
        id = kwargs.get('id')
        name = kwargs.get('name')
        if id:
            if id == self.id:
                return self
            if id in self.subcategories:
                return self.subcategories[id]
        if name is not None and name == self.name:
            return self
        for category in self.subcategories.itervalues():
            result = category.find_category(**kwargs)
            if result:
                return result
        return False
        
    def _deserialize_child(self, d):
        c = Category(deserialize=d, parent=self.parent)
        self.emit('subcategory_added', category=self, subcategory=category)
        return c
        
#    def _obj_update_return(self, **kwargs):
#        id = kwargs.get('id')
#        obj = kwargs.get('obj')
#        #print 'obj_update_return: ', id, obj
#        if obj is None:
#            self.members_id.discard(id)
#        elif id in self.members_id:
#            self.add_member(obj)
#            #self.members.add(obj)
#            #self.emit('member_update', category_id=self.id, obj_id=obj.id, state=True)
