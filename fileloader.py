import numpy as np
import sys
import os
import pickle
import re
import pandas as pd
import msgpack as mp
import msgpack_numpy as mpn
from more_itertools import locate

def read_pickle(folder, file, remove_duplicates=True, board_pose_bool=False):
    """
    Read pickle file and optionally remove duplicates based on board_aruco_ids
    
    Args:
        folder: folder path
        file: file name
        remove_duplicates: if True, removes duplicate aruco IDs and empty lists (only used when board_pose_bool=False)
        board_pose_bool: if True, ensures board pose format: [[dict1], [dict2], ...]
                        - Checks if format is already correct
                        - If not, removes empty lists, duplicates, and flattens structure
                        if False, returns based on remove_duplicates parameter
    
    Returns:
        loaded objects from pickle file
    """
    objects = []
    path = os.path.join(folder, file)
    with open(path, "rb") as openfile:
        while True:
            try:
                objects.append(pickle.load(openfile))
            except EOFError:
                break
    
    # If board_pose_bool is True, enforce correct board pose format
    if board_pose_bool:
        cleaned_objects = []
        
        for obj in objects:
            if isinstance(obj, list):
                # Check if format is already correct: [[{dict}], [{dict}], ...]
                is_correct_format = True
                
                for subobj in obj:
                    if isinstance(subobj, list):
                        if len(subobj) == 0:  # Empty list
                            is_correct_format = False
                            break
                        elif len(subobj) == 1 and isinstance(subobj[0], dict) and 'board_aruco_ids' in subobj[0]:
                            # Correct: single dict in a list
                            continue
                        elif len(subobj) > 1:  # Multiple dicts in one list
                            is_correct_format = False
                            break
                        else:
                            is_correct_format = False
                            break
                    else:
                        is_correct_format = False
                        break
                
                # If format is already correct, return as-is
                if is_correct_format:
                    cleaned_objects.append(obj)
                else:
                    # Format is incorrect, fix it: remove empty lists, duplicates, and flatten
                    cleaned_sublist = []
                    seen_ids = set()
                    
                    for subobj in obj:
                        if isinstance(subobj, list):
                            if not subobj:  # Skip empty lists
                                continue
                            
                            # Process each item in the sublist
                            for item in subobj:
                                if isinstance(item, dict) and 'board_aruco_ids' in item:
                                    aruco_id = item['board_aruco_ids'][0] if len(item['board_aruco_ids']) > 0 else None
                                    
                                    # Remove duplicates and flatten: each dict in its own list
                                    if aruco_id is not None and aruco_id not in seen_ids:
                                        seen_ids.add(aruco_id)
                                        cleaned_sublist.append([item])
                        
                        elif isinstance(subobj, dict) and 'board_aruco_ids' in subobj:
                            # Direct dict - wrap in list
                            aruco_id = subobj['board_aruco_ids'][0] if len(subobj['board_aruco_ids']) > 0 else None
                            if aruco_id is not None and aruco_id not in seen_ids:
                                seen_ids.add(aruco_id)
                                cleaned_sublist.append([subobj])
                    
                    if cleaned_sublist:
                        cleaned_objects.append(cleaned_sublist)
            else:
                cleaned_objects.append(obj)
        
        return cleaned_objects if cleaned_objects else objects
    
    # If board_pose_bool is False, use remove_duplicates parameter
    if not remove_duplicates:
        return objects
    
    # Auto-detect structure and remove duplicates (when board_pose_bool=False and remove_duplicates=True)
    cleaned_objects = []
    
    for obj in objects:
        if isinstance(obj, list):
            cleaned_sublist = []
            
            for subobj in obj:
                if isinstance(subobj, list) and subobj:
                    has_aruco_ids = any(isinstance(item, dict) and 'board_aruco_ids' in item for item in subobj)
                    
                    if has_aruco_ids:
                        seen_ids = set()
                        filtered_list = []
                        
                        for item in subobj:
                            if isinstance(item, dict) and 'board_aruco_ids' in item:
                                aruco_id = item['board_aruco_ids'][0] if len(item['board_aruco_ids']) > 0 else None
                                if aruco_id is not None and aruco_id not in seen_ids:
                                    seen_ids.add(aruco_id)
                                    filtered_list.append(item)
                        
                        if filtered_list:
                            cleaned_sublist.append(filtered_list)
                    else:
                        cleaned_sublist.append(subobj)
                        
                elif isinstance(subobj, dict) and 'board_aruco_ids' in subobj:
                    cleaned_sublist.append(subobj)
            
            if cleaned_sublist:
                cleaned_objects.append(cleaned_sublist)
        else:
            cleaned_objects.append(obj)
    
    return cleaned_objects if cleaned_objects else objects
