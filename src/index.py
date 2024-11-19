from ktv_extractor import model
from ktv_extractor.process import index
import sys
import os

model.init()

counter = 0

for dirpath, dirnames, filenames in os.walk(sys.argv[1]):
    for filename in filenames:
        if filename.endswith('.mkv'):
            counter = counter + 1
            index(os.path.join(dirpath, filename))
            if counter % 1000 == 0:
                print('processed %d' % (counter))