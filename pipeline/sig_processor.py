from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pipeline.sig_files import find_sig_files


class SigFileProcessor:
    """Process .sig files with configurable correction types."""

    DEFAULT_CORRECTION_TYPES = {
        'bronze': "2520.4",
        'silver': "2517.9"
    }

    DEFAULT_INSTRUMENT_NUMBERS = {
        'bronze': "2212118",
        'silver': "1202103"
    }

    @staticmethod
    def parse_correction_types_file(config_path: str | Path) -> dict[str, str]:
        """Parse a sensor-calibration JSON file into a correction_type -> end_line mapping.

        Pure — does not touch ``DEFAULT_CORRECTION_TYPES``. Used by
        :meth:`load_default_correction_types` and by callers (such as
        ``RunConfig``) that want a resolved calibration table for a single
        instance without changing the class-wide defaults.
        """
        path_obj = Path(config_path).expanduser().resolve()
        if not path_obj.exists():
            raise FileNotFoundError(f"Correction-types config file not found: {path_obj}")

        with path_obj.open("r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                "Correction-types config JSON must be an object mapping correction_type -> end_line string."
            )

        normalized: dict[str, str] = {}
        for key, value in data.items():
            if key is None:
                continue
            correction_type = str(key).strip().lower()
            if not correction_type:
                continue
            end_line_value = str(value).strip()
            if not end_line_value:
                raise ValueError(f"End-line value for correction type '{correction_type}' is empty in {path_obj}")
            normalized[correction_type] = end_line_value

        if not normalized:
            raise ValueError(f"No correction types found in {path_obj}")

        return normalized

    @classmethod
    def load_default_correction_types(cls, config_path: str | Path) -> dict[str, str]:
        """Load correction-type end-line values from a JSON file and update DEFAULT_CORRECTION_TYPES."""
        cls.DEFAULT_CORRECTION_TYPES = cls.parse_correction_types_file(config_path)
        return cls.DEFAULT_CORRECTION_TYPES

    def __init__(self, correction_value: str | None = None, instrument_number: str | None = None,
                 correction_type: str | None = None, correction_config: dict | None = None,
                 correction_types: dict[str, str] | None = None,
                 instrument_numbers: dict[str, str] | None = None,
                 logger: logging.Logger | None = None):
        self._logger = logger
        # Instance-level calibration tables, defaulting to the class-wide
        # defaults. Passing these explicitly lets a caller (e.g. RunConfig)
        # resolve per-run calibration without mutating DEFAULT_CORRECTION_TYPES /
        # DEFAULT_INSTRUMENT_NUMBERS, which are shared, process-wide state.
        self._correction_types = correction_types if correction_types is not None else self.DEFAULT_CORRECTION_TYPES
        self._instrument_numbers = (
            instrument_numbers if instrument_numbers is not None else self.DEFAULT_INSTRUMENT_NUMBERS
        )

        if correction_config:
            self.end_line_value = correction_config.get('end_line')
            self.instrument_number = correction_config.get('instrument_number')
            self.correction_type = correction_config.get('name', 'custom')

        elif correction_value is not None:
            self.end_line_value = correction_value
            self.instrument_number = instrument_number
            self.correction_type = 'custom'

        elif correction_type:
            if correction_type not in self._correction_types:
                raise ValueError(f"Invalid correction_type specified. Use 'bronze' or 'silver'. Got: {correction_type}")

            self.correction_type = correction_type
            self.end_line_value = self._correction_types[correction_type]
            self.instrument_number = self._instrument_numbers[correction_type]

        else:
            raise ValueError("Must provide either correction_value, correction_type, or correction_config")

        if not self.end_line_value or self.end_line_value.strip() == "":
            raise ValueError("correction_value must be provided and cannot be empty")

    def _log_info(self, message: str) -> None:
        """Route info-level messages through a logger if one was supplied, else print."""
        if self._logger is not None:
            self._logger.info(message)
        else:
            print(message)

    def _log_error(self, message: str) -> None:
        """Route error-level messages through a logger if one was supplied, else print."""
        if self._logger is not None:
            self._logger.error(message)
        else:
            print(message)

    def process_sig_files(self, input_folder: str, output_folder: str, verbose: bool = False) -> None:
        """Process all .sig files in input_folder and write truncated copies to output_folder."""
        end_line_start = self.end_line_value

        input_dir = Path(input_folder).expanduser().resolve()
        output_dir = Path(output_folder).expanduser().resolve()

        if not output_dir.exists():
            output_dir.mkdir(parents=True)
            if verbose:
                self._log_info(f"Created output folder: {output_dir}")

        processed_count = 0

        for entry in find_sig_files(input_dir):
            output_file_path = output_dir / entry.name

            try:
                if verbose:
                    self._log_info(f"Processing: {entry.name}")
                self._process_single_file(entry, output_file_path, end_line_start)
                processed_count += 1
                if verbose:
                    self._log_info(f"Processed: {entry.name}")
            except Exception as e:
                self._log_error(f"Error processing {entry.name}: {e}")

        if verbose:
            self._log_info(f"Processing complete. {processed_count} files processed.")

    def _process_single_file(self, input_file_path: Path, output_file_path: Path, end_line_start: str) -> None:
        with input_file_path.open('r') as input_file, output_file_path.open('w') as output_file:
            target_found = True
            for line in input_file:
                if target_found:
                    output_file.write(line)
                if line.startswith(end_line_start):
                    target_found = False

    def get_supported_correction_types(self) -> list:
        """Correction-type names this instance knows about (e.g. 'bronze', 'silver')."""
        return list(self._correction_types.keys())

    def extract_instrument_from_file(self, file_path: str) -> str | None:
        try:
            with Path(file_path).expanduser().resolve().open('r') as f:
                for line in f:
                    if line.startswith('instrument='):
                        return line.split('=', 1)[1].strip()
        except (FileNotFoundError, IOError, IndexError):
            pass
        return None

    def get_file_metadata(self, file_path: str) -> dict:
        metadata = {}
        try:
            with Path(file_path).expanduser().resolve().open('r') as f:
                for line in f:
                    if '=' in line and not line.startswith('data='):
                        parts = line.strip().split('=', 1)
                        if len(parts) == 2:
                            metadata[parts[0].strip()] = parts[1].strip()
        except (FileNotFoundError, IOError):
            pass
        return metadata

    def _extract_instrument_name(self, instrument: str) -> str:
        if not instrument:
            return "Unknown"
        match = re.search(r'(\d{7})', instrument)
        if match:
            instrument_number = match.group(1)
            if instrument_number == self._instrument_numbers['silver']:
                return 'Silver'
            elif instrument_number == self._instrument_numbers['bronze']:
                return 'Bronze'
            elif self.instrument_number and instrument_number == self.instrument_number:
                return 'Custom'
        return 'Unknown'

    def check_instrument_consistency(self, folder_path: str) -> dict[str, Any]:
        """Check that all .sig files in folder_path share the same instrument."""
        folder = Path(folder_path).expanduser().resolve()

        if not folder.exists():
            return {
                'consistent': False,
                'instrument': None,
                'instrument_name': 'Unknown',
                'files_by_instrument': {},
                'total_files': 0,
                'warnings': [f"Folder does not exist: {folder}"]
            }

        files_by_instrument = {}
        warnings = []
        total_files = 0

        for entry in find_sig_files(folder):
            instrument = self.extract_instrument_from_file(str(entry))
            total_files += 1

            if instrument is None:
                warnings.append(f"Could not extract instrument from: {entry.name}")
                instrument = "Unknown"

            if instrument not in files_by_instrument:
                files_by_instrument[instrument] = []
            files_by_instrument[instrument].append(entry.name)

        unique_instruments = list(files_by_instrument.keys())
        is_consistent = len(unique_instruments) == 1

        if is_consistent:
            instrument_value = unique_instruments[0]
            if instrument_value == "Unknown":
                warnings.append("All files have unknown instrument values")
                instrument_name = "Unknown"
            else:
                instrument_name = self._extract_instrument_name(instrument_value)
        else:
            instrument_value = None
            instrument_name = "Mixed"
            for instrument, files in files_by_instrument.items():
                if len(files) > 1:
                    warnings.append(f"Files with instrument '{instrument}': {', '.join(files)}")
                else:
                    warnings.append(f"File with instrument '{instrument}': {files[0]}")

        return {
            'consistent': is_consistent,
            'instrument': instrument_value,
            'instrument_name': instrument_name,
            'files_by_instrument': files_by_instrument,
            'total_files': total_files,
            'warnings': warnings
        }
