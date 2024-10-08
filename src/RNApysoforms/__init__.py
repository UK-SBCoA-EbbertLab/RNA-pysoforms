# Import necessary functions from local modules
from .shorten_gaps import shorten_gaps  # Function to shorten gaps in data
from .to_intron import to_intron        # Function to convert exons to introns
from .set_axis import set_axis          # Function to set axis properties for plot
from .read_gtf import read_gtf          # Function to read and parse GTF (Gene Transfer Format) files
from .read_expression_matrix import read_expression_matrix # Function to load counts matrix
from .gene_filtering import gene_filtering # Function to filter by gene_name 
from .calculate_exon_number import calculate_exon_number ## Function to calculate exon number if missing
from .make_plot import make_plot
from .make_traces import make_traces

# Define the public API of this module by specifying which functions to expose when imported
__all__ = ['shorten_gaps', 'to_intron', 'set_axis', "read_gtf", "make_transcript_structure_traces",
           "read_expression_matrix", "gene_filtering", "calculate_exon_number", "make_transcript_expression_traces",
           "make_plot"]

