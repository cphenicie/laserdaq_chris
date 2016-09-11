# A group of functions to do common data organization tasks

### Functions ###
# makeFilePath: Make a string for a file path indexed by today's date. If the path does not exist, create it
# saveData: Given an array of data and a list of variable names corresponding to columns in the array, save the data
#           (and optional metadata) in a specified file

import datetime
import os
import scipy.io as sio

def makeFilePath():
    td = datetime.date.today()
    year = str(td.year)
    if td.month < 10:
        month = "0" + str(td.month)
    else:
        month = str(td.month)
    if td.day < 10:
        day = "0" + str(td.day)
    else:
        day = str(td.day)
    filePath = r"I:\\thompsonlab\\REI\\Daily\\%s\\%s-%s\\%s%s%s\\" % (year, year, month, year, month, day)
    if not os.path.exists(filePath):
        os.makedirs(filePath)

    return filePath

# Given a matrix of data where each data set is in its own column, and given a list of names that corresponds to each
# column in the data set, save a .mat file with the data labelled by its name
def saveData(data, names, file, metadata):
    # Create a dictionary where the data is referenced by the desired variable name
    dataDict = {}
    cols = range(len(names))
    for name, col in zip(names, cols):
        dataDict[name.replace(" ", "")] = data[:, col] # Make sure none of the names have spaces in them

    # If we are going to overwrite a file, append _1 or _2, ... or _n until so we don't overwrite data
    if os.path.isfile(file+".mat"):
        i = 1
        origDir = file
        while os.path.exists(file+".mat"):
            file = origDir + "_" + str(i)
            i = i + 1
        print("You tried to overwrite data, I'm actually saving this as " + file + ".mat")

    sio.savemat(file, dataDict)
    if metadata:
        txt = open(file + '.txt', 'w')
        txt.write(metadata)
        txt.close()