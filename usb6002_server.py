from labrad import types as T, util
from labrad.server import LabradServer, setting
from twisted.internet.defer import inlineCallbacks, returnValue
import PyDAQmx as pydaqmx  # Python library to execute NI-DAQmx code
import ctypes # Lets us use data types compatible with C code
import numpy as np



class TTLSwitch:
    def __init__(self, dev, port, line):
        self.dev = dev
        self.port = port
        self.line = line
        self.loc = dev + "/" + port + "/" +  "line" + str(line)
        self.taskName = ''  # Name of the task (I don't know when this would not be an empty string...)
        self.lineNames = ""  # I don't know, from the help guide: "The name of the created virtual channel(s). If you create multiple virtual channels with one call to this function, you can specify a list of names separated by commas. If you do not specify a name, NI-DAQmx uses the physical channel name as the virtual channel name. If you specify your own names for nameToAssignToLines, you must use the names when you refer to these channels in other NI-DAQmx functions."
        self.lineGrouping = pydaqmx.DAQmx_Val_ChanPerLine  # I THINK this should allow you to only address 1 line instead of the entire port, but I see no difference between the two. Group digital lines into one (ChanPerLine) or more (ChanForAllLines) lines
        self.nSamps = 1  # Number of steps (or "samples") in the pulse sequence
        self.autoSt = 1  # If 1, do not wait for pydaqmx.DAQmxStartTask()
        self.tOut = pydaqmx.float64(10.0)  # Return an error if it takes longer than this many seconds to write the entire step sequence
        self.dataLay = pydaqmx.DAQmx_Val_GroupByChannel  # Specify if the data are interleaved (GroupByChannel) or noninterleaved (GroupByScanNumber)
        self.handle = pydaqmx.TaskHandle()
        pydaqmx.DAQmxCreateTask(self.taskName, ctypes.byref( self.handle ))
        pydaqmx.DAQmxCreateDOChan( self.handle, self.loc, self.lineNames, self.lineGrouping)

    def high(self):
        pydaqmx.DAQmxStartTask(self.handle)
        sampArr = np.array(2**self.line, dtype=pydaqmx.uInt32)
        pydaqmx.DAQmxWriteDigitalU32(self.handle, self.nSamps, self.autoSt, self.tOut, self.dataLay, sampArr, None, None)
        pydaqmx.DAQmxStopTask(self.handle)

    def low(self):
        pydaqmx.DAQmxStartTask(self.handle)
        sampArr = np.array(0, dtype=pydaqmx.uInt32)
        pydaqmx.DAQmxWriteDigitalU32(self.handle, self.nSamps, self.autoSt, self.tOut, self.dataLay, sampArr, None,
                                     None)
        pydaqmx.DAQmxStopTask(self.handle)



class USB6002(LabradServer):
    name = 'usb6002'  # This is how you will access this class from a labrad connection (with name.replace(" ", "_") and name.lower() )

    @inlineCallbacks
    def initServer(self):
        self.makeTTLSwitches(self)
        self.handleDict = {}  # All of the task handles will in in this dictionary referenced by some string we pass into this class
        yield

    @setting(1, 'echo', msg='?', returns='?')
    def echo(self, c, msg):
        print(msg)
        return msg

    @setting(2, 'makeTTLSwitches', returns='?')
    def makeTTLSwitches(self, c):
        self.switches = {}
        dev = 'Dev1'
        portLineNumDict = {'port0': 8, 'port1': 4, 'port2': 1}
        for port in portLineNumDict:
            for i in range(portLineNumDict[port]):
                self.switches[dev + "/" + port + "/" + "line" + str(i)] = TTLSwitch(dev, port, i)
        return None

    @setting(3, 'flipSwitch', loc='s', state='s', returns='?')
    def flipSwitch(self, c, loc, state):
        if state.lower() == "high":
            self.switches[loc].high()
        elif state.lower() == "low":
            self.switches[loc].low()
        else:
            print("Not a valid state")
        # print(loc)
        return None

    # @setting(4, 'makeHandle', name='s')
    # def makeHandle(self, c, name):
    #     self.handleDict[name] = pydaqmx.TaskHandle()

    @setting(5, 'makeTask', name='s')
    def makeTask(self, c, name):
        ## Create a task out of an existing handle
        # int32 DAQmxCreateTask (const char taskName[], TaskHandle *taskHandle);
        self.handleDict[name] = pydaqmx.TaskHandle()
        taskName = ''  # Name of the task (I don't know when this would not be an empty string...)
        input1Pointer = ctypes.byref(self.handleDict[name])  # Equivalent to &setStates in C, the pointer to the task handle
        pydaqmx.DAQmxCreateTask(taskName, input1Pointer)

    @setting(6, 'configClock', name='s', fSamp='v[Hz]', nSamp='i')
    def configClock(self, c, name, fSamp, nSamp):
        ## Configure the clock
        # int32 DAQmxCfgSampClkTiming (TaskHandle taskHandle, const char source[], float64 rate, int32 activeEdge, int32 sampleMode, uInt64 sampsPerChanToAcquire);
        source = None  # If you use an external clock, specify here, otherwise it should be None
        rate = pydaqmx.float64(
            fSamp['Hz'])  # The sampling rate in samples per second per channel. If you use an external source for the Sample Clock, set this value to the maximum expected rate of that clock.
        edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
        sampMode = pydaqmx.DAQmx_Val_FiniteSamps  # Acquire samples continuously or just a finite number of samples
        sampPerChan = pydaqmx.uInt64(nSamp)  # Total number of sample to acquire for each channel
        pydaqmx.DAQmxCfgSampClkTiming(self.handleDict[name], source, rate, edge, sampMode, sampPerChan)


    @setting(7, 'makeAnalogIn', name='s', portString='s')
    def makeAnalogIn(self, c, name, portString):
        ## Create Analog In voltage channel
        # int32 DAQmxCreateAIVoltageChan (TaskHandle taskHandle, const char physicalChannel[], const char nameToAssignToChannel[], int32 terminalConfig, float64 minVal, float64 maxVal, int32 units, const char customScaleName[]);
        chan = portString  # Location of the channel (this should be a physical channel, but it will be used as a virtual channel?)
        chanName = ""  # Name(s) to assign to the created virtual channel(s). "" means physical channel name will be used
        termConfig = pydaqmx.DAQmx_Val_Diff  # Is this singled/double referenced, differential, etc.\
        vMin = -10  # Minimum voltage you expect to measure (in units described by variable "units" below)
        vMax = 10  # Maximum voltage you expect to measure
        units = pydaqmx.DAQmx_Val_Volts  # Units used in vMax/vMin.
        custUnits = None  # If units where DAQmx_Val_FromCustomScale, specify scale. Otherwise, it should be None
        pydaqmx.DAQmxCreateAIVoltageChan(self.handleDict[name], chan, chanName, termConfig, vMin, vMax, units, custUnits)

    @setting(8, 'setTriggerRising', name='s', chan='s')
    def setTriggerRising(self, c, name, chan):
        pydaqmx.DAQmxCfgDigEdgeStartTrig(self.handleDict[name], chan, pydaqmx.DAQmx_Val_Rising)

    @setting(9, 'setTriggerFalling', name='s', chan='s')
    def setTriggerFalling(self, c, name, chan):
        pydaqmx.DAQmxCfgDigEdgeStartTrig(self.handleDict[name], chan, pydaqmx.DAQmx_Val_Falling)

    @setting(10, 'startTask', name='s')
    def startTask(self, c, name):
        pydaqmx.DAQmxStartTask(self.handleDict[name])

    @setting(11, 'stopTask', name='s')
    def stopTask(self, c, name):
        pydaqmx.DAQmxStopTask(self.handleDict[name])

    # Intended to work well for short measurements.
    # Make an entire measurement of a configured TaskHandle handle and save it into dataBuffer
    @setting(12, 'takeData', name='s', nSampsPerChan='i', nChan='i', returns='*i')
    def takeData(self, c, name, nSampsPerChan, nChan):
        # int32 DAQmxReadBinaryI16 (TaskHandle taskHandle, int32 numSampsPerChan, float64 timeout, bool32 fillMode, int16 readArray[], uInt32 arraySizeInSamps, int32 *sampsPerChanRead, bool32 *reserved);
        dataBuffer16 = np.zeros(nSampsPerChan*nChan, dtype=np.int16) # PyDAQmx needs an array of int16s
        dataBuffer32 = np.zeros(nSampsPerChan * nChan, dtype=np.int32)  # LabRAD needs an array of int32s
        read = pydaqmx.int32()  # Variable that will hold the value of how many samples we actually read (This gives us the freedom of putting in any sized dataBuffer and know exactly how much data is in it)
        #nSampsPerChan = -1 in finite mode means wait until all samples are collected and read them
        timeout = -1  # -1 means wait indefinitely to read the samples
        fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies if you want to prioritize by lowest channel or lowest sample (if you have mutiple channels each getting multiple samples)
        arrSize = pydaqmx.uInt32(len(dataBuffer16))
        # sampsPerChanRead = ctypes.byref(read)  # The number of samples we actually read
        # pydaqmx.DAQmxReadBinaryI16(handle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize, sampsPerChanRead, None)  # This is the line when you actually read the voltage
        pydaqmx.DAQmxReadBinaryI16(self.handleDict[name], nSampsPerChan, timeout, fillMode, dataBuffer16, arrSize, ctypes.byref(read),
                                   None)  # This is the line when you actually read the voltage
        for i in range(len(dataBuffer16)):
            dataBuffer32[i] = dataBuffer16[i]

        return dataBuffer32
    #
    # # Intended to work well with threads and long data collection
    # # Grab as much data as will fit in dataBuffer and put in into a queue, also put into the queue how much data we took
    # # (Note, this can be less than the entire size of the buffer if, for instance, the taskHandle one has 900 data points
    # # left until it has collected all nSamp, but we still want to use a buffer with 1000 elements)
    # def putDataInQueue(taskHandle, dataBuffer, nChan, queue):
    #     read = pydaqmx.int32()
    #     nSampsPerChan = len(dataBuffer) / nChan  # How many samples we will collect from each channel
    #     timeout = -1  # -1 means wait indefinitely to read the samples
    #     fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies that dataBuffer will be divided into continuous blocks of data for each channel (rather than interleaved)
    #     arrSize = pydaqmx.uInt32(len(dataBuffer))
    #
    #     pydaqmx.DAQmxReadBinaryI16(taskHandle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize,
    #                                ctypes.byref(read), None)
    #     queue.put(dataBuffer)
    #     queue.put(read)
    #     return

__server__ = USB6002()

if __name__ == '__main__':
    util.runServer(__server__)