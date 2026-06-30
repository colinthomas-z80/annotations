from gwpy.timeseries import TimeSeries

# event 1126259446

step = 10
count = 10

for detector in ["H1", "L1"]:
    time_start = 1126259400
    for seg in range(count):
        time_start = time_start + (seg-1) * step
        time_end = time_start + step

        strain = TimeSeries.fetch_open_data(
            detector,
            time_start,
            time_end
        )

        name = f"{detector}_strain_{seg}.hdf5"

        strain.write(name, format="hdf5")

        s = TimeSeries.read(name)
        s.name = f"{detector}:Strain"
        s.write(f"{detector}_strain_{seg}.gwf", format="gwf")
