#!/usr/bin/env python3
"""
Comprehensive test script for all zs-yaml conversion functions.
Tests yaml_to_yaml, yaml_to_json, json_to_yaml, and bin_to_yaml.
"""

import sys
import os
import tempfile
import yaml
import json
import subprocess

# Add parent directory to path to import zs_yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from zs_yaml.convert import yaml_to_yaml, yaml_to_json, json_to_yaml, bin_to_yaml

def test_yaml_to_yaml():
    """Test yaml_to_yaml transformation and templating functionality"""
    print("Testing yaml_to_yaml transformation...")
    
    # Create a test YAML with transformations
    test_yaml_content = """_meta:
  schema_module: team.api
  schema_type: Team

name: "Transformation Test Team"
members:
  - name: "Alice"
    age: 25
    address:
      street: "Main St"
      city: "Test City"
      country: "Test Country"
      zipCode: 12345
    workExperience: []
    skills:
      _f: repeat_node
      _a:
        count: 3
        node:
          name: "Python"
          level: 8
    hobbies:
      _f: py_eval
      _a:
        expr: '["Reading", "Gaming", "Coding"]'
    bio: "Test bio"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_input:
        temp_input.write(test_yaml_content)
        temp_input_path = temp_input.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_output:
        temp_output_path = temp_output.name
    
    try:
        # Run yaml_to_yaml transformation
        yaml_to_yaml(temp_input_path, temp_output_path)
        
        # Read and verify the output
        with open(temp_output_path, 'r') as f:
            output_data = yaml.safe_load(f)
        
        # Verify transformations were applied
        assert len(output_data['members'][0]['skills']) == 3, "repeat_node transformation failed"
        assert all(s['name'] == 'Python' for s in output_data['members'][0]['skills']), "repeat_node content incorrect"
        assert output_data['members'][0]['hobbies'] == ["Reading", "Gaming", "Coding"], "py_eval transformation failed"
        
        print("   ✓ Transformations applied successfully")
        
        # Clean up
        os.unlink(temp_input_path)
        os.unlink(temp_output_path)
        
        return True
        
    except Exception as e:
        os.unlink(temp_input_path)
        if os.path.exists(temp_output_path):
            os.unlink(temp_output_path)
        raise


def test_yaml_to_json():
    """Test yaml_to_json conversion"""
    print("\nTesting yaml_to_json conversion...")
    
    # Use team1.yaml as input
    input_yaml_path = "team1.yaml"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_output:
        output_json_path = temp_output.name
    
    try:
        # Convert YAML to JSON
        yaml_to_json(input_yaml_path, output_json_path)
        
        # Read and verify JSON
        with open(output_json_path, 'r') as f:
            json_data = json.load(f)
        
        # Verify key fields exist
        assert 'name' in json_data, "name field missing in JSON"
        assert 'members' in json_data, "members field missing in JSON"
        assert isinstance(json_data['members'], list), "members should be a list"
        assert len(json_data['members']) > 0, "members list should not be empty"
        
        # Verify no _meta in JSON output (as per design)
        assert '_meta' not in json_data, "JSON should not contain _meta section"
        
        print("   ✓ YAML to JSON conversion successful")
        
        # Save path for next test
        return output_json_path
        
    except Exception as e:
        if os.path.exists(output_json_path):
            os.unlink(output_json_path)
        raise


def test_json_to_yaml(json_path):
    """Test json_to_yaml conversion"""
    print("\nTesting json_to_yaml conversion...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_output:
        output_yaml_path = temp_output.name
    
    try:
        # Convert JSON to YAML
        json_to_yaml(json_path, output_yaml_path)
        
        # Read and verify YAML
        with open(output_yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        # Verify key fields exist
        assert 'name' in yaml_data, "name field missing in YAML"
        assert 'members' in yaml_data, "members field missing in YAML"
        assert isinstance(yaml_data['members'], list), "members should be a list"
        
        print("   ✓ JSON to YAML conversion successful")
        
        # Clean up
        os.unlink(output_yaml_path)
        os.unlink(json_path)  # Clean up JSON from previous test
        
        return True
        
    except Exception as e:
        if os.path.exists(output_yaml_path):
            os.unlink(output_yaml_path)
        if os.path.exists(json_path):
            os.unlink(json_path)
        raise


def test_bin_to_yaml():
    """Test bin_to_yaml conversion (roundtrip test)"""
    print("\nTesting bin_to_yaml conversion...")
    
    # First, create a binary file from team1.yaml
    print("   Creating binary file from team1.yaml...")
    result = subprocess.run(['zs-yaml', 'team1.yaml', 'test_bin_to_yaml.bin'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to create binary file: {result.stderr}")
    
    # Create template YAML with metadata for bin_to_yaml
    template_yaml_content = """_meta:
  schema_module: team.api
  schema_type: Team
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_template:
        temp_template.write(template_yaml_content)
        template_path = temp_template.name
    
    try:
        # Convert binary back to YAML
        bin_to_yaml('test_bin_to_yaml.bin', template_path)
        
        # Read and verify the output
        with open(template_path, 'r') as f:
            output_data = yaml.safe_load(f)
        
        # Read original for comparison
        with open('team1.yaml', 'r') as f:
            original_data = yaml.safe_load(f)
        
        # Verify _meta section exists
        assert '_meta' in output_data, "_meta section missing"
        assert output_data['_meta']['schema_module'] == 'team.api'
        assert output_data['_meta']['schema_type'] == 'Team'
        
        # Verify data integrity
        assert 'name' in output_data, "name field missing"
        assert 'members' in output_data, "members field missing"
        assert output_data['name'] == "Dream Team", "Team name doesn't match"
        
        print("   ✓ Binary to YAML conversion successful")
        
        # Clean up
        os.unlink('test_bin_to_yaml.bin')
        os.unlink(template_path)
        
        return True
        
    except Exception as e:
        if os.path.exists('test_bin_to_yaml.bin'):
            os.unlink('test_bin_to_yaml.bin')
        if os.path.exists(template_path):
            os.unlink(template_path)
        raise


def test_yaml_to_yaml_with_template_args():
    """Test yaml_to_yaml with template argument substitution"""
    print("\nTesting yaml_to_yaml with template arguments...")
    
    # Create a YAML with template placeholders
    test_yaml_content = """_meta:
  schema_module: team.api
  schema_type: Team

name: "${team_name}"
members:
  - name: "${member_name}"
    age: ${member_age}
    address:
      street: "${street}"
      city: "Test City"
      country: "Test Country"
      zipCode: 12345
    workExperience: []
    skills: []
    hobbies: []
    bio: "Bio for ${member_name}"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_input:
        temp_input.write(test_yaml_content)
        temp_input_path = temp_input.name
    
    # Import YamlTransformer to test with template args
    from zs_yaml.yaml_transformer import YamlTransformer
    
    try:
        # Create transformer with template arguments
        template_args = {
            'team_name': 'Template Test Team',
            'member_name': 'Bob',
            'member_age': '30',
            'street': '123 Template St'
        }
        
        transformer = YamlTransformer(temp_input_path, template_args)
        
        # Verify template substitution
        assert transformer.data['name'] == 'Template Test Team'
        assert transformer.data['members'][0]['name'] == 'Bob'
        assert transformer.data['members'][0]['age'] == 30
        assert transformer.data['members'][0]['address']['street'] == '123 Template St'
        assert transformer.data['members'][0]['bio'] == 'Bio for Bob'
        
        print("   ✓ Template argument substitution successful")
        
        # Clean up
        os.unlink(temp_input_path)
        
        return True
        
    except Exception as e:
        if os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        raise


if __name__ == "__main__":
    try:
        # Run all tests
        test_yaml_to_yaml()
        json_path = test_yaml_to_json()
        test_json_to_yaml(json_path)
        test_bin_to_yaml()
        test_yaml_to_yaml_with_template_args()
        
        print("\n✅ All conversion tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)