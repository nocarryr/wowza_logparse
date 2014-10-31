#from pygame_midiIO import PyGameMidiIO

#MidiIO = PyGameMidiIO

#from portmidizero_midiIO import pmzMidiIO

#MidiIO = pmzMidiIO

try:
    from pyportmidi_midiIO import pypmMidiIO
    MidiIO = pypmMidiIO
    IO_LOADER = MidiIO
except:
    pass



#from rtmidi_midiIO import rtmMidiIO

#MidiIO = rtmMidiIO


