# A bunch of classes and functions to make it easier to interface with PyDAQmx.
# To get the documentation for functions called by PyDAQmx, open the NI-DAQmx C Reference Help, which can be found in
# the Start menu an search for "C Reference Help"

import PyDAQmx as pydaqmx  # Python library to execute NI-DAQmx code
import ctypes # Lets us use data types compatible with C code
import numpy as np

# TTLswitch is the most basic digital output class. Just make new object by specifying the dev (str, the device name),
# port (int, the port number on the device), and line (int, the line number in the port. The built in function high()
# will output 3.3V on the line and low() will output 0V.
class TTLSwitch:
    def __init__(self, dev, port, line):
        self.dev = dev
        self.port = port
        self.line = line
        self.loc = dev + str(port) + "line" + str(line)
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

# # Quick test
# gasSwitch = TTLSwitch('Dev1/', 'port0/', 1)
# gasSwitch.high()


# Configure an task handle as an analog channel to read in a voltage in differential mode. Need to specify the device,
# port, handle that will be configured, and the frequency and number of measurements that will be made.
def makeAnalogIn(portString, handle, fSamp, nSamp):

    ## Create a task out of an existing handle
    # int32 DAQmxCreateTask (const char taskName[], TaskHandle *taskHandle);
    taskName = ''  # Name of the task (I don't know when this would not be an empty string...)
    input1Pointer = ctypes.byref(handle)  # Equivalent to &setStates in C, the pointer to the task handle
    pydaqmx.DAQmxCreateTask(taskName, input1Pointer)

    ## Create Analog In voltage channel
    # int32 DAQmxCreateAIVoltageChan (TaskHandle taskHandle, const char physicalChannel[], const char nameToAssignToChannel[], int32 terminalConfig, float64 minVal, float64 maxVal, int32 units, const char customScaleName[]);
    chan = portString  # Location of the channel (this should be a physical channel, but it will be used as a virtual channel?)
    chanName = ""  # Name(s) to assign to the created virtual channel(s). "" means physical channel name will be used
    termConfig = pydaqmx.DAQmx_Val_Diff  # Is this singled/double referenced, differential, etc.\
    vMin = -10  # Minimum voltage you expect to measure (in units described by variable "units" below)
    vMax = 10  # Maximum voltage you expect to measure
    units = pydaqmx.DAQmx_Val_Volts  # Units used in vMax/vMin.
    custUnits = None  # If units where DAQmx_Val_FromCustomScale, specify scale. Otherwise, it should be None
    pydaqmx.DAQmxCreateAIVoltageChan(handle, chan, chanName, termConfig, vMin, vMax, units, custUnits)

    ## Configure the clock
    # int32 DAQmxCfgSampClkTiming (TaskHandle taskHandle, const char source[], float64 rate, int32 activeEdge, int32 sampleMode, uInt64 sampsPerChanToAcquire);
    source = None  # If you use an external clock, specify here, otherwise it should be None
    rate = pydaqmx.float64(fSamp)
    edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
    sampMode = pydaqmx.DAQmx_Val_FiniteSamps  # Acquire samples continuously or just a finite number of samples
    sampPerChan = pydaqmx.uInt64(nSamp)
    pydaqmx.DAQmxCfgSampClkTiming(handle, source, rate, edge, sampMode, sampPerChan)

# Actually make the measurement of a configured TaskHandle handle and save it into dataBuffer
def getAnalogIn(handle, dataBuffer):
    # int32 DAQmxReadBinaryI16 (TaskHandle taskHandle, int32 numSampsPerChan, float64 timeout, bool32 fillMode, int16 readArray[], uInt32 arraySizeInSamps, int32 *sampsPerChanRead, bool32 *reserved);
    read = pydaqmx.int32()
    nSampsPerChan = -1  # -1 in finite mode means wait until all samples are collected and read them
    timeout = -1  # -1 means wait indefinitely to read the samples
    fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies if you want to prioritize by lowest channel or lowest sample (if you have mutiple channels each getting multiple samples)
    arrSize = pydaqmx.uInt32(len(dataBuffer))
    sampsPerChanRead = ctypes.byref(read)
    pydaqmx.DAQmxStartTask(handle)
    pydaqmx.DAQmxReadBinaryI16(handle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize, sampsPerChanRead, None)  # This is the line when you actually read the voltage
    pydaqmx.DAQmxStopTask(handle)
