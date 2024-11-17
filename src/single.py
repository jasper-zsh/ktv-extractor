from ktv_extractor import model
from ktv_extractor.process import index
import sys

model.init()
index(sys.argv[1])