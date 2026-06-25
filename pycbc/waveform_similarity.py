%matplotlib inline
# We learn about the potential parameters of a source by comparing it to many different waveforms
# each of which represents a possible source with different properties. 
import pylab
from pycbc.waveform import get_td_waveform

# We can directly compare how similar waveforms are to each other using an inner product between then called 
# a 'match'. This maximizes over the possible time of arrival and phase. We'll generate a reference waveform
# which we'll compare to.
m1 = m2 = 20
f_lower = 20
approximant = "SEOBNRv4"
delta_t = 1.0 / 2048
hp, _ = get_td_waveform(approximant=approximant,
                         mass1=m1, mass2=m2,
                         delta_t=delta_t, f_lower=f_lower)
pylab.plot(hp.sample_times, hp)
pylab.xlabel('Time (s)')
pylab.ylabel('Strain')


