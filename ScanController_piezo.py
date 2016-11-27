# Things to add: Read the laser current and put that in the metadata
#                Make nSampPerChan and nSampsPerChan HAVE MUCH MORE DIFFERENT NAMES! (One is "samp" and one is "samps")
#                Make plotting faster or make it so that you can abort GUI without losing data (or is that already the case?)
import sys
from PyQt4 import QtCore, QtGui, uic
import PyDAQmx as pydaqmx  # Python library to execute NI-DAQmx code
import pydaqshortcuts
import numpy as np
import telnetlib
import time
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import Queue
import threading
import topticaShortcuts
import dataShortcuts
import matplotlib.animation as animation
import ctypes
import pdb

### Hard-coded variables ###
dev = "Dev1/"
startTrig = "PFI0"
waveOffset = 5  # How far away from the actual starting wavelength (in nm) we will initially slew the laser
tUpdate = 1  # How many seconds between each update in the graph.
#filePath = dataShortcuts.makeFilePath()
filePath = dataShortcuts.genFilePath()
#############################


qtCreatorFile = "ScanUI_piezo.ui"  # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

pause = False
class MyApp(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.updateMetadata()
        self.takingData = False
        self.initializing = False

        # Update save directory
        self.mechSaveFolderLineEdit.setText(filePath)
        self.piezoSaveFolderLineEdit.setText(filePath)

        # Define interactions with the GUI
        numFields = [self.startWaveSpinBox, self.endWaveSpinBox, self.scanRateSpinBox, self.sampleRateSpinBox]
        textFields = [self.inputsTextEdit, self.fileNameLineEdit]
        [field.valueChanged.connect(self.updateMetadata) for field in numFields]
        [field.textChanged.connect(self.updateMetadata) for field in textFields]
        self.startScanButton.clicked.connect(self.startScan)
        self.piezoCenterSpinBox.valueChanged.connect(lambda: self.setWavelength(self.piezoCenterSpinBox.value()))
        #self.piezoScanRateSpinBox.valueChanged.connect(self.updatePiezoScan)
        #self.samplingRateSpinBox.valueChanged.connect(self.updatePiezoSampling)

        self.graphChoiceBoxes = [self.graphChoices1, self.graphChoices2, self.graphChoices3]
        [box.currentIndexChanged.connect(self.changeGraph) for box in self.graphChoiceBoxes]
        self.axisToColDict = {}  # Dictionary to tell which graph to display on which axis

        self.startPiezoScanButton.clicked.connect(self.startPiezoScan)
        self.stopPiezoScanButton.clicked.connect(self.stopPiezoScan)
        self.startPiezoSamplingButton.clicked.connect(self.startPiezoSampling)
        self.stopPiezoSamplingButton.clicked.connect(self.stopPiezoSampling)
        self.savePiezoDataContButton.clicked.connect(self.getContinuousPiezoData)
        self.savePiezoDataOnceButton.clicked.connect(self.getSinglePiezoData)


        self.samplingRunning = False
        self.piezoScanRunning = False
        self.killPiezoScan = False

        self.resetDeviceButton.clicked.connect(self.resetDevice)
        self.startPDBButton.clicked.connect(self.startPDB)

        # Initialize graphs
        self.figHand1 = Figure()
        self.axHand1 = self.figHand1.add_subplot(111)
        self.canvas1 = FigureCanvasQTAgg(self.figHand1)
        self.figHand2 = Figure()
        self.axHand2 = self.figHand2.add_subplot(111)
        self.canvas2 = FigureCanvasQTAgg(self.figHand2)
        self.figHand3 = Figure()
        self.axHand3 = self.figHand3.add_subplot(111)
        self.canvas3 = FigureCanvasQTAgg(self.figHand3)

        self.figHand4 = Figure()
        self.axHand4 = self.figHand4.add_subplot(111)
        self.canvas4 = FigureCanvasQTAgg(self.figHand4)
        self.canvas4.setParent(self.graphHolder4)
        self.figHand4.subplots_adjust(bottom=0.55, top=0.9, right=0.97, left=0.1)
        self.fig4Toolbar = NavigationToolbar2QT(self.canvas4, self.graphHolder4, coordinates=True)



        self.canvases = [self.canvas1, self.canvas2, self.canvas3]
        self.figs = [self.figHand1, self.figHand2, self.figHand3]
        self.axes = [self.axHand1, self.axHand2, self.axHand3]
        self.colNums = range(3)
        self.graphHolders = [self.graphHolder1, self.graphHolder2, self.graphHolder3]
        for canvas, fig, holder in zip(self.canvases, self.figs, self.graphHolders):
            canvas.setParent(holder)
            fig.subplots_adjust(bottom=0.55, top=0.9, right=0.85, left=0.10)  # Otherwise the axes seem to get cut off

        self.fig1Toolbar = NavigationToolbar2QT(self.canvas1, self.graphHolder1, coordinates=True)
        self.fig2Toolbar = NavigationToolbar2QT(self.canvas2, self.graphHolder2, coordinates=True)
        self.fig3Toolbar = NavigationToolbar2QT(self.canvas3, self.graphHolder3, coordinates=True)
        self.toolbars = [self.fig1Toolbar, self.fig2Toolbar, self.fig3Toolbar]
        ## Peace and Sri have this line, but it seems to break this code and be unnecessary:
        # for toolbar, holder in zip(self.graphHolders, self.toolbars):
        #     toolbar.setParent(holder)

        #self.tn = telnetlib.Telnet("10.0.0.2", 1998)
        self.laser = topticaShortcuts.TopticaDLCPro()
        self.tn = self.laser.tn








    def updateMetadata(self):
        self.metadataTextEdit.setPlainText("Starting wavelength (nm) = " + str(self.startWaveSpinBox.value()))  # This one is setPlainText so it will clear the previous text
        self.metadataTextEdit.appendPlainText("Ending wavelength (nm) = " + str(self.endWaveSpinBox.value()))
        self.metadataTextEdit.appendPlainText("Scan Rate (nm/s) = " + str(self.scanRateSpinBox.value()))
        self.metadataTextEdit.appendPlainText("Sampling Rate (samples/s) = " + str(self.sampleRateSpinBox.value()))
        self.metadataTextEdit.appendPlainText("\nInput configuration: \n" + str(self.inputsTextEdit.toPlainText()))

    def changeGraph(self):
        if not self.initializing:
            for axis, box in zip(self.axes, self.graphChoiceBoxes):
                self.axisToColDict[axis] = self.varNameToColDict[str(box.currentText())]

            if not self.takingData:
                for axis, canvas in zip(self.axes, self.canvases):
                    axis.cla()  # Clear the axes so that we aren't re-drawing the old data underneath the new data (which slows down plotting ~1.5x)
                    axis.plot(self.data[:, -1], self.data[:, self.axisToColDict[axis]], 'k')
                    canvas.draw()

    def initializeData(self):
        self.initializing = True
        # Configure the analog in data we will take and the corresponding graphChoices comboBoxes
        self.aiPorts = list()
        self.aiNames = list()
        self.graphChoices1.clear()
        self.graphChoices2.clear()
        self.graphChoices3.clear()
        self.graphChoicesPiezo.clear()
        self.varNameToColDict = {}  # Dictionary that tells us the column of data corresponding to the name written in inputTextEdit

        self.inputs = self.inputsTextEdit.toPlainText()
        textLines = self.inputs.split('\n')
        i = 0
        for line in textLines:
            splitLine = line.split(':')
            if len(splitLine) == 2:  # In case there are trailing new lines
                self.aiPorts.append(str.strip(str(splitLine[0])))  # str.strip() gets rid of any leading/trailing spaces
                self.aiNames.append(str.strip(str(splitLine[1])))
                self.graphChoices1.addItem(str.strip(str(splitLine[1])))
                self.graphChoices2.addItem(str.strip(str(splitLine[1])))
                self.graphChoices3.addItem(str.strip(str(splitLine[1])))
                self.graphChoicesPiezo.addItem(str.strip(str(splitLine[1])))
                self.varNameToColDict[str.strip(str(splitLine[1]))] = i
                i += 1

        # Store the variables that will be used during this data run
        self.portString = ""
        for port in self.aiPorts:
            self.portString += (dev + port + ", ")
        self.portString = self.portString[:-2]  # Since we will have a trailing ", " at the end

        self.startWave = self.startWaveSpinBox.value()
        self.endWave = self.endWaveSpinBox.value()
        self.scanRate = self.scanRateSpinBox.value()
        self.sampleRate = self.sampleRateSpinBox.value()
        self.inputs = self.inputsTextEdit.toPlainText()
        self.saveDir = str(self.mechSaveFolderLineEdit.text())
        self.fileName = str(self.fileNameLineEdit.text())
        self.metadata = self.metadataTextEdit.toPlainText()
        self.nChan = len(self.aiPorts)


        # Define the upper bound for how many samples we can take while the scan is running, then find the acutal
        # highest number by considering that is has to be an integer multiple of the number of channels that can be
        # updated an integer number of times
        self.tElapsed = abs(self.endWave - self.startWave) / self.scanRate # nm / (nm/s) = s
        self.nSampMax =  self.sampleRate * self.tElapsed # Samples/s * s = Samples Note: this is not exactly the total number of samples that will be taken
        self.nSteps = int(np.ceil(self.tElapsed / float(tUpdate)))  # The number of steps through the data to update once every "tUpdate" seconds (we'll actually be a bit faster)

        # We can now define the variables to put into pydaqmx for one update loop
        self.nSampsPerChanPerStep = int(self.nSampMax/(self.nChan*self.nSteps)) # int(a/b) is equivalent to int(np.floor(a/b))
        self.fSampPerChan = self.nSampsPerChanPerStep * self.nSteps / self.tElapsed # Frequency so we will take the full amount of time to get the samples

        self.q = Queue.Queue()
        self.varNames = self.aiNames
        self.varNames.append("NominalWavelength")  # We will put the nominal wavelengths as the last entry in the data array

        # import pdb
        # pdb.set_trace()

        # Initialize which plots will be shown on which axes, by default they are on the first item added
        if self.nChan > 1:
            self.graphChoices2.setCurrentIndex(1)
        if self.nChan > 2:
            self.graphChoices3.setCurrentIndex(2)
            self.graphChoicesPiezo.setCurrentIndex(2)

        for axis, box in zip(self.axes, self.graphChoiceBoxes):
            self.axisToColDict[axis] = self.varNameToColDict[str(box.currentText())]

        self.initializing = False



    def takeData(self):
        self.takingData = True
        time.sleep(0.5)
        print "Starting scan"
        self.readAI = pydaqmx.TaskHandle()
        # pydaqshortcuts.makeAnalogIn(self.portString, self.readAI, self.sampFreqPerChan, self.nSampsPerChan)
        pydaqshortcuts.makeAnalogIn(self.portString, self.readAI, self.fSampPerChan, self.nSampsPerChanPerStep * self.nSteps)
        pydaqmx.DAQmxCfgDigEdgeStartTrig(self.readAI, startTrig, pydaqmx.DAQmx_Val_Rising)  # Trigger to actually start collecting data
        pydaqmx.DAQmxStartTask(self.readAI)
        self.tn.write("(exec 'laser1:ctl:scan:start) \r\n")

        # Initialize some variables
        ptsPerChan = 0
        stepBuffer = np.zeros(self.nSampsPerChanPerStep * self.nChan, dtype=np.int16)  # Needs to be int16 to work with PyDAQmx, the DAQ units are all integers anyway
        fullBuffer = np.zeros((self.nSampsPerChanPerStep * self.nSteps, self.nChan + 1), dtype=np.float32)  # One extra column for the nominal wavelength. Use float32 so we can cast an int16 into it as well as put floats in for the nominal wavelength
        fullBuffer[:, -1] = np.linspace(self.startWave, self.endWave, self.nSampsPerChanPerStep * self.nSteps)  # Place nominal wavelengths in the last column just so we don't have "+1" floating around the loops

        for i in range(self.nSteps):
            # Make a thread to grab data from the readAI task in parallel to the rest of the code, a new thread for each step.
            t = threading.Thread(target=pydaqshortcuts.putDataInQueue, args=(self.readAI, stepBuffer, self.nChan, self.q))
            t.start()

            # Retrieve the data from the queue and sort it
            stepData = self.q.get()
            numTakenPerChan = self.q.get().value  # The ctypes object stores the value in a python-friendly format using the .value attribute

            for j in range(self.nChan):
                fullBuffer[ptsPerChan: ptsPerChan + numTakenPerChan, j] = stepData[j::self.nChan] # j::self.nChan is call "slicing", means "start at j, go until end, in steps of size self.nChan"
            ptsPerChan += numTakenPerChan  # Make sure this is updated AFTER we used it in fullBuffer

            for axis, canvas in zip(self.axes, self.canvases):
                axis.cla()  # Clear the axes so that we aren't re-drawing the old data underneath the new data (which slows down plotting ~1.5x)
                axis.plot(fullBuffer[0:ptsPerChan, -1], fullBuffer[0:ptsPerChan, self.axisToColDict[axis]], 'k')
                axis.get_xaxis().get_major_formatter().set_useOffset(False)
                #axis.get_xaxis().get_major_formatter().set_scientific(False)
                canvas.draw()

            app.processEvents()  # If we don't have this line the graphs don't update until the end of data collection

            # for axis, canvas in zip(self.axes, self.canvases):
            #     p = threading.Thread(target=self.plotData, args=(axis, canvas, fullBuffer[0:ptsPerChan, -1], fullBuffer[0:ptsPerChan, self.axisToColDict[axis]]))
            #     p.start()
            # app.processEvents()  # If we don't have this line the graphs don't update until the end of data collection

        pydaqmx.DAQmxStopTask(self.readAI)
        self.takingData = False
        return fullBuffer

    # def plotData(self, axis, canvas, x, y):
    #     axis.cla()  # Clear the axes so that we aren't re-drawing the old data underneath the new data (which slows down plotting ~1.5x)
    #     axis.plot(x, y, 'k')
    #     canvas.draw()


    def startScan(self):
        self.initializeData()  # Set up the GUI and initialize variables to hold data
        topticaShortcuts.setScan(self.tn, self.startWave, waveOffset, self.endWave, self.scanRate)
        topticaShortcuts.thread_waitForSlew(self.tn, self.startWave - waveOffset)
        self.data = self.takeData()
        dataShortcuts.safemkdir(self.saveDir)
        if self.saveDir[-1] != "\\":
            self.saveDir += "\\"
        dataShortcuts.saveData(self.data, self.varNames, self.saveDir + self.fileName, metadata=self.metadata) # If you have no metadata set metadata=None
        print("Done")



############################### Piezo Scan code ######################################

    # Unfortunately, the voltage steps taken by the USB6002 are noticably larger than the ones taken by the Toptica native
    # signal generator, so we will run the piezo scan by generating the signal from the toptica, and then feeding it back
    # into itself. Then, we can just measure the piezo voltage and the PD voltage on separate channels, in this case we have
    # set up the system to take the signal out of the Toptica through Out A, and plugged this into a BNC tee with 2 other
    # BNCs, one going to Fast in 3 and one going to the USB6002 ai3.
    #
    # (This isn't much more silly than generating the signal by the USB6002 since there's also no way to synchronize the
    # input and the output from the USB6002, we'd still need to have a tee to measure the output, anyway)

    def startPiezoScan(self):
        self.laser.defaultPiezoScan() # This will run continuously

    def stopPiezoScan(self):
        self.laser.setParameter("laser1:scan:enabled", "#f")

    def startPiezoSampling(self):
        self.samplingRunning = True

        fSamp = 25000
        nSamp = int(fSamp*4/30.0)

        self.readChan = pydaqmx.TaskHandle()
        pydaqshortcuts.makeAnalogIn("Dev1/ai2:3", self.readChan, fSamp, nSamp)

        # Start animation, giving it the proper calibration parameters
        arcFactor = float(self.laser.readParameter('laser1:dl:pc:external-input:factor'))
        arcOffset = float(self.laser.readParameter('laser1:dl:pc:voltage-set'))
        self.piezoQ = Queue.Queue()
        self.ani = animation.FuncAnimation(self.figHand4, pydaqshortcuts.makeUpdatingGraph, fargs=(self.axHand4, self.readChan, nSamp, arcFactor, arcOffset, self.piezoQ), interval=20)
        self.canvas4.draw()
        self.ani.event_source.start()
        return self.ani

    def flushQueue(self, q):
        """ Because using q.queue.clear() just breaks everything """
        print("flushing queue...")
        for i in range(q.qsize()-1):
            q.get()
        print("done")

    def getSinglePiezoData(self):
        # Flush all the data previously put in the queue
        self.flushQueue(self.piezoQ)
        data = self.piezoQ.get()
        # import matplotlib.pyplot as plt
        # plt.plot(data[1::2], data[0::2])
        # plt.show()
        return data

    def getContinuousPiezoData(self):
        pass

    def stopPiezoSampling(self):
        self.samplingRunning = False
        if hasattr(self, 'ani') and hasattr(self, 'readChan'):
            self.ani.event_source.stop()
            self.readChan = self.clearTask(self.readChan)


    def updatePiezoSampling(self):
        if hasattr(self, "ani") and hasattr(self, 'readChan'):
            self.ani.event_source.stop()
            self.clearTask(self.readChan)
        #Update
        if self.samplingRunning:
            self.startPiezoSampling()


    def clearTask(self, task):
        if task:
            pydaqmx.DAQmxStopTask(task)
            pydaqmx.DAQmxClearTask(task)
        return False  # So that we can always call stopPiezoScan without an error


    def setWavelength(self, wavelength):
        self.laser.setParameter("laser1:ctl:wavelength-set", str(wavelength))
        #self.tn.write("(param-set! 'laser1:ctl:wavelength-set '" + str(wavelength) + ") \r\n")
        topticaShortcuts.thread_waitForSlew(self.tn, wavelength)


    def resetDevice(self):
        pydaqmx.DAQmxResetDevice("Dev1")

    def startPDB(self):
        pdb.set_trace()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())