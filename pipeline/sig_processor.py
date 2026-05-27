import json
import os
import re
from pathlib import Path
from typing import Literal, List, Dict, Set, Optional, Union
from os.path import abspath, expanduser


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

    @classmethod
    def load_default_correction_types(cls, config_path: Union[str, Path]) -> Dict[str, str]:
        """Load correction-type end-line values from a JSON file and update DEFAULT_CORRECTION_TYPES."""
        path_obj = Path(config_path).expanduser()
        if not path_obj.exists():
            raise FileNotFoundError(f"Correction-types config file not found: {path_obj}")

        with path_obj.open("r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                "Correction-types config JSON must be an object mapping correction_type -> end_line string."
            )

        normalized: Dict[str, str] = {}
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

        cls.DEFAULT_CORRECTION_TYPES = dict(normalized)
        return cls.DEFAULT_CORRECTION_TYPES

    def __init__(self, correction_value: str = None, instrument_number: str = None,
                 correction_type: str = None, correction_config: dict = None):
        if correction_config:
            self.end_line_value = correction_config.get('end_line')
            self.instrument_number = correction_config.get('instrument_number')
            self.correction_type = correction_config.get('name', 'custom')

        elif correction_value is not None:
            self.end_line_value = correction_value
            self.instrument_number = instrument_number
            self.correction_type = 'custom'

        elif correction_type:
            if correction_type not in self.DEFAULT_CORRECTION_TYPES:
                raise ValueError(f"Invalid correction_type specified. Use 'bronze' or 'silver'. Got: {correction_type}")

            self.correction_type = correction_type
            self.end_line_value = self.DEFAULT_CORRECTION_TYPES[correction_type]
            self.instrument_number = self.DEFAULT_INSTRUMENT_NUMBERS[correction_type]

        else:
            raise ValueError("Must provide either correction_value, correction_type, or correction_config")

        if not self.end_line_value or self.end_line_value.strip() == "":
            raise ValueError("correction_value must be provided and cannot be empty")

    def process_sig_files(self, input_folder: str, output_folder: str, verbose: bool = False) -> None:
        """Process all .sig files in input_folder and write truncated copies to output_folder."""
        end_line_start = self.end_line_value

        input_folder = abspath(expanduser(input_folder))
        output_folder = abspath(expanduser(output_folder))

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            if verbose:
                print(f"Created output folder: {output_folder}")

        processed_count = 0

        for filename in sorted(os.listdir(input_folder)):
            if filename.endswith('.sig'):
                input_file_path = os.path.join(input_folder, filename)
                output_file_path = os.path.join(output_folder, filename)

                try:
                    if verbose:
                        print(f"Processing: {filename}")
                    self._process_single_file(input_file_path, output_file_path, end_line_start)
                    processed_count += 1
                    if verbose:
                        print(f"Processed: {filename}")
                except Exception as e:
                    print(f"Error processing {filename}: {e}")

        if verbose:
            print(f"Processing complete. {processed_count} files processed.")

    def _process_single_file(self, input_file_path: str, output_file_path: str, end_line_start: str) -> None:
        with open(input_file_path, 'r') as input_file, open(output_file_path, 'w') as output_file:
            target_found = True
            for line in input_file:
                if target_found:
                    output_file.write(line)
                if line.startswith(end_line_start):
                    target_found = False

    def get_supported_correction_types(self) -> list:
        return list(self.DEFAULT_CORRECTION_TYPES.keys())

    def get_correction_end_line(self) -> str:
        return self.end_line_value

    def get_correction_config(self) -> dict:
        return {
            'correction_type': self.correction_type,
            'end_line_value': self.end_line_value,
            'instrument_number': self.instrument_number
        }

    def extract_instrument_from_file(self, file_path: str) -> Optional[str]:
        try:
            with open(abspath(expanduser(file_path)), 'r') as f:
                for line in f:
                    if line.startswith('instrument='):
                        return line.split('=', 1)[1].strip()
        except (FileNotFoundError, IOError, IndexError):
            pass
        return None

    def get_file_metadata(self, file_path: str) -> dict:
        metadata = {}
        try:
            with open(abspath(expanduser(file_path)), 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('data='):
                        parts = line.strip().split('=', 1)
                        if len(parts) == 2:
                            metadata[parts[0].strip()] = parts[1].strip()
        except (FileNotFoundError, IOError):
            pass
        return metadata

    def _determine_correction_type(self, instrument: str) -> str:
        if not instrument:
            return 'unknown'
        match = re.search(r'(\d{7})', instrument)
        if match:
            instrument_number = match.group(1)
            if instrument_number == self.DEFAULT_INSTRUMENT_NUMBERS['silver']:
                return 'silver'
            elif instrument_number == self.DEFAULT_INSTRUMENT_NUMBERS['bronze']:
                return 'bronze'
            elif self.instrument_number and instrument_number == self.instrument_number:
                return 'custom'
        return 'unknown'

    def _extract_instrument_name(self, instrument: str) -> str:
        if not instrument:
            return "Unknown"
        match = re.search(r'(\d{7})', instrument)
        if match:
            instrument_number = match.group(1)
            if instrument_number == self.DEFAULT_INSTRUMENT_NUMBERS['silver']:
                return 'Silver'
            elif instrument_number == self.DEFAULT_INSTRUMENT_NUMBERS['bronze']:
                return 'Bronze'
            elif self.instrument_number and instrument_number == self.instrument_number:
                return 'Custom'
        return 'Unknown'

    def check_instrument_consistency(self, folder_path: str) -> Dict[str, any]:
        """Check that all .sig files in folder_path share the same instrument."""
        folder_path = abspath(expanduser(folder_path))

        if not os.path.exists(folder_path):
            return {
                'consistent': False,
                'instrument': None,
                'instrument_name': 'Unknown',
                'files_by_instrument': {},
                'total_files': 0,
                'warnings': [f"Folder does not exist: {folder_path}"]
            }

        files_by_instrument = {}
        warnings = []
        total_files = 0

        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith('.sig'):
                file_path = os.path.join(folder_path, filename)
                instrument = self.extract_instrument_from_file(file_path)
                total_files += 1

                if instrument is None:
                    warnings.append(f"Could not extract instrument from: {filename}")
                    instrument = "Unknown"

                if instrument not in files_by_instrument:
                    files_by_instrument[instrument] = []
                files_by_instrument[instrument].append(filename)

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
