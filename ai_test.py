
import PyDAQmx as pydaqmx
import ctypes,numpy

handle = pydaqmx.TaskHandle()
pydaqmx.DAQmxCreateTask('', ctypes.byref( handle ))

## Create Analog In voltage channel
# int32 DAQmxCreateAIVoltageChan (TaskHandle taskHandle, const char physicalChannel[], const char nameToAssignToChannel[], int32 terminalConfig, float64 minVal, float64 maxVal, int32 units, const char customScaleName[]);
chan = '/Dev1/ai2'  # Location of the channel (this should be a physical channel, but it will be used as a virtual channel?)
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
rate = pydaqmx.float64(100)  # The sampling rate in samples per second per channel. If you use an external source for the Sample Clock, set this value to the maximum expected rate of that clock.
edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
sampMode = pydaqmx.DAQmx_Val_FiniteSamps  # Acquire samples continuously or just a finite number of samples
sampPerChan = pydaqmx.uInt64(2)  # Total number of sample to acquire for each channel
pydaqmx.DAQmxCfgSampClkTiming(handle, source, rate, edge, sampMode, sampPerChan)

#int32 __CFUNC DAQmxGetAIDevScalingCoeff(TaskHandle taskHandle, const char channel[], float64 *data, uInt32 arraySizeInElements);
coeffArray = numpy.zeros(100,dtype=ctypes.c_double())
pydaqmx.DAQmxGetAIDevScalingCoeff(handle,'/Dev1/ai2',coeffArray.data,100)
print coeffArray

# int32 DAQmxReadBinaryI16 (TaskHandle taskHandle, int32 numSampsPerChan, float64 timeout, bool32 fillMode, int16 readArray[], uInt32 arraySizeInSamps, int32 *sampsPerChanRead, bool32 *reserved);
read = pydaqmx.int32()  # Variable that will hold the value of how many samples we actually read (This gives us the freedom of putting in any sized dataBuffer and know exactly how much data is in it)
nSampsPerChan = -1  # -1 in finite mode means wait until all samples are collected and read them
timeout = -1  # -1 means wait indefinitely to read the samples
fillMode = pydaqmx.DAQmx_Val_GroupByChannel  # Controls organization of output. Specifies if you want to prioritize by lowest channel or lowest sample (if you have mutiple channels each getting multiple samples)
dataBuffer = numpy.zeros(100,dtype=pydaqmx.int16())
dataBufferFloat= numpy.zeros(100,dtype=pydaqmx.float64())
arrSize = pydaqmx.uInt32(len(dataBuffer))
# sampsPerChanRead = ctypes.byref(read)  # The number of samples we actually read
#pydaqmx.DAQmxStartTask(handle)
#pydaqmx.DAQmxReadBinaryI16(handle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize, sampsPerChanRead, None)  # This is the line when you actually read the voltage
pydaqmx.DAQmxReadBinaryI16(handle, nSampsPerChan, timeout, fillMode, dataBuffer, arrSize, ctypes.byref(read),None)  # This is the line when you actually read the voltage
#pydaqmx.DAQmxReadAnalogF64(handle, nSampsPerChan, timeout, fillMode, dataBufferFloat, arrSize, ctypes.byref(read),None)  # This is the line when you actually read the voltage
pydaqmx.DAQmxStopTask(handle)
pydaqmx.DAQmxClearTask(handle)

print dataBuffer
print dataBufferFloat