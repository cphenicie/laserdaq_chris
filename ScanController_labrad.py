# Things to add: Read the laser current and put that in the metadata
#                Make nSampPerChan and nSampsPerChan HAVE MUCH MORE DIFFERENT NAMES! (One is "samp" and one is "samps")
#                Make plotting faster or make it so that you can abort GUI without losing data (or is that already the case?)
import sys
from PyQt4 import QtCore, QtGui, uic
import numpy as np
import time
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import Queue
import dataShortcuts
import labrad

## Make sure you have started labrad and toptica_server before running this script!!


### Hard-coded variables ###
dev = "Dev1/"
startTrig = "PFI0"
waveOffset = 5  # How far away from the actual starting wavelength (in nm) we will initially slew the laser
tUpdate = 1  # How many seconds between each update in the graph
filePath = dataShortcuts.makeFilePath()
Hz = labrad.types.Value(1.0,'Hz')
#############################


qtCreatorFile = "ScanUI.ui"  # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class MyApp(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.updateMetadata()
        self.takingData = False
        self.initializing = False
        self.cxn = labrad.connect('localhost')
        self.nm = labrad.types.Value(1.0, 'nm')
        self.s = labrad.types.Value(1.0, 's')

        # Define interactions with the GUI
        numFields = [self.startWaveSpinBox, self.endWaveSpinBox, self.scanRateSpinBox, self.sampleRateSpinBox]
        textFields = [self.inputsTextEdit, self.fileNameLineEdit]
        [field.valueChanged.connect(self.updateMetadata) for field in numFields]
        [field.textChanged.connect(self.updateMetadata) for field in textFields]
        self.startScanButton.clicked.connect(self.startScan)

        self.graphChoiceBoxes = [self.graphChoices1, self.graphChoices2, self.graphChoices3]
        [box.currentIndexChanged.connect(self.changeGraph) for box in self.graphChoiceBoxes]
        self.axisToColDict = {}  # Dictionary to tell which graph to display on which axis

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

        self.canvases = [self.canvas1, self.canvas2, self.canvas3]
        self.figs = [self.figHand1, self.figHand2, self.figHand3]
        self.axes = [self.axHand1, self.axHand2, self.axHand3]
        self.colNums = range(3)
        self.graphHolders = [self.graphHolder1, self.graphHolder2, self.graphHolder3]
        for canvas, fig, holder in zip(self.canvases, self.figs, self.graphHolders):
            canvas.setParent(holder)
            fig.subplots_adjust(bottom=0.55, top=0.9, right=0.69, left=0.15)  # Otherwise the axes seem to get cut off

        self.fig1Toolbar = NavigationToolbar2QT(self.canvas1, self.graphHolder1, coordinates=True)
        self.fig2Toolbar = NavigationToolbar2QT(self.canvas2, self.graphHolder2, coordinates=True)
        self.fig3Toolbar = NavigationToolbar2QT(self.canvas3, self.graphHolder3, coordinates=True)
        self.toolbars = [self.fig1Toolbar, self.fig2Toolbar, self.fig3Toolbar]
        ## Peace and Sri have this line, but it seems to break this code and be unnecessary:
        # for toolbar, holder in zip(self.graphHolders, self.toolbars):
        #     toolbar.setParent(holder)

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
        self.fileName = self.fileNameLineEdit.text()
        self.metadata = self.metadataTextEdit.toPlainText()
        self.nChan = len(self.aiPorts)
        self.sampFreqPerChan = self.sampleRate / self.nChan
        self.tSamp = abs(self.endWave - self.startWave) / self.scanRate
        self.nSampsPerChan = int(self.tSamp * self.sampFreqPerChan)
        self.nSamps = int(self.nSampsPerChan * self.nChan)
        self.stepBufferSize = self.sampleRate * tUpdate
        self.nSteps = np.ceil(self.nSamps / self.stepBufferSize)
        self.q = Queue.Queue()
        #self.tn = telnetlib.Telnet("10.0.0.2", 1998)
        self.varNames = self.aiNames
        self.varNames.append("NominalWavelength")  # We will put the nominal wavelengths as the last entry in the data array

        # Initialize which plots will be shown on which axes, by default they are on the first item added
        if self.nChan > 1:
            self.graphChoices2.setCurrentIndex(1)
        if self.nChan > 2:
            self.graphChoices3.setCurrentIndex(2)

        for axis, box in zip(self.axes, self.graphChoiceBoxes):
            self.axisToColDict[axis] = self.varNameToColDict[str(box.currentText())]

        self.initializing = False


    def takeData(self):
        self.takingData = True
        time.sleep(0.5)
        print "Starting scan"
        self.cxn.usb6002.makeTask("readAI")
        self.cxn.usb6002.makeAnalogIn("readAI", self.portString)
        self.cxn.usb6002.configClock("readAI", self.sampFreqPerChan*Hz, self.nSampsPerChan)
        self.cxn.usb6002.setTriggerRising("readAI", startTrig)
        self.cxn.usb6002.startTask("readAI")
        self.cxn.topticactl1500.startScan()

        dataBuffer = self.cxn.usb6002.takeData("readAI", self.nSampsPerChan, self.nChan)
        fullBuffer = np.zeros((int(self.nSampsPerChan), int(self.nChan) + 1), dtype=np.float32)  # One extra column for the nominal wavelength. Use float32 so we can cast an int16 into it as well as put floats in
        fullBuffer[:, -1] = np.linspace(self.startWave, self.endWave, self.nSampsPerChan)  # Place nominal wavelengths in the last column just so we don't have "+1" floating around the loops

        # sort the data into a matrix
        for i in range(self.nChan):
            fullBuffer[:, i] = dataBuffer[i*self.nSampsPerChan: (i+1)*self.nSampsPerChan]

        for axis, canvas in zip(self.axes, self.canvases):
            axis.cla()  # Clear the axes so that we aren't re-drawing the old data underneath the new data (which slows down plotting ~1.5x)
            axis.plot(fullBuffer[:, -1], fullBuffer[:, self.axisToColDict[axis]], 'k')
            canvas.draw()

        self.cxn.usb6002.stopTask("readAI")
        self.takingData = False
        return fullBuffer


    def startScan(self):
        self.initializeData()  # Set up the GUI and initialize variables to hold data
        self.cxn.topticactl1500.setScan( (self.startWave-waveOffset)*self.nm, self.startWave*self.nm, self.endWave*self.nm, self.scanRate*(self.nm/self.s))
        self.data = self.takeData()
        dataShortcuts.saveData(self.data, self.varNames, filePath + str(self.fileName), metadata=self.metadata) # If you have no metadata set metadata=None
        print("Done")


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())