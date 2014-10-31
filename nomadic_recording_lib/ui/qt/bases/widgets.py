from PyQt4 import QtCore
from PyQt4.QtGui import *

class Label(QLabel):
    def set_text(self, text):
        self.setText(text)
        
class LayoutMixIn(object):
    def pack_start(self, *args, **kwargs):
        self.addWidget(*args, **kwargs)
    def remove(self, *args, **kwargs):
        self.removeWidget(*args, **kwargs)
        
class HBox(QHBoxLayout, LayoutMixIn):
    pass
class VBox(QVBoxLayout, LayoutMixIn):
    pass
    
class HPane(HBox):
    pass
class VPane(VBox):
    pass

class Frame(QGroupBox, LayoutMixIn):
    def __init__(self, **kwargs):
        s = kwargs.get('label', '')
        layout = kwargs.get('topwidget', VBox)
        super(Frame, self).__init__(s, **kwargs)
        self.setLayout(layout())
        self.topwidget = layout
    def set_label(self, label):
        self.setTitle(label)
        
class ScrolledWindow(QScrollArea):
    def pack_start(self, *args, **kwargs):
        self.widget().addWidget(*args, **kwargs)
    def remove(self, *args, **kwargs):
        self.widget().removeWidget(*args, **kwargs)
    
class Table(QGridLayout, LayoutMixIn):
    def do_add_widget(self, widget, loc, **kwargs):
        self.addWidget(widget, loc[1], loc[0], **kwargs)
    def do_child_loc_update(self, widget, loc):
        ## TODO: find a way to relocate children
        pass

class ColorSelection(Color):
    def setup_widgets(self, **kwargs):
        self.topwidget = Frame()
        
class ColorBtn(Color):
    def setup_widgets(self, **kwargs):
        self.widget = Button()
        self.topwidget = self.widget
    
class Entry(EntryBuffer):
    def setup_widgets(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.topwidget = Frame(label=self.name)
        self.widget = QLineEdit()
        self.widget.connect('editingFinished', self.on_editingFinished)
        self.topwidget.pack_start(self.widget)
    
    def get_widget_text(self):
        return self.widget.text()
        
    def set_widget_text(self, text):
        self.widget.setText(text)
    
    def on_editingFinished(self):
        self.set_object_text(self.get_widget_text())
        

class SpinBtn(Spin):
    def setup_widgets(self, **kwargs):
        self.widget = QSpinBox()
        range = [kwargs.get(key) for key in ['value_min', 'value_max']]
        self.widget.setRange(*range)
        value = self.get_object_value()
        if value is not None:
            self.widget.setValue(value)
        self.widget.connect('valueChanged', self.on_widget_value_changed)
    def set_widget_value(self, value):
        self.widget_value_set_by_program = True
        self.widget.setValue(value)
    def on_widget_value_changed(self, value):
        if not self.widget_value_set_by_program:
            self.set_object_value(value)
        self.widget_value_set_by_program = False
    
class Button(QPushButton):
    pass
    
class ToggleBtn(Toggle):
    def setup_widgets(self, **kwargs):
        self.widget = Button(**kwargs)
        self.widget.setCheckable(True)
    def get_widget_state(self):
        return self.widget.isChecked()
    def set_widget_state(self, state):
        self.widget.setChecked(state)

orientation_map = {'horizontal':QtCore.Qt.Horizontal, 
                   'vertical':QtCore.Qt.Vertical}
class Slider(Fader):
    def setup_widgets(self, **kwargs):
        self.widget = QSlider(orientation_map[self.orientation])
        range = [self.ui_scale[key] for key in ['min', 'max']]
        self.widget.setRange(*range)
        self.widget.connect('sliderMoved', self.on_widget_change_value)
        self.widget.connect('sliderPressed', self.on_widget_button_press)
        self.widget.connect('sliderReleased', self.on_widget_button_release)
        
    def set_widget_value(self, value):
        self.widget.setValue(value)
        
    def on_widget_change_value(self, value):
        self.scaler.set_value('ui', value)
    
class HSlider(Slider):
    orientation = 'horizontal'
    
class VSlider(Slider):
    orientation = 'vertical'
