# `config/calibrations/` - Optional Sensor Calibration Files

Place per-run calibration JSON files here when a run needs instrument-specific
end-line values outside the built-in defaults. Files named
`<input_dir_name>.json` are auto-detected by `RunConfig.apply_sensor_calibrations()`.

Expected shape:

```json
{
  "bronze": "2520.4",
  "silver": "2517.9"
}
```

These files should not contain raw spectra, machine paths, GPS coordinates, or
private sample identifiers.
