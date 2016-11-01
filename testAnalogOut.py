import PyDAQmx as pydaqmx  # Python library to execute NI-DAQmx code
import ctypes # Lets us use data types compatible with C code
import numpy as np
import time


outScan = pydaqmx.TaskHandle()
taskName = ''  # Name of the task (I don't know when this would not be an empty string...)
input1Pointer = ctypes.byref(outScan)  # Equivalent to &setStates in C, the pointer to the task handle
pydaqmx.DAQmxCreateTask(taskName, input1Pointer)

chan = 'Dev1/ao1'  # Location of the channel (this should be a physical channel, but it will be used as a virtual channel?)
chanName = ""  # Name(s) to assign to the created virtual channel(s). "" means physical channel name will be used
type = pydaqmx.DAQmx_Val_Sine  # Is this singled/double referenced, differential, etc.\
freq = pydaqmx.float64(10.0)
amp = pydaqmx.float64(10.0)
offset = pydaqmx.float64(0)
#pydaqmx.DAQmxCreateAOFuncGenChan(outScan, chan, chanName, type, freq, amp, offset)

minVal = pydaqmx.float64(-10.0)
maxVal = pydaqmx.float64(10.0)
units = pydaqmx.DAQmx_Val_Volts
pydaqmx.DAQmxCreateAOVoltageChan(outScan, chan, chanName, minVal, maxVal, units, 0)

fSamp = 5000
nSamp = 1000
amp = 10
source = None  # If you use an external clock, specify here, otherwise it should be None
rate = pydaqmx.float64(fSamp) # The sampling rate in samples per second per channel. If you use an external source for the Sample Clock, set this value to the maximum expected rate of that clock.
edge = pydaqmx.DAQmx_Val_Rising  # Which edge of the clock (Rising/Falling) to acquire data
sampMode = pydaqmx.DAQmx_Val_ContSamps  # Acquire samples continuously or just a finite number of samples
sampPerChan = pydaqmx.uInt64(nSamp*1)  # Total number of sample to acquire for each channel
pydaqmx.DAQmxCfgSampClkTiming(outScan, source, rate, edge, sampMode, sampPerChan)

#writeArray = np.zeros((int(nSamp),), dtype=np.float64)
x = np.array(range(nSamp*1))/5.0
writeArray = np.array(amp*np.sin(x), dtype=np.float64)
written = pydaqmx.int32()
nSampPerChan = pydaqmx.int32(nSamp)
#pydaqmx.DAQmxWriteAnalogScalarF64(outScan, 0, 1, pydaqmx.float64(10.0), None)
# pydaqmx.DAQmxWriteAnalogF64(outScan, nSampPerChan, pydaqmx.bool32(0), pydaqmx.DAQmx_Val_WaitInfinitely, pydaqmx.DAQmx_Val_GroupByChannel, writeArray, ctypes.byref(written), None)

pydaqmx.DAQmxWriteAnalogF64(outScan, nSampPerChan, pydaqmx.bool32(0), pydaqmx.DAQmx_Val_WaitInfinitely,
                            pydaqmx.DAQmx_Val_GroupByChannel, writeArray, ctypes.byref(written), None)
for i in range(10):
    # pydaqmx.DAQmxWriteAnalogF64(outScan, nSampPerChan, pydaqmx.bool32(0), pydaqmx.DAQmx_Val_WaitInfinitely,
    #                             pydaqmx.DAQmx_Val_GroupByChannel, writeArray, ctypes.byref(written), None)
    pydaqmx.DAQmxStartTask(outScan)
    time.sleep(1)
    pydaqmx.DAQmxStopTask(outScan)
