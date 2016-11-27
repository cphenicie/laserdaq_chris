# A bunch of classes and functions to make it easier to interface with PyDAQmx.
# To get the documentation for functions called by PyDAQmx, open the NI-DAQmx C Reference Help, which can be found in
# the Start menu an search for "C Reference Help"

########## Contents ##########

### Classes ###
# TTLSwitch: configure a given digital out line to be switched on (with TTLSwitch.high()) or off (with TTLSwitch.low())


### Functions ###
# makeAnalogIn: Configure analog in channel(s) to collect a total of nSamp data points at a frequency fSamp
# getAnalogIn: Read all nSamp channels from an analog in task
# putDataInQueue:  Fill up a specified buffer with data and put that data into a specified queue



import PyDAQmx as pydaqmx  # Python library to execute NI-DAQmx code
import ctypes # Lets us use data types compatible with C code
import numpy as np
import Queue
import matplotlib.animation as animation
import matplotlib.pyplot as plt

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
    rate = pydaqmx.float64(fSamp) # The sampling rate in samples per second per channel. If you use an external source for the Sample Clock, set this value to the maximum expected rate of that clock.
    edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
    sampMode = pydaqmx.DAQmx_Val_FiniteSamps  # Acquire samples continuously or just a finite number of samples
    # sampMode = pydaqmx.DAQmx_Val_ContSamps
    sampPerChan = pydaqmx.uInt64(nSamp)  # Total number of sample to acquire for each channel
    pydaqmx.DAQmxCfgSampClkTiming(handle, source, rate, edge, sampMode, sampPerChan)

# Intended to work well for short measurements.
# Make an entire measurement of a configured TaskHandle handle and save it into dataBuffer
def getAnalogIn(handle, dataBuffer):
    # int32 DAQmxReadBinaryI16 (TaskHandle taskHandle, int32 numSampsPerChan, float64 timeout, bool32 fillMode, int16 readArray[], uInt32 arraySizeInSamps, int32 *sampsPerChanRead, bool32 *reserved);
    read = pydaqmx.int32()  # Variable that will hold the value of how many samples we actually read (This gives us the freedom of putting in any sized dataBuffer and know exactly how much data is in it)
    nSampsPerChan = -1  # -1 in finite mode means wait until all samples are collected and read them
    timeout = -1  # -1 means wait indefinitely to read the samples
    fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies if you want to prioritize by lowest channel or lowest sample (if you have mutiple channels each getting multiple samples)
    arrSize = pydaqmx.uInt32(len(dataBuffer))
    # sampsPerChanRead = ctypes.byref(read)  # The number of samples we actually read
    pydaqmx.DAQmxStartTask(handle)
    # pydaqmx.DAQmxReadBinaryI16(handle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize, sampsPerChanRead, None)  # This is the line when you actually read the voltage
    pydaqmx.DAQmxReadBinaryI16(handle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize, ctypes.byref(read), None)  # This is the line when you actually read the voltage
    pydaqmx.DAQmxStopTask(handle)

# Intended to work well with threads and long data collection
# Grab as much data as will fit in dataBuffer and put in into a queue, also put into the queue how much data we took
# (Note, this can be less than the entire size of the buffer if, for instance, the taskHandle one has 900 data points
# left until it has collected all nSamp, but we still want to use a buffer with 1000 elements)
def putDataInQueue(taskHandle, dataBuffer, nChan, queue):
    read = pydaqmx.int32()
    nSampsPerChan = len(dataBuffer) / nChan  # How many samples we will collect from each channel
    timeout = -1  # -1 means wait indefinitely to read the samples
    # fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies that dataBuffer will be divided into continuous blocks of data for each channel (rather than interleaved)
    fillMode = pydaqmx.DAQmx_Val_GroupByScanNumber
    arrSize = pydaqmx.uInt32(len(dataBuffer))

    pydaqmx.DAQmxReadBinaryI16(taskHandle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize,
                               ctypes.byref(read), None)
    queue.put(dataBuffer)
    queue.put(read)
    return


# Create an output sine wave (apparently DAQmxCreateAOFunGenChan doesn't work with the 6002?
def makeAnalogOut(portString, handle, freq, amp, offset, waveform):
    outScan = handle
    taskName = ''  # Name of the task (I don't know when this would not be an empty string...)
    input1Pointer = ctypes.byref(outScan)  # Equivalent to &setStates in C, the pointer to the task handle
    pydaqmx.DAQmxCreateTask(taskName, input1Pointer)

    chan = portString  # Location of the channel (this should be a physical channel, but it will be used as a virtual channel?)
    chanName = ""  # Name(s) to assign to the created virtual channel(s). "" means physical channel name will be used

    minVal = pydaqmx.float64(-10.0)
    maxVal = pydaqmx.float64(10.0)
    units = pydaqmx.DAQmx_Val_Volts
    pydaqmx.DAQmxCreateAOVoltageChan(outScan, chan, chanName, minVal, maxVal, units, 0)

    fSamp = 1000
    nSamp = 1000
    source = None  # If you use an external clock, specify here, otherwise it should be None
    rate = pydaqmx.float64(
        fSamp)  # The sampling rate in samples per second per channel. If you use an external source for the Sample Clock, set this value to the maximum expected rate of that clock.
    edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
    sampMode = pydaqmx.DAQmx_Val_ContSamps  # Acquire samples continuously or just a finite number of samples
    sampPerChan = pydaqmx.uInt64(nSamp)  # Total number of sample to acquire for each channel
    pydaqmx.DAQmxCfgSampClkTiming(outScan, source, rate, edge, sampMode, sampPerChan)

    # writeArray = np.zeros((int(nSamp),), dtype=np.float64)
    if waveform == 'sin':
        x = 2 * np.pi * freq * np.array(range(nSamp)) / 1000.0
        writeArray = np.array(amp * np.sin(x) + offset, dtype=np.float64)
    if waveform == 'saw':
        # The amplitude is the peak-to-peak voltage in this waveform
        if freq != np.ceil(freq):
            print("I don't understand decimals yet, the frequency I'm actually using is " +str(np.ceil(freq)+"Hz"))
        writeArray = amp/1000.0*(np.array(range(1000)) * freq % 1000) + offset


    written = pydaqmx.int32()
    nSampPerChan = pydaqmx.int32(nSamp)
    pydaqmx.DAQmxWriteAnalogF64(outScan, nSampPerChan, pydaqmx.bool32(0), pydaqmx.DAQmx_Val_WaitInfinitely,
                                pydaqmx.DAQmx_Val_GroupByChannel, writeArray, ctypes.byref(written), None)


# def continuouslyUpdatePlot(canvas, fig, axis, taskHandle, fSamp, nSamp, app):
#     print("starting piezo scan")
#     def animate(i):
#         axis.cla()
#         pydaqmx.DAQmxStartTask(taskHandle)
#
#         ## Read from the specified line(s)
#         # int32 DAQmxReadBinaryI16 (TaskHandle taskHandle, int32 numSampsPerChan, float64 timeout, bool32 fillMode, int16 readArray[], uInt32 arraySizeInSamps, int32 *sampsPerChanRead, bool32 *reserved);
#         nSampsPerChan = -1  # -1 in finite mode means wait until all samples are collected and read them
#         timeout = -1  # -1 means wait indefinitely to read the samples
#         fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies if you want to prioritize by lowest channel or lowest sample (if you have mutiple channels each getting multiple samples)
#         read = pydaqmx.int32()
#         data = np.zeros((int(nSamp),), dtype=np.int16)
#         readArr = data  # The array to read the samples into
#         # arrSize = c_uint32(int(nSamp)).value  # size of the read array
#         arrSize = pydaqmx.uInt32(nSamp)
#         sampsPerChanRead = ctypes.byref(read)
#         pydaqmx.DAQmxReadBinaryI16(taskHandle, nSampsPerChan, timeout, fillMode, readArr, arrSize, sampsPerChanRead, None)
#
#         pydaqmx.DAQmxStopTask(taskHandle)
#         # filename = "test.csv"
#         # np.savetxt(filename, data, delimiter=",")
#         tMS = (np.arange(0, nSamp) / float(fSamp)) * 1e3
#
#         # freq = 20
#         # amp = 10
#         # offset = 0
#         # tMS = amp / 1000.0 * (np.array(range(1000)) * freq % 1000) + offset
#         # dataCal = data * (20.0 / 2 ** 16)
#         # axis.plot(tMS, dataCal)
#
#         # plt.plot(data)
#         #plt.xlabel('Time (ms)')
#         #plt.ylabel('Signal (V)')
#
#     ani = animation.FuncAnimation(fig, animate, interval=500)
#     #plt.show()
#     canvas.draw()
#     #app.processEvents() # Tell the app that's calling this to update
#     return ani





def makeUpdatingGraph(i, axis, taskHandle, nSamp, arcFactor, arcOffset, piezoQ):
    piezoCal = 177 # Calibration between piezo voltage and frequency detuning in MHz/V
    axis.cla()
    pydaqmx.DAQmxStartTask(taskHandle)

    ## Read from the specified line(s)
    # int32 DAQmxReadBinaryI16 (TaskHandle taskHandle, int32 numSampsPerChan, float64 timeout, bool32 fillMode, int16 readArray[], uInt32 arraySizeInSamps, int32 *sampsPerChanRead, bool32 *reserved);
    nSampsPerChan = -1  # -1 in finite mode means wait until all samples are collected and read them
    timeout = -1  # -1 means wait indefinitely to read the samples
    # fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies if you want to prioritize by lowest channel or lowest sample (if you have mutiple channels each getting multiple samples)
    fillMode = pydaqmx.DAQmx_Val_GroupByScanNumber
    read = pydaqmx.int32()
    data = np.zeros((int(2*nSamp),), dtype=np.int16) # Factor of two because we are also collecting the piezo voltage interleaved
    readArr = data  # The array to read the samples into
    # arrSize = c_uint32(int(nSamp)).value  # size of the read array

    # I'm pretty sure I should be using arrSize2, but I'm not positive...
    arrSize = pydaqmx.uInt32(nSamp)
    arrSize2 = pydaqmx.uInt32(2*nSamp)

    sampsPerChanRead = ctypes.byref(read)
    pydaqmx.DAQmxReadBinaryI16(taskHandle, nSampsPerChan, timeout, fillMode, readArr, arrSize2, sampsPerChanRead, None)
    #import time
    #time.sleep(0.1)
    pydaqmx.DAQmxStopTask(taskHandle)


    coeffs = np.zeros(4)
    coeffsPointer = coeffs.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    pydaqmx.DAQmxGetAIDevScalingCoeff(taskHandle, 'Dev1/ai2:3', coeffsPointer, 4)


    # import pdb
    # pdb.set_trace()

    # topticaOutDAQUnits = []
    # dataInDAQUnits = []
    # for j in range(2*nSamp):
    #     if j%2 == 0:
    #         dataInDAQUnits.append(data[j])
    #     else:
    #         topticaOutDAQUnits.append(data[j])



    # dataInVolts = [coeffs[0] + j*coeffs[1] + j**2*coeffs[2] + j**3 * coeffs[3] for j in dataInDAQUnits]
    #
    # topticaOutVolts = [coeffs[0] + j*coeffs[1] for j in topticaOutDAQUnits]
    # piezoVoltage = [arcOffset + arcFactor*j for j in topticaOutVolts]
    # detuning = [piezoCal * j for j in piezoVoltage]
    #
    #
    #
    # axis.plot(detuning, dataInVolts,'r-')
    # #axis.set_xlim([0, 10])
    # #axis.set_ylim([0, 10])
    # axis.set_xlabel("Detuning (MHz)")

    axis.plot(data[1::2], data[0::2])
    piezoQ.put(data)
    #piezoQ.put(i)
    #print(i)



def makeAnalogInSource(portString, handle, source, fSamp, nSamp):

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
    #source = None  # If you use an external clock, specify here, otherwise it should be None
    rate = pydaqmx.float64(fSamp) # The sampling rate in samples per second per channel. If you use an external source for the Sample Clock, set this value to the maximum expected rate of that clock.
    edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
    sampMode = pydaqmx.DAQmx_Val_FiniteSamps  # Acquire samples continuously or just a finite number of samples
    sampPerChan = pydaqmx.uInt64(nSamp)  # Total number of sample to acquire for each channel
    pydaqmx.DAQmxCfgSampClkTiming(handle, source, rate, edge, sampMode, sampPerChan)





def makeAnalogOutSource(portString, handle, source, freq, amp, offset, waveform):
    outScan = handle
    taskName = ''  # Name of the task (I don't know when this would not be an empty string...)
    input1Pointer = ctypes.byref(outScan)  # Equivalent to &setStates in C, the pointer to the task handle
    pydaqmx.DAQmxCreateTask(taskName, input1Pointer)

    chan = portString  # Location of the channel (this should be a physical channel, but it will be used as a virtual channel?)
    chanName = ""  # Name(s) to assign to the created virtual channel(s). "" means physical channel name will be used

    minVal = pydaqmx.float64(-10.0)
    maxVal = pydaqmx.float64(10.0)
    units = pydaqmx.DAQmx_Val_Volts
    pydaqmx.DAQmxCreateAOVoltageChan(outScan, chan, chanName, minVal, maxVal, units, 0)

    fSamp = 1000
    nSamp = 1000
    #source = None  # If you use an external clock, specify here, otherwise it should be None
    rate = pydaqmx.float64(
        fSamp)  # The sampling rate in samples per second per channel. If you use an external source for the Sample Clock, set this value to the maximum expected rate of that clock.
    edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
    sampMode = pydaqmx.DAQmx_Val_ContSamps  # Acquire samples continuously or just a finite number of samples
    sampPerChan = pydaqmx.uInt64(nSamp)  # Total number of sample to acquire for each channel
    pydaqmx.DAQmxCfgSampClkTiming(outScan, source, rate, edge, sampMode, sampPerChan)

    # writeArray = np.zeros((int(nSamp),), dtype=np.float64)
    if waveform == 'sin':
        x = 2 * np.pi * freq * np.array(range(nSamp)) / 1000.0
        writeArray = np.array(amp * np.sin(x) + offset, dtype=np.float64)
    if waveform == 'saw':
        # The amplitude is the peak-to-peak voltage in this waveform
        if freq != np.ceil(freq):
            print("I don't understand decimals yet, the frequency I'm actually using is " +str(np.ceil(freq)+"Hz"))
        writeArray = amp/1000.0*(np.array(range(1000)) * freq % 1000) + offset


    written = pydaqmx.int32()
    nSampPerChan = pydaqmx.int32(nSamp)
    pydaqmx.DAQmxWriteAnalogF64(outScan, nSampPerChan, pydaqmx.bool32(0), pydaqmx.DAQmx_Val_WaitInfinitely,
                                pydaqmx.DAQmx_Val_GroupByChannel, writeArray, ctypes.byref(written), None)
