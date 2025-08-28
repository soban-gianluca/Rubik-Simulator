#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(__file__))

from src.personal_best_manager import PersonalBestManager

def main():
    print("Testing total solves calculation...")
    
    # Create the personal best manager
    pbm = PersonalBestManager()
    
    print("\nIndividual difficulty solves:")
    total_manual = 0
    for difficulty in ["easy", "medium", "hard", "limited_time", "limited_moves"]:
        solves = pbm.get_total_solves(difficulty)
        print(f"{difficulty}: {solves}")
        total_manual += solves
    
    print(f"\nManual calculation total: {total_manual}")
    
    # Get total using the method
    total_method = pbm.get_total_solves()
    print(f"Method calculation total: {total_method}")
    
    print(f"\nDo they match? {total_manual == total_method}")
    
    # Let's also check the raw records
    print("\nRaw records:")
    for difficulty, record in pbm.records.items():
        print(f"{difficulty}: {record.get('total_solves', 0)}")

if __name__ == "__main__":
    main()
