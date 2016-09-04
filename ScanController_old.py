# Things to add: Read the laser current and put that in the metadata
#                Automaitcally make folder if not exist

import sys
from PyQt4 import QtCore, QtGui, uic
import PyDAQmx as pydaqmx  # Python library to execute NI-DAQmx code
import pydaqshortcuts
import numpy as np
import re
import scipy.io as sio
import datetime
import telnetlib
import time
import ctypes

### Hard-coded variables ###
dev = "Dev1/"
startTrig = "PFI0"
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
waveOffset = 5  # How far away from the actual starting wavelength (in nm) we will initially slew the laser
#############################
qtCreatorFile = "ScanUI.ui"  # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)




class thread_CollectAnalogIn(QThread):
    def __init__(self, GUIObj, taskHandle, dataBuffer):
        QThread.__init__(self)
        # Initialize variables fed from the GUI object
        self.GUIObj = GUIObj
        self.taskHandle = taskHandle
        self.dataBuffer = dataBuffer

        # Initialize some hard-coded variables
        self.read = pydaqmx.int32()
        self.nSampsPerChan = -1  # -1 in finite mode means wait until all samples are collected and read them
        self.timeout = -1  # -1 means wait indefinitely to read the samples
        self.fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies that dataBuffer will be divided into continuous blocks of data for each channel (rather than interleaved)
        self.arrSize = pydaqmx.uInt32(len(self.dataBuffer))
        self.sampsPerChanRead = ctypes.byref(self.read)

    def run(self):
        self.GUIObj.tn.write("(exec 'laser1:ctl:scan:start) \r\n")
        pydaqmx.DAQmxStartTask(self.taskHandle)
        pydaqmx.DAQmxReadBinaryI16(self.taskHandle, self.nSampsPerChan, self.timeout, self.fillMode, self.dataBuffer, self.arrSize, self.sampsPerChanRead, None)
        pydaqmx.DAQmxStopTask(self.taskHandle)

        self.emit(SIGNAL('plot_data(PyQt_PyObject)'), self.dataBuffer)



class thread_CheckScanProgress(QThread):
    def __init__(self, GUIObj):
        QThread.__init__(self)
        self.GUIObj = GUIObj
        self.tn = GUIObj.tn
        #self.stillWorking = True
        global stillWorking
        stillWorking = True

    def run(self):
        global stillWorking
        #while self.stillWorking:
        while stillWorking:
            time.sleep(1)  # Wait until the progress has definitely started before we start checking progress
            self.tn.read_very_eager()  # Clear out the buffer
            self.tn.write("(param-disp 'laser1:ctl:scan:progress) \r\n")
            time.sleep(.03)  # Wait until the laser can respond fully
            reList = ["progress = "]
            self.tn.expect(reList, 1)  # Wait up to 1 second to receive a message containing a string in reList
            output = self.tn.read_very_eager()
            #print("length of output = " + str(len(output)))
            if len(output) == 6:  # Progress is one digit (There are 5 characters after the progress value)
                print("Laser says \"" + output[0] + "\"")
                if int(output[0]) == 0:
                    print("I'm 0")
                    #self.stillWorking = False
                    stillWorking = False
            else:
                print("Laser says \"" + output[0:2] + "\"")




class thread_WaitForSlew(QThread):
    def __init__(self, GUIObj):
        QThread.__init__(self)
        self.GUIObj = GUIObj
        #self.tn = GUIObj.tn


    def run(self):
        self.GUIObj.tn.read_very_eager()  # Clear out the buffer
        reList = ["wavelength-act = "]  # The expression we will look for in the output of the laser, we will end up basically deleting all the text up to and including this
        timeWait = 30  # The time we will wait for the laser to slew to the correct wavelength
        while timeWait > 0:
            self.GUIObj.tn.write("(param-disp 'laser1:ctl:wavelength-act) \r\n")
            time.sleep(.03)
            self.GUIObj.tn.expect(reList, 1)  # Wait up to 1 second to receive a message containing a string in reList
            waveActStr = self.GUIObj.tn.read_very_eager()  # The beginning of the buffer is now the wavelength
            if waveActStr == '':
                waveAct = 0  #  Arbitrary choice, anything would work as long as it's guaranteed not to be within 0.1nm of the set starting point
            else:
                waveAct = float(waveActStr[0:6])  # Just take up to the first decimal

            if abs(waveAct - (self.GUIObj.startWave - waveOffset)) < 0.1:
                timeWait = 0
            else:
                # print("Difference = " + str(waveAct - self.startWave - waveOffset) + " , timeWait = " + str(timeWait) )
                timeWait = timeWait - 1
                time.sleep(1)
                if timeWait <= 0:
                    print(
                    "After 30 seconds we still aren't at the starting wavelength, code will now crash. Have a nice day!")




class MyApp(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        self.updateMetadata()
        self.startWaveSpinBox.valueChanged.connect(self.updateMetadata)
        self.endWaveSpinBox.valueChanged.connect(self.updateMetadata)
        self.scanRateSpinBox.valueChanged.connect(self.updateMetadata)
        self.sampleRateSpinBox.valueChanged.connect(self.updateMetadata)
        self.inputsTextEdit.textChanged.connect(self.updateMetadata)
        self.fileNameLineEdit.textChanged.connect(self.updateMetadata)

        self.startScanButton.clicked.connect(self.startScan)

    def updateMetadata(self):
        self.metadataTextEdit.setPlainText("Starting wavelength (nm) = " + str(self.startWaveSpinBox.value()))
        self.metadataTextEdit.appendPlainText("Ending wavelength (nm) = " + str(self.endWaveSpinBox.value()))
        self.metadataTextEdit.appendPlainText("Scan Rate (nm/s) = " + str(self.scanRateSpinBox.value()))
        self.metadataTextEdit.appendPlainText("Sampling Rate (samples/s) = " + str(self.sampleRateSpinBox.value()))
        self.metadataTextEdit.appendPlainText("\nInput configuration: \n" + str(self.inputsTextEdit.toPlainText()))

    def initializeData(self):

        # Store the variables that will be used durign this data run
        self.startWave = self.startWaveSpinBox.value()
        self.endWave = self.endWaveSpinBox.value()
        self.scanRate = self.scanRateSpinBox.value()
        self.sampleRate = self.sampleRateSpinBox.value()
        self.inputs = self.inputsTextEdit.toPlainText()
        self.fileName = self.fileNameLineEdit.text()
        self.metadata = self.metadataTextEdit.toPlainText()

        # Configure the graph choices comboBoxes
        self.aiPorts = list()
        self.aiNames = list()
        self.graphChoices1.clear()
        self.graphChoices2.clear()
        self.graphChoices3.clear()

        self.inputs = self.inputsTextEdit.toPlainText()
        textLines = self.inputs.split('\n')
        for line in textLines:
            splitLine = line.split(':')
            if len(splitLine) == 2:  # In case there are trailing new lines
                self.aiPorts.append(
                    str.strip(str(splitLine[0])))  # str.strip() gets rid of any leading an trailing spaces
                self.aiNames.append(str.strip(str(splitLine[1])))
                self.graphChoices1.addItem(str.strip(str(splitLine[1])))
                self.graphChoices2.addItem(str.strip(str(splitLine[1])))
                self.graphChoices3.addItem(str.strip(str(splitLine[1])))

        # Initialize some dictionaries to link variables to the port names
        self.aiNameDict = {}
        portString = ""
        for port, name in zip(self.aiPorts, self.aiNames):
            self.aiNameDict[port] = name
            portString += (dev + port + ", ")

        portString = portString[:-2]  # Since we will have a trailing ", " at the end

        ## Configure the Analog Input lines
        self.fSampPerChan = self.sampleRate / len(self.aiPorts)
        self.tSamp = abs(self.endWave - self.startWave) / self.scanRate
        self.nSampPerChan = int(self.tSamp * self.fSampPerChan)  # pydaqmx.uInt64 can only accept integer inputs

        self.readAI = pydaqmx.TaskHandle()
        pydaqshortcuts.makeAnalogIn(portString, self.readAI, self.fSampPerChan, self.nSampPerChan)
        pydaqmx.DAQmxCfgDigEdgeStartTrig(self.readAI, startTrig,
                                         pydaqmx.DAQmx_Val_Rising)  # Trigger to actually start collecting data

    def initializeLaser(self):
        self.tn = telnetlib.Telnet("10.0.0.2", 1998)
        time.sleep(.1)
        self.tn.write("(param-set! 'laser1:ctl:wavelength-set '" + str(self.startWave - waveOffset) + ") \r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:wavelength-begin '" + str(self.startWave - waveOffset) + ") \r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:wavelength-end '" + str(self.endWave) + ")\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:trigger:output-enabled '#t)\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:trigger:output-threshold '" + str(self.startWave) + ")\r\n")
        self.tn.write("(param-set! 'laser1:scan:enabled '#f)\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:speed '" + str(self.scanRate) + ")\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:microsteps '#t)\r\n")
        # self.tn.write("(param-set! 'laser1:dl:cc:current-set '" + str(current) + ")\r\n")
        # self.tn.write("(param-set! 'laser1:dl:cc:enabled '#t)\r\n")
        time.sleep(1)

    def stoptask(self):
        self.tn.write("(param-disp 'laser1:ctl:scan:progress) \r\n")
        time.sleep(.03)

        # take output and strip extra spaces
        output = self.tn.read_very_eager()
        output = output.replace(" ", "")

        # collect scan progress from the Telnet prompt
        searchobj = re.search('(?<=:progress=)\d+', output, re.MULTILINE)
        try:
            if searchobj.group() == "0":
                pydaqmx.DAQmxWaitUntilTaskDone(self.readAI, -1)
                pydaqmx.DAQmxStopTask(self.readAI)
                print "Scan Complete"
            else:
                self.stoptask()

        except AttributeError:
            self.stoptask()

        except RuntimeError:
            pydaqmx.DAQmxStopTask(self.readAI)
            print "scan depth too long"
            sys.exit()

    def getraw(self):
        nChan = len(self.aiPorts)
        self.dataSorted = np.zeros((self.nSampPerChan, nChan))
        for i in range(0, len(self.dataBuffer), nChan):
            for j in range(nChan):
                self.dataSorted[i / 2, j] = self.dataBuffer[i + j]

    def waitForSlew(self):
        self.tn.read_very_eager()  # Clear out the buffer
        reList = [
            "wavelength-act = "]  # The expression we will look for in the output of the laser, we will end up basically deleting all the text up to and including this
        timeWait = 30  # The time we will wait for the laser to slew to the correct wavelength
        while timeWait > 0:
            self.tn.write("(param-disp 'laser1:ctl:wavelength-act) \r\n")
            time.sleep(.03)
            self.tn.expect(reList, 1)  # Wait up to 1 second to receive a message containing a string in reList
            waveActStr = self.tn.read_very_eager()  # The beginning of the buffer is now the wavelength
            if waveActStr == '':
                waveAct = 0  # Guaranteeing that it is not within 0.1nm of the set starting point
            else:
                waveAct = float(waveActStr[0:6])

            if abs(waveAct - (self.startWave - waveOffset)) < 0.1:
                timeWait = 0
            else:
                # print("Difference = " + str(waveAct - self.startWave - waveOffset) + " , timeWait = " + str(timeWait) )
                timeWait = timeWait - 1
                time.sleep(1)
                if timeWait <= 0:
                    print(
                    "After 30 seconds we still aren't at the starting wavelength, code will now crash. Have a nice day!")

    def startScan(self):
        self.initializeData()  # Set up the GUI and initialize variables to hold data
        self.initializeLaser()  # Write the parameter into the Toptica
        self.waitForSlew()  # Wait until laser is at starting wavelength
        self.dataBuffer = np.zeros((int(self.nSampPerChan * len(self.aiPorts)),), dtype=np.int16)
        nominal_x = np.linspace(self.startWave, self.endWave, self.nSampPerChan)
        time.sleep(0.5)
        print "Starting scan"
        self.tn.write("(exec 'laser1:ctl:scan:start) \r\n")
        read = pydaqmx.int32()
        pydaqmx.DAQmxStartTask(self.readAI)
        pydaqmx.DAQmxReadBinaryI16(self.readAI, -1, -1, pydaqmx.DAQmx_Val_GroupByScanNumber, self.dataBuffer,
                                   pydaqmx.uInt32(len(self.dataBuffer)),
                                   ctypes.byref(read), None)

        self.stoptask()
        self.getraw()
        dataDict = {}
        i = 0
        for port in self.aiPorts:
            dataDict[self.aiNameDict[port].replace(" ", "")] = self.dataSorted[:, i]
            i = i + 1

        dataDict["nominal_x"] = nominal_x
        sio.savemat(filePath + str(self.fileName), dataDict)
        txt = open(filePath + str(self.fileName) + '.txt', 'w')
        txt.write(self.metadata)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())