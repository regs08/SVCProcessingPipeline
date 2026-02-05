"""
SigFileProcessor class for processing .sig files with configurable correction values.
"""

import json
import os
import re
from pathlib import Path
from typing import Literal, List, Dict, Set, Optional, Union
from os.path import abspath, expanduser


class SigFileProcessor:
    """Process .sig files with configurable correction types."""
    
    # Default correction type configurations
    DEFAULT_CORRECTION_TYPES = {
        'bronze': "2520.4",
        'silver': "2517.9"
    }
    
    # Default instrument number mappings
    DEFAULT_INSTRUMENT_NUMBERS = {
        'bronze': "2212118",
        'silver': "1202103"
    }

    @classmethod
    def load_default_correction_types(cls, config_path: Union[str, Path]) -> Dict[str, str]:
        """
        Load predefined correction-type end-line values from a JSON file and set DEFAULT_CORRECTION_TYPES.

        Expected JSON format (flat mapping):
            {"bronze": "2520.4", "silver": "2517.9"}
        """
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
        """
        Initialize the SigFileProcessor with configurable correction parameters.
        
        Args:
            correction_value (str, optional): The correction value to truncate at (e.g., "2517.9", "2520.4")
            instrument_number (str, optional): Custom instrument number for detection
            correction_type (str, optional): Predefined correction type ('bronze' or 'silver') - for backward compatibility
            correction_config (dict, optional): Custom configuration dict with 'end_line' and 'instrument_number' keys
            
        Examples:
            # Primary method: Pass correction value directly
            processor = SigFileProcessor("2517.9")
            processor = SigFileProcessor("2520.4")
            
            # With instrument number
            processor = SigFileProcessor("2517.9", instrument_number="1202103")
            
            # Backward compatibility with predefined types
            processor = SigFileProcessor(correction_type='silver')
            
            # Using custom config
            processor = SigFileProcessor(correction_config={
                'end_line': '2520.4',
                'instrument_number': '2212118'
            })
        """
        # No need for separate parser - we'll use existing SpecDAL infrastructure
        
        # Handle different initialization methods
        if correction_config:
            # Custom configuration provided
            self.end_line_value = correction_config.get('end_line')
            self.instrument_number = correction_config.get('instrument_number')
            self.correction_type = correction_config.get('name', 'custom')
            
        elif correction_value is not None:
            # Primary method: Correction value provided directly
            self.end_line_value = correction_value
            self.instrument_number = instrument_number
            self.correction_type = 'custom'
            
        elif correction_type:
            # Backward compatibility: Predefined type provided
            if correction_type not in self.DEFAULT_CORRECTION_TYPES:
                raise ValueError(f"Invalid correction_type specified. Use 'bronze' or 'silver'. Got: {correction_type}")
            
            self.correction_type = correction_type
            self.end_line_value = self.DEFAULT_CORRECTION_TYPES[correction_type]
            self.instrument_number = self.DEFAULT_INSTRUMENT_NUMBERS[correction_type]
            
        else:
            raise ValueError("Must provide either correction_value, correction_type, or correction_config")
        
        # Validate required values
        if not self.end_line_value or self.end_line_value.strip() == "":
            raise ValueError("correction_value must be provided and cannot be empty")
    
    def process_sig_files(self, input_folder: str, output_folder: str, verbose: bool = False) -> None:
        """
        Processes .sig files based on the correction configuration specified in the constructor.

        Args:
            input_folder (str): The path to the input folder containing .sig files.
            output_folder (str): The path to the output folder for processed files.
            verbose (bool): Whether to print verbose output (follows SpecDAL pattern).
        """
        end_line_start = self.end_line_value
        
        # Use SpecDAL's path handling pattern
        input_folder = abspath(expanduser(input_folder))
        output_folder = abspath(expanduser(output_folder))
        
        # Create output folder if it doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            if verbose:
                print(f"Created output folder: {output_folder}")

        processed_count = 0
        
        # Use SpecDAL's file discovery pattern
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
        """
        Process a single .sig file by truncating at the specified line.
        
        Args:
            input_file_path (str): Path to the input .sig file
            output_file_path (str): Path to the output .sig file
            end_line_start (str): The line start pattern to truncate at
        """
        with open(input_file_path, 'r') as input_file, open(output_file_path, 'w') as output_file:
            target_found = True
            for line in input_file:
                if target_found:
                    output_file.write(line)
                if line.startswith(end_line_start):
                    target_found = False
    
    def get_supported_correction_types(self) -> list:
        """
        Get the list of supported predefined correction types.
        
        Returns:
            list: List of supported correction types
        """
        return list(self.DEFAULT_CORRECTION_TYPES.keys())
    
    def get_correction_end_line(self) -> str:
        """
        Get the end line pattern for the current correction configuration.
        
        Returns:
            str: The end line pattern
        """
        return self.end_line_value
    
    def get_correction_config(self) -> dict:
        """
        Get the current correction configuration.
        
        Returns:
            dict: Dictionary with correction configuration
        """
        return {
            'correction_type': self.correction_type,
            'end_line_value': self.end_line_value,
            'instrument_number': self.instrument_number
        }
    
    def extract_instrument_from_file(self, file_path: str) -> Optional[str]:
        """
        Extract the instrument value from a single SIG file using SpecDAL's existing pattern.
        
        Args:
            file_path (str): Path to the SIG file
            
        Returns:
            Optional[str]: The instrument value or None if not found
        """
        try:
            with open(abspath(expanduser(file_path)), 'r') as f:
                for line in f:
                    if line.startswith('instrument='):
                        # Extract the instrument value after the '=' sign
                        instrument_value = line.split('=', 1)[1].strip()
                        return instrument_value
        except (FileNotFoundError, IOError, IndexError):
            pass
        
        return None
    
    def get_file_metadata(self, file_path: str) -> dict:
        """
        Extract metadata from a SIG file using SpecDAL's existing reader pattern.
        
        Args:
            file_path (str): Path to the SIG file
            
        Returns:
            dict: Dictionary of metadata fields
        """
        metadata = {}
        try:
            with open(abspath(expanduser(file_path)), 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('data='):
                        parts = line.strip().split('=', 1)
                        if len(parts) == 2:
                            field_name = parts[0].strip()
                            field_value = parts[1].strip()
                            metadata[field_name] = field_value
        except (FileNotFoundError, IOError):
            pass
        
        return metadata
    
    def _determine_correction_type(self, instrument: str) -> str:
        """
        Determine correction type based on instrument number.
        
        Args:
            instrument (str): The instrument string from SIG file
            
        Returns:
            str: 'bronze', 'silver', 'custom', or 'unknown'
        """
        if not instrument:
            return 'unknown'
        
        # Extract instrument number from the instrument string
        # Format is typically "HI: 1202103 (HR-1024i)" or similar
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
        """
        Extract instrument name based on instrument number.
        
        Args:
            instrument (str): The instrument string from SIG file
            
        Returns:
            str: 'Bronze', 'Silver', 'Custom', or 'Unknown'
        """
        if not instrument:
            return "Unknown"
        
        # Extract instrument number and determine type
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
        """
        Check instrument consistency across all SIG files in a folder.
        
        Args:
            folder_path (str): Path to the folder containing SIG files
            
        Returns:
            Dict containing:
                - 'consistent': bool - Whether all files have the same instrument
                - 'instrument': str - The instrument value (if consistent) or None
                - 'instrument_name': str - The instrument name for display
                - 'files_by_instrument': Dict[str, List[str]] - Files grouped by instrument
                - 'total_files': int - Total number of SIG files processed
                - 'warnings': List[str] - Any warnings about inconsistencies
        """
        # Use SpecDAL's path handling pattern
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
        
        # Process all SIG files in the folder (sorted like SpecDAL)
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
        
        # Check consistency
        unique_instruments = list(files_by_instrument.keys())
        is_consistent = len(unique_instruments) == 1
        
        if is_consistent:
            instrument_value = unique_instruments[0]
            if instrument_value == "Unknown":
                warnings.append("All files have unknown instrument values")
                instrument_name = "Unknown"
            else:
                # Extract instrument name as Bronze or Silver
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
    
    def print_instrument_summary(self, folder_path: str) -> None:
        """
        Print a summary of instrument consistency for SIG files in a folder.
        
        Args:
            folder_path (str): Path to the folder containing SIG files
        """
        result = self.check_instrument_consistency(folder_path)
        
        print(f"=== Instrument Consistency Check for {folder_path} ===")
        print(f"Total SIG files processed: {result['total_files']}")
        
        if result['consistent']:
            if result['instrument'] and result['instrument'] != "Unknown":
                print(f"✅ All files belong to instrument: {result['instrument_name']}")
            else:
                print("⚠️ All files have unknown instrument values")
        else:
            print("⚠️ Files have different instrument values:")
            for instrument, files in result['files_by_instrument'].items():
                print(f"  {instrument}: {len(files)} files")
        
        if result['warnings']:
            print("\nWarnings:")
            for warning in result['warnings']:
                print(f"  - {warning}")
        
        print()
    
    def process_and_create_collection(self, input_folder: str, output_folder: str, 
                                    collection_name: str = None, verbose: bool = False):
        """
        Process SIG files and create a SpecDAL Collection from the processed files.
        
        Args:
            input_folder (str): Path to the input folder containing SIG files
            output_folder (str): Path to the output folder for processed files
            collection_name (str): Name for the collection (defaults to folder name)
            verbose (bool): Whether to print verbose output
            
        Returns:
            Collection: SpecDAL Collection object with processed spectra
        """
        # Process the files first
        self.process_sig_files(input_folder, output_folder, verbose=verbose)
        
        # Import Collection here to avoid circular imports
        try:
            from specdal.containers.collection import Collection
        except ImportError:
            raise ImportError("SpecDAL Collection class not available. Make sure SpecDAL is properly installed.")
        
        # Create collection name from folder if not provided
        if collection_name is None:
            collection_name = os.path.basename(abspath(expanduser(input_folder)))
        
        # Create collection and read processed files
        collection = Collection(name=collection_name)
        if verbose:
            print(f"Creating collection '{collection_name}' from processed files...")
        
        collection.read(directory=output_folder, verbose=verbose)
        
        if verbose:
            print(f"Collection created with {len(collection)} spectra")
        
        return collection
