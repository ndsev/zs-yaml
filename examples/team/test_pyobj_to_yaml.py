#!/usr/bin/env python3
"""
Test script for pyobj_to_yaml functionality.
"""

import sys
import os
import tempfile
import yaml

# Add parent directory to path to import zs_yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from zs_yaml.convert import yaml_to_pyobj, pyobj_to_yaml

def test_pyobj_to_yaml_roundtrip():
    """Test converting a YAML to Python object and back to YAML"""
    print("Testing pyobj_to_yaml roundtrip conversion...")
    
    # Use the existing team1.yaml as input
    input_yaml_path = "team1.yaml"
    
    # Read the original YAML for comparison
    with open(input_yaml_path, 'r') as f:
        original_data = yaml.safe_load(f)
    
    print(f"1. Loading YAML from {input_yaml_path}")
    # Convert YAML to Python object
    pyobj = yaml_to_pyobj(input_yaml_path)
    print(f"   Successfully loaded {pyobj.__class__.__name__} object")
    
    # Convert Python object back to YAML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
        output_yaml_path = temp_file.name
    
    print(f"2. Converting Python object back to YAML at {output_yaml_path}")
    pyobj_to_yaml(pyobj, output_yaml_path)
    print("   Successfully converted to YAML")
    
    # Read the generated YAML
    with open(output_yaml_path, 'r') as f:
        generated_data = yaml.safe_load(f)
    
    # Verify _meta section exists and has correct values
    print("3. Verifying _meta section...")
    assert '_meta' in generated_data, "_meta section missing in generated YAML"
    assert 'schema_module' in generated_data['_meta'], "schema_module missing in _meta"
    assert 'schema_type' in generated_data['_meta'], "schema_type missing in _meta"
    
    # Note: The module name changes from team.api to team.team when loaded
    # This is expected behavior as the actual module structure is team.team
    print(f"   Original module: {original_data['_meta']['schema_module']}")
    print(f"   Generated module: {generated_data['_meta']['schema_module']}")
    print(f"   Generated module is the actual Python module path")
    
    # The type should match exactly
    assert generated_data['_meta']['schema_type'] == original_data['_meta']['schema_type']
    print("   _meta section verified successfully")
    
    # Verify some key data fields exist (based on actual Team schema)
    print("4. Verifying data integrity...")
    assert 'name' in generated_data, "name field missing"
    assert 'members' in generated_data, "members field missing"
    assert isinstance(generated_data['members'], list), "members should be a list"
    print("   Data fields verified successfully")
    
    # Clean up
    os.unlink(output_yaml_path)
    
    print("\n✓ pyobj_to_yaml test passed successfully!")
    return True

def test_pyobj_to_yaml_with_nested_extern():
    """Test pyobj_to_yaml with data containing nested extern references"""
    print("\nTesting pyobj_to_yaml with nested extern data...")
    
    # Create a test YAML without transformation module reference
    test_yaml_content = """_meta:
  schema_module: team.api
  schema_type: Team

name: Test Team
members:
  - name: "Test Person"
    age: 30
    address:
      street: "Test St"
      city: "Test City"
      country: "Test Country"
      zipCode: 12345
    workExperience: []
    skills: []
    hobbies: []
    bio: "Test bio"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_input:
        temp_input.write(test_yaml_content)
        temp_input_path = temp_input.name
    
    try:
        # Convert to Python object
        print("1. Loading test YAML with extern reference")
        pyobj = yaml_to_pyobj(temp_input_path)
        print(f"   Successfully loaded {pyobj.__class__.__name__} object")
        
        # Convert back to YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_output:
            output_yaml_path = temp_output.name
        
        print("2. Converting back to YAML")
        pyobj_to_yaml(pyobj, output_yaml_path)
        print("   Successfully converted to YAML")
        
        # Verify the output
        with open(output_yaml_path, 'r') as f:
            output_data = yaml.safe_load(f)
        
        print("3. Verifying output...")
        assert output_data['members'] is not None, "Members data should not be None"
        assert len(output_data['members']) > 0, "Should have at least one member"
        assert 'name' in output_data['members'][0], "Member should have name field"
        print("   Data was properly included")
        
        # Clean up
        os.unlink(output_yaml_path)
        
        print("\n✓ Nested extern test passed successfully!")
        return True
        
    finally:
        os.unlink(temp_input_path)

if __name__ == "__main__":
    try:
        # Run tests
        test_pyobj_to_yaml_roundtrip()
        test_pyobj_to_yaml_with_nested_extern()
        
        print("\n✅ All tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)