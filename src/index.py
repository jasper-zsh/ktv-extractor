from ktv_extractor import model
from ktv_extractor.process import index
import sys
import os

model.init()

for dirpath, dirnames, filenames in os.walk(sys.argv[1]):
    for filename in filenames:
        if filename.endswith('.mkv'):
            index(os.path.join(dirpath, filename))