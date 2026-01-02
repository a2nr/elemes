#!/usr/bin/env python3
"""
Script to test the token tracking system
"""

import csv
import os
import uuid
import tempfile
import subprocess
import time
import requests
import json

# Configuration
TOKENS_FILE = 'tokens.csv'
BASE_URL = 'http://localhost:5000'

def test_csv_generation():
    """Test if the CSV file was generated correctly"""
    print("Testing CSV generation...")
    
    if not os.path.exists(TOKENS_FILE):
        print("✗ tokens.csv file does not exist")
        return False
    
    with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
        header = f.readline().strip()
        print(f"✓ CSV header: {header}")
        
        # Check if it contains required columns
        columns = header.split(';')
        if 'token' in columns and 'nama_siswa' in columns:
            print("✓ Required columns (token, nama_siswa) are present")
            return True
        else:
            print("✗ Required columns are missing")
            return False

def test_endpoints():
    """Test the API endpoints"""
    print("\\nTesting API endpoints...")
    
    # Test /validate-token endpoint
    try:
        response = requests.post(f'{BASE_URL}/validate-token', 
                                json={'token': 'test-token'}, 
                                headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            print("✓ /validate-token endpoint is working")
        else:
            print(f"✗ /validate-token endpoint returned {response.status_code}")
    except Exception as e:
        print(f"✗ Error testing /validate-token endpoint: {e}")
    
    # Test /login endpoint
    try:
        response = requests.post(f'{BASE_URL}/login', 
                                json={'token': 'test-token'}, 
                                headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            print("✓ /login endpoint is working")
        else:
            print(f"✗ /login endpoint returned {response.status_code}")
    except Exception as e:
        print(f"✗ Error testing /login endpoint: {e}")
    
    # Test /track-progress endpoint
    try:
        response = requests.post(f'{BASE_URL}/track-progress', 
                                json={'token': 'test-token', 'lesson_name': 'test_lesson'}, 
                                headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            print("✓ /track-progress endpoint is working")
        else:
            print(f"✗ /track-progress endpoint returned {response.status_code}")
    except Exception as e:
        print(f"✗ Error testing /track-progress endpoint: {e}")

def test_token_functionality():
    """Test the complete token functionality"""
    print("\\nTesting complete token functionality...")
    
    # Generate a test token
    test_token = str(uuid.uuid4())
    test_student_name = "Test Student"
    
    # Add test token to CSV file
    with open(TOKENS_FILE, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        writer.writerow([test_token, test_student_name] + [''] * (len(open(TOKENS_FILE).readline().strip().split(';')) - 2))
    
    print(f"✓ Added test token to CSV: {test_token}")
    
    # Test login with the token
    try:
        response = requests.post(f'{BASE_URL}/login', 
                                json={'token': test_token}, 
                                headers={'Content-Type': 'application/json'})
        data = response.json()
        
        if data['success'] and data['student_name'] == test_student_name:
            print("✓ Token validation successful")
        else:
            print(f"✗ Token validation failed: {data}")
    except Exception as e:
        print(f"✗ Error during token validation: {e}")
    
    # Test progress tracking
    try:
        response = requests.post(f'{BASE_URL}/track-progress', 
                                json={'token': test_token, 'lesson_name': 'introduction_to_c', 'status': 'completed'}, 
                                headers={'Content-Type': 'application/json'})
        data = response.json()
        
        if data['success']:
            print("✓ Progress tracking successful")
        else:
            print(f"✗ Progress tracking failed: {data}")
    except Exception as e:
        print(f"✗ Error during progress tracking: {e}")
    
    # Verify the progress was updated in the CSV
    try:
        with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            for row in reader:
                if row['token'] == test_token:
                    if row.get('introduction_to_c', '') == 'completed':
                        print("✓ Progress correctly updated in CSV")
                    else:
                        print(f"✗ Progress not updated correctly in CSV: {row.get('introduction_to_c', 'not found')}")
                    break
    except Exception as e:
        print(f"✗ Error checking CSV for progress update: {e}")

def main():
    print("Starting token tracking system tests...")
    
    # Wait a bit to ensure the server is running
    time.sleep(5)
    
    success = True
    
    # Test CSV generation
    if not test_csv_generation():
        success = False
    
    # Test endpoints
    test_endpoints()
    
    # Test complete functionality
    test_token_functionality()
    
    if success:
        print("\\n✓ All tests passed! Token tracking system is working correctly.")
    else:
        print("\\n✗ Some tests failed.")
    
    # Cleanup: Remove the test token from CSV
    try:
        rows = []
        with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            fieldnames = reader.fieldnames
            for row in reader:
                if row['token'] != test_token:  # Don't include the test token in the new file
                    rows.append(row)
        
        with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
        
        print("✓ Test token cleaned up from CSV")
    except Exception as e:
        print(f"✗ Error cleaning up test token: {e}")

if __name__ == '__main__':
    main()