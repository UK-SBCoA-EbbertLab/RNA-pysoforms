import pandas as pd  # Import pandas for data manipulation
import numpy as np  # Import numpy for numerical operations
import plotly.graph_objects as go  # Import Plotly for creating plots
from typing import List, Union  # Import type annotations for functions

def shorten_gaps(exons: pd.DataFrame, introns: pd.DataFrame, 
                 group_var: Union[str, List[str]] = None, 
                 target_gap_width: int = 100) -> pd.DataFrame:
    """
    Shorten the gaps between exons and introns for more compact transcript visualization.

    Parameters:
    -----------
    exons : pd.DataFrame
        DataFrame containing exon information.
    introns : pd.DataFrame
        DataFrame containing intron information.
    group_var : str or List[str], optional
        Column(s) used to group transcripts. Default is None.
    target_gap_width : int, optional
        Maximum allowed width for gaps between exons. Default is 100.

    Returns:
    --------
    pd.DataFrame
        DataFrame with shortened intron gaps and rescaled coordinates.
    """
    # Ensure required columns are present in both the exons and introns DataFrames
    for df in [exons, introns]:
        assert all(col in df.columns for col in ['start', 'end', 'strand', 'seqnames']), \
            "Both exons and introns DataFrames must have 'start', 'end', 'strand', and 'seqnames' columns"

    # Ensure each DataFrame has a 'type' column indicating 'exon' or 'intron'
    exons = _get_type(exons, "exons")  # Set 'type' to 'exon' for exons DataFrame
    introns = _get_type(introns, "introns")  # Set 'type' to 'intron' for introns DataFrame

    # Adjust the start and end positions of introns slightly to avoid overlap with exons
    introns = introns.copy()  # Copy to avoid modifying the original DataFrame
    introns['start'] += 1  # Increment start by 1 to avoid exon overlap
    introns['end'] -= 1  # Decrement end by 1 to avoid exon overlap

    # Identify gaps between exons
    gaps = _get_gaps(exons)  # Find gaps between exons on the same chromosome and strand

    # Map the identified gaps to the corresponding introns
    gap_map = _get_gap_map(introns, gaps)  # Map gaps to introns (or exons)

    # Shorten the gaps based on the target gap width
    introns_shortened = _get_shortened_gaps(introns, gaps, gap_map, group_var, target_gap_width)

    # If a group variable (e.g., transcript name) is provided, handle gaps at transcript starts
    if group_var:
        tx_start_gaps = _get_tx_start_gaps(exons, group_var)  # Identify gaps at transcript starts
        gap_map_tx_start = _get_gap_map(tx_start_gaps, gaps)  # Map gaps at transcript starts
        tx_start_gaps_shortened = _get_shortened_gaps(tx_start_gaps, gaps, gap_map_tx_start, group_var, target_gap_width)
        # Remove unnecessary columns from transcript start gaps
        tx_start_gaps_shortened = tx_start_gaps_shortened.drop(columns=['start', 'end', 'strand', 'seqnames'])
    else:
        tx_start_gaps_shortened = None  # No transcript start gaps if no group_var is provided

    # Rescale the coordinates of exons and introns after shortening the gaps
    rescaled_tx = _get_rescaled_txs(exons, introns_shortened, tx_start_gaps_shortened, group_var)
    
    return rescaled_tx  # Return the DataFrame with rescaled transcript coordinates

def _get_type(df: pd.DataFrame, df_type: str) -> pd.DataFrame:
    """
    Ensure the DataFrame has a 'type' column, indicating whether it's 'exon' or 'intron'.
    """
    if 'type' not in df.columns:  # If 'type' column doesn't exist
        df = df.copy()  # Copy DataFrame to avoid modifying the original
        df['type'] = 'exon' if df_type == 'exons' else 'intron'  # Set 'type' to 'exon' or 'intron'
    elif df_type == 'introns':  # Ensure intron DataFrame has only 'intron' in 'type' column
        assert all(df['type'] == 'intron'), "All 'type' values in the introns DataFrame must be 'intron'"
    return df  # Return the DataFrame with the 'type' column

def _get_gaps(exons: pd.DataFrame) -> pd.DataFrame:
    """
    Identify gaps between exons in a single chromosome and strand.

    Parameters:
    -----------
    exons : pd.DataFrame
        DataFrame containing exon information with 'seqnames', 'start', 'end', and 'strand'.

    Returns:
    --------
    pd.DataFrame
        DataFrame with start and end positions of gaps between exons.
    """
    # Ensure all exons are from a single chromosome and strand
    assert exons['seqnames'].nunique() == 1 and exons['strand'].nunique() == 1, \
        "Exons must be from a single chromosome and strand"

    # Sort exons by start position to process them sequentially
    exons_sorted = exons.sort_values('start')

    merged_exons = []  # List to store merged exon regions
    current_start = exons_sorted.iloc[0]['start']
    current_end = exons_sorted.iloc[0]['end']
    
    # Iterate over sorted exons to merge overlapping ones
    for _, exon in exons_sorted.iterrows():
        if exon['start'] > current_end:
            # Add the current merged exon to the list
            merged_exons.append({'start': current_start, 'end': current_end})
            # Start a new merged exon
            current_start = exon['start']
            current_end = exon['end']
        else:
            # Extend the current merged exon if overlapping
            current_end = max(current_end, exon['end'])

    # Append the last merged exon
    merged_exons.append({'start': current_start, 'end': current_end})

    # Identify gaps between consecutive merged exons
    gaps = []
    for i in range(1, len(merged_exons)):
        gap_start = merged_exons[i-1]['end'] + 1
        gap_end = merged_exons[i]['start'] - 1
        if gap_start <= gap_end:  # Only consider valid gaps
            gaps.append({'start': gap_start, 'end': gap_end})

    return pd.DataFrame(gaps)  # Return gaps as a DataFrame

def _get_tx_start_gaps(exons: pd.DataFrame, group_var: Union[str, List[str]]) -> pd.DataFrame:
    """
    Identify gaps at the start of each transcript based on the first exon.

    Parameters:
    -----------
    exons : pd.DataFrame
        DataFrame containing exon information.
    group_var : str or List[str]
        Column name(s) used to group transcripts.

    Returns:
    --------
    pd.DataFrame
        DataFrame containing gaps at the start of each transcript.
    """
    # Get the start of the first exon for each transcript (grouped by group_var)
    tx_starts = exons.groupby(group_var)['start'].min().reset_index()
    overall_start = exons['start'].min()  # Get the overall start of the first exon

    tx_start_gaps = tx_starts.copy()  # Create a copy of the start positions for modification
    tx_start_gaps['end'] = tx_start_gaps['start']  # Set the end of the gap to the transcript start
    tx_start_gaps['start'] = overall_start  # Set the start of the gap to the overall start
    tx_start_gaps['seqnames'] = exons['seqnames'].iloc[0]  # Use the same chromosome for all transcripts
    tx_start_gaps['strand'] = exons['strand'].iloc[0]  # Use the same strand for all transcripts

    return tx_start_gaps  # Return the DataFrame with transcript start gaps

def _get_gap_map(df: pd.DataFrame, gaps: pd.DataFrame) -> dict:
    """
    Map gaps to the corresponding introns or exons based on their start and end positions.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame containing exons or introns.
    gaps : pd.DataFrame
        DataFrame containing gaps.

    Returns:
    --------
    dict
        Dictionary with 'equal' gaps (exact matches) and 'pure_within' gaps (fully within an intron or exon).
    """
    equal_hits = []  # Store exact matches between gaps and introns/exons
    within_hits = []  # Store gaps that are fully within introns/exons

    for i, gap in gaps.iterrows():  # Loop through gaps
        for j, row in df.iterrows():  # Loop through exons/introns
            if gap['start'] == row['start'] and gap['end'] == row['end']:
                # If the gap matches the intron/exon exactly, record it as an equal match
                equal_hits.append({'gap_index': i, 'df_index': j})
            elif gap['start'] >= row['start'] and gap['end'] <= row['end']:
                # If the gap is completely inside the intron/exon, record it as a within match
                within_hits.append({'gap_index': i, 'df_index': j})

    equal_hits = pd.DataFrame(equal_hits)  # Convert equal matches to a DataFrame
    within_hits = pd.DataFrame(within_hits)  # Convert within matches to a DataFrame

    # Remove within hits that are also present in equal hits
    pure_within_hits = within_hits[~within_hits.apply(tuple, 1).isin(equal_hits.apply(tuple, 1))]

    # Return a dictionary of equal and pure_within gap matches
    return {'equal': equal_hits, 'pure_within': pure_within_hits}

def _get_shortened_gaps(df: pd.DataFrame, gaps: pd.DataFrame, gap_map: dict, 
                        group_var: Union[str, List[str]], target_gap_width: int) -> pd.DataFrame:
    """
    Shorten the gaps between exons and introns according to a target gap width.
    """
    df = df.copy()
    df['width'] = df['end'] - df['start'] + 1  # Calculate the width of each intron/exon

    df['shorten_type'] = 'none'  # Initialize a column to track the type of shortening

    # Check if 'df_index' exists in both 'equal' and 'pure_within'
    if 'equal' in gap_map and 'df_index' in gap_map['equal']:
        # Mark rows for shortening of type 'equal'
        df.loc[df.index.isin(gap_map['equal']['df_index']), 'shorten_type'] = 'equal'

    if 'pure_within' in gap_map and 'df_index' in gap_map['pure_within']:
        # Mark rows for shortening of type 'pure_within'
        df.loc[df.index.isin(gap_map['pure_within']['df_index']), 'shorten_type'] = 'pure_within'

    # Apply the shortening logic for "equal" type gaps
    df['shortened_width'] = np.where(
        (df['shorten_type'] == 'equal') & (df['width'] > target_gap_width),
        target_gap_width,
        df['width']
    )

    # Handle "pure_within" type gaps
    if 'pure_within' in gap_map and len(gap_map['pure_within']) > 0:
        
        overlapping_gap_indexes = gap_map['pure_within']['gap_index'].values

        if len(overlapping_gap_indexes) > 0:

            # Calculate the sum of the reduction in gap widths for each unique intron index
            sum_gap_diff = pd.DataFrame({
                'intron_indexes': gap_map['pure_within']['df_index'],
                'gap_width': gaps.loc[overlapping_gap_indexes, 'end'].values - gaps.loc[overlapping_gap_indexes, 'start'].values + 1
            })

            ## Reduce the widths
            sum_gap_diff['shortened_gap_width'] = np.where(
                sum_gap_diff['gap_width'] > target_gap_width, 
                target_gap_width, 
                sum_gap_diff['gap_width']
            )


            sum_gap_diff['shortened_gap_diff'] = sum_gap_diff['gap_width'] - sum_gap_diff['shortened_gap_width']


            # Sum the shortened gap differences for each intron to ensure proper shortening
            sum_gap_diff = sum_gap_diff.groupby('intron_indexes').agg(sum_shortened_gap_diff=('shortened_gap_diff', 'sum')).reset_index()

            # Add a new column initialized with NaN (equivalent to NA_integer_ in R)
            df["sum_shortened_gap_diff"] = np.nan

            # Set the "sum_shortened_gap_diff" column in df where the index is in "intron_indexes" from sum_gap_diff
            df.loc[df.index.isin(sum_gap_diff['intron_indexes']), 'sum_shortened_gap_diff'] = sum_gap_diff.set_index('intron_indexes')['sum_shortened_gap_diff']

            # Step 3: Apply the mutation to adjust the 'shortened_width' column
            df['shortened_width'] = np.where(
                df['sum_shortened_gap_diff'].isna(),
                df['shortened_width'],  # keep original shortened_width if sum_shortened_gap_diff is NaN
                df['width'] - df['sum_shortened_gap_diff']  # adjust shortened_width otherwise
            )

            # Step 4: Drop the 'sum_shortened_gap_diff' column
            df = df.drop(columns=['sum_shortened_gap_diff'])

            df = df.drop(columns=['shorten_type', 'width']).rename(columns={'shortened_width': 'width'})


    return df

def _get_rescaled_txs(exons: pd.DataFrame, introns_shortened: pd.DataFrame, 
                      tx_start_gaps_shortened: pd.DataFrame, 
                      group_var: Union[str, List[str]]) -> pd.DataFrame:
    """
    Rescale transcript coordinates based on shortened gaps.

    Parameters:
    -----------
    exons : pd.DataFrame
        DataFrame containing exon information.
    introns_shortened : pd.DataFrame
        DataFrame containing intron information with shortened gaps.
    tx_start_gaps_shortened : pd.DataFrame
        DataFrame containing rescaled transcript start gaps.
    group_var : str or List[str]
        Column(s) used to group transcripts.

    Returns:
    --------
    pd.DataFrame
        Rescaled transcript DataFrame with adjusted coordinates.
    """
    exons = exons.copy()  # Copy exons DataFrame to avoid modifying the original
    exons['width'] = exons['end'] - exons['start'] + 1  # Calculate the width of each exon

    # Combine the exons and shortened introns into one DataFrame
    rescaled_tx = pd.concat([exons, introns_shortened], ignore_index=True)
    # Sort the DataFrame by group_var (e.g., transcript) and start position
    rescaled_tx = rescaled_tx.sort_values(by=[group_var, 'start', 'end'] if group_var else ['start', 'end'])

    # Calculate cumulative sum to get rescaled start and end positions
    rescaled_tx['rescaled_end'] = rescaled_tx.groupby(group_var)['width'].cumsum() if group_var else rescaled_tx['width'].cumsum()
    rescaled_tx['rescaled_start'] = rescaled_tx['rescaled_end'] - rescaled_tx['width'] + 1

    if group_var is None:  # If no grouping, all transcripts start at position 1
        rescaled_tx['width_tx_start'] = 1
    else:
        # Merge rescaled transcript start gaps to adjust start positions
        rescaled_tx = rescaled_tx.merge(tx_start_gaps_shortened, on=group_var, suffixes=('', '_tx_start'))

    # Adjust the rescaled start and end positions based on transcript start gaps
    rescaled_tx['rescaled_end'] += rescaled_tx['width_tx_start']
    rescaled_tx['rescaled_start'] += rescaled_tx['width_tx_start']

    # Adjust start and end positions for introns to avoid exon overlap
    rescaled_tx['start'] = np.where(rescaled_tx['type'] == 'intron', rescaled_tx['start'] - 1, rescaled_tx['start'])
    rescaled_tx['end'] = np.where(rescaled_tx['type'] == 'intron', rescaled_tx['end'] + 1, rescaled_tx['end'])
    rescaled_tx['rescaled_start'] = np.where(rescaled_tx['type'] == 'intron', rescaled_tx['rescaled_start'] - 1, rescaled_tx['rescaled_start'])
    rescaled_tx['rescaled_end'] = np.where(rescaled_tx['type'] == 'intron', rescaled_tx['rescaled_end'] + 1, rescaled_tx['rescaled_end'])

    # Drop original start, end, and width columns, and rename rescaled columns to 'start' and 'end'
    rescaled_tx = rescaled_tx.drop(columns=['start', 'end', 'width']).rename(columns={'rescaled_start': 'start', 'rescaled_end': 'end'})

    # Reorder columns to ensure consistency in output
    column_order = ['seqnames', 'start', 'end', 'strand'] + [col for col in rescaled_tx.columns if col not in ['seqnames', 'start', 'end', 'strand']]
    rescaled_tx = rescaled_tx[column_order]

    return rescaled_tx  # Return the DataFrame with rescaled transcript coordinates
