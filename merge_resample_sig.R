suppressPackageStartupMessages({
  library(spectrolab)
  library(readr)
})

# Bronze Instrument No.: 2212118
# Silver Instrument No.: 1202103

# Parse arguments -------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
default_input <- Sys.getenv("SIG_RESAMPLE_INPUT", unset = getwd())
default_output_dir <- Sys.getenv("SIG_RESAMPLE_OUTPUT", unset = getwd())
default_output_file <- "merged_spectra.csv"

input_dir <- if (length(args) >= 1 && nzchar(args[[1]])) args[[1]] else default_input
output_dir <- if (length(args) >= 2 && nzchar(args[[2]])) args[[2]] else default_output_dir
output_file <- if (length(args) >= 3 && nzchar(args[[3]])) args[[3]] else default_output_file
output_path <- file.path(output_dir, output_file)

if (!dir.exists(input_dir)) {
  stop("Input directory not found: ", normalizePath(input_dir, mustWork = FALSE))
}

if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

# Load and preprocess spectra -------------------------------------------------
spectra <- read_spectra(path = input_dir)

if (nrow(spectra) == 0) {
  stop("No spectra were loaded from ", normalizePath(input_dir))
}

splice_at <- guess_splice_at(spectra)
aligned <- match_sensors(spectra, splice_at = splice_at)
smoothed <- smooth(aligned)
resampled <- resample(smoothed, new_bands = 400:2500, fwhm = 10)

# Convert to data frame -------------------------------------------------------
spectra_df <- as.data.frame(resampled)

# Export ----------------------------------------------------------------------
write_csv(spectra_df, output_path)
message("Merged spectra written to: ", normalizePath(output_path, mustWork = FALSE))
