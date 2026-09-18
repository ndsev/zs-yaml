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


def test_bin_to_yaml_with_type_arg():
    """Test bin_to_yaml with the type passed directly, no pre-existing target.

    Regression for ndsev/zs-yaml#30: schema_module/schema_type (CLI --type) allow
    binary -> YAML without a pre-created target file containing _meta.
    """
    print("\nTesting bin_to_yaml with --type (no pre-existing target)...")

    result = subprocess.run(['zs-yaml', 'team1.yaml', 'test_bin_to_yaml_type.bin'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to create binary file: {result.stderr}")

    out_path = 'test_bin_to_yaml_type_out.yaml'
    cli_out = 'test_bin_to_yaml_type_cli.yaml'
    for p in (out_path, cli_out):
        if os.path.exists(p):
            os.unlink(p)

    try:
        # API: pass the type directly; the target file does not exist yet.
        bin_to_yaml('test_bin_to_yaml_type.bin', out_path,
                    schema_module='team.api', schema_type='Team')
        with open(out_path, 'r') as f:
            output_data = yaml.safe_load(f)
        assert output_data['_meta']['schema_module'] == 'team.api'
        assert output_data['_meta']['schema_type'] == 'Team'
        assert output_data['name'] == "Dream Team", "Team name doesn't match"
        assert 'members' in output_data, "members field missing"

        # CLI: end-to-end --type path.
        r = subprocess.run(
            ['zs-yaml', 'test_bin_to_yaml_type.bin', cli_out, '--type', 'team.api.Team'],
            capture_output=True, text=True)
        assert r.returncode == 0, f"CLI --type failed: {r.stderr}"
        with open(cli_out, 'r') as f:
            cli_data = yaml.safe_load(f)
        assert cli_data['name'] == "Dream Team"

        print("   ✓ bin -> yaml via --type successful")
        return True
    finally:
        for p in ('test_bin_to_yaml_type.bin', out_path, cli_out):
            if os.path.exists(p):
                os.unlink(p)


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


def test_transform_cache_is_scoped_to_one_transform():
    """The transform cache must not outlive the transform that filled it.

    ``YamlTransformer`` used to keep every transformed document in a
    class-level dict for the life of the process, so a consumer converting
    many documents in one run retained every expanded tree and had to call
    ``clear_cache()`` to get the memory back. The cache now lives only for
    the duration of one transform, and ``cache_session()`` is the explicit
    way to widen that window.

    Three things are pinned here:
      1. repeated includes of the same file inside one document still share
         a single transformer (the dedup the cache exists for),
      2. after a top-level transform returns, the transformers it built are
         collectable — nothing is retained,
      3. inside ``cache_session()`` separate transforms do share, and the
         cache is released when the block exits.
    """
    import gc
    import shutil
    import weakref
    from zs_yaml.yaml_transformer import YamlTransformer

    print("\nTesting transform cache scoping...")

    work_dir = tempfile.mkdtemp(prefix='zs_yaml_cache_scope_')
    shared_path = os.path.join(work_dir, 'shared.yaml')
    doc_path = os.path.join(work_dir, 'doc.yaml')

    with open(shared_path, 'w') as f:
        f.write("""street: "Main St"
city: "Test City"
country: "Test Country"
zipCode: 12345
""")

    with open(doc_path, 'w') as f:
        f.write("""_meta:
  schema_module: team.api
  schema_type: Team

first:
  _f: insert_yaml
  _a:
    file: shared.yaml
second:
  _f: insert_yaml
  _a:
    file: shared.yaml
""")

    class CountingTransformer(YamlTransformer):
        """Records every construction so cache hits become observable."""
        built = []

        def __init__(self, yaml_file_path, template_args=None, initial_transformations=None):
            CountingTransformer.built.append(os.path.abspath(yaml_file_path))
            super().__init__(yaml_file_path, template_args, initial_transformations)

    try:
        # 1. within-document dedup: shared.yaml is built once, not twice.
        CountingTransformer.built = []
        doc = CountingTransformer.get_or_create(doc_path)
        shared_builds = [p for p in CountingTransformer.built if p == shared_path]
        assert len(shared_builds) == 1, (
            f"shared.yaml was transformed {len(shared_builds)} times inside one "
            f"document; repeated includes must share one transformer"
        )
        assert doc.data['first'] == doc.data['second']
        print("   ✓ repeated includes inside one document share one transformer")

        # 2. nothing survives the transform: the whole graph is collectable.
        doc_ref = weakref.ref(doc)
        shared_ref = None
        del doc
        gc.collect()
        assert doc_ref() is None, (
            "transformer for the document is still reachable after the "
            "transform returned — the cache is leaking"
        )

        # Same check for an included file, reached while a session is open.
        with YamlTransformer.cache_session():
            included = YamlTransformer.get_or_create(shared_path)
            shared_ref = weakref.ref(included)
            del included
        gc.collect()
        assert shared_ref() is None, (
            "transformer for an included file outlived the cache session"
        )
        print("   ✓ transformers are collectable once the transform returns")

        # 3. an explicit session shares across separate top-level transforms.
        CountingTransformer.built = []
        with YamlTransformer.cache_session():
            first = CountingTransformer.get_or_create(doc_path)
            second = CountingTransformer.get_or_create(doc_path)
            assert first is second, (
                "cache_session() must serve the same transformer to repeated "
                "get_or_create() calls"
            )
            del first, second
        doc_builds = [p for p in CountingTransformer.built if p == doc_path]
        assert len(doc_builds) == 1, (
            f"doc.yaml was transformed {len(doc_builds)} times inside one "
            f"cache_session(); the session must serve the cached transformer"
        )

        # Outside any session the same two calls build twice — that is the
        # documented default, and what keeps batch consumers from leaking.
        CountingTransformer.built = []
        a = CountingTransformer.get_or_create(doc_path)
        b = CountingTransformer.get_or_create(doc_path)
        assert a is not b, (
            "outside cache_session() each call must build a fresh transformer"
        )
        del a, b
        print("   ✓ cache_session() shares across transforms, default does not")

        return True
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_descriptor_cache_keyed_on_object_not_id():
    """Regression: _COMPOUND_CACHE must not alias distinct types by id().

    Once upon a time the cache keyed on ``id(type_info)``. Each call to a
    generated ``type_info()`` returns a fresh ``TypeInfo`` instance, so after
    GC reclaims one, a later call can land at the same memory address and the
    cache returns a stale descriptor — surfacing as ``'X' object has no
    attribute 'y'`` errors during ``bin_to_dict`` / ``bin_to_yaml`` in
    long-running processes that load multiple schemas.

    The cache now keys on the generated class, which is held strongly and
    cannot have its identity recycled. See ``test_descriptor_cache.py`` for
    the cache-hit side of that key choice.

    We simulate the collision by seeding the cache with an int key matching
    ``id(type_info)`` whose value is an unrelated descriptor, then verify the
    lookup still returns the correct descriptor for that ``type_info``.
    """
    from team.api import Team, Person
    from zs_yaml import convert

    print("Testing _COMPOUND_CACHE id-reuse regression...")

    ti_team = Team.type_info()
    ti_person = Person.type_info()

    convert._COMPOUND_CACHE.clear()
    desc_team = convert._compound_descriptor(ti_team)
    desc_person = convert._compound_descriptor(ti_person)
    assert desc_team is not desc_person, "Distinct TypeInfos must produce distinct descriptors"

    # Simulate the previous bug: an int key matching id(ti_person) carrying
    # an unrelated descriptor (as if a freed TypeInfo had occupied that
    # address before GC reclaimed it). A correctly-keyed cache ignores the
    # stale int-keyed entry; a buggy id-keyed cache would return desc_team
    # for ti_person.
    convert._COMPOUND_CACHE[id(ti_person)] = desc_team
    desc_person_again = convert._compound_descriptor(ti_person)

    if desc_person_again is not desc_person:
        team_fields = [f.schema_name for f in desc_team.fields]
        person_fields_expected = [f.schema_name for f in desc_person.fields]
        person_fields_actual = [f.schema_name for f in desc_person_again.fields]
        raise AssertionError(
            "_COMPOUND_CACHE returned a stale descriptor — id() reuse regression. "
            f"Expected fields={person_fields_expected}, got={person_fields_actual} "
            f"(matches Team fields={team_fields})."
        )

    print("   ✓ cache returns correct descriptor under simulated id() collision")
    return True


def _null_paths(node, path=""):
    """Every path in a tree whose value is None."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if value is None:
                found.append(f"{path}.{key}")
            else:
                found.extend(_null_paths(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.extend(_null_paths(value, f"{path}[{i}]"))
    return found


def test_bin_to_dict_skip_nulls():
    """skip_nulls leaves unset optional fields out instead of emitting None."""
    import zserio
    from team.api import Contact, Profile
    from zs_yaml.convert import bin_to_dict

    print("Testing bin_to_dict(skip_nulls=...)...")

    # Profile is the schema's optional-carrying type (Team has no optional
    # fields, so it cannot exercise this at all). nickname and home are left
    # unset at the top level, and the second contact leaves handle unset so
    # the array/compound recursion is covered too.
    profile = Profile()
    profile.owner = "Alice"
    profile.nickname = None
    profile.home = None
    filled, empty = Contact(), Contact()
    filled.kind = "email"
    filled.handle = "alice@example.com"
    empty.kind = "phone"
    empty.handle = None
    profile.contacts = [filled, empty]

    with tempfile.TemporaryDirectory() as tmp:
        bin_path = os.path.join(tmp, "profile.bin")
        zserio.serialize_to_file(profile, bin_path)

        with_nulls, _ = bin_to_dict(bin_path, "team.api", "Profile")
        without_nulls, _ = bin_to_dict(bin_path, "team.api", "Profile", skip_nulls=True)

    # The default must still emit them — that is 0.11.0 behavior.
    default_nulls = sorted(_null_paths(with_nulls))
    assert default_nulls == ['.contacts[1].handle', '.home', '.nickname'], (
        f"default bin_to_dict emitted unexpected null paths: {default_nulls}"
    )

    remaining = _null_paths(without_nulls)
    assert not remaining, f"skip_nulls left None entries at: {remaining}"

    assert set(without_nulls) == {"owner", "contacts"}, (
        f"skip_nulls produced unexpected top-level keys: {sorted(without_nulls)}"
    )
    assert without_nulls["owner"] == "Alice"
    assert without_nulls["contacts"][0] == {"kind": "email", "handle": "alice@example.com"}, (
        "skip_nulls must not touch fields that are set"
    )
    assert without_nulls["contacts"][1] == {"kind": "phone"}, (
        "skip_nulls must drop the unset field inside an array element"
    )

    print(f"   ✓ default keeps {len(default_nulls)} None entries, skip_nulls drops them")
    return True


def test_has_function_invocations():
    """The flag mirrors whether the document contained any `_f:` call."""
    from zs_yaml.yaml_transformer import YamlTransformer

    print("Testing YamlTransformer.has_function_invocations...")

    plain = """_meta:
  schema_module: team.api
  schema_type: Team

name: "No Functions Here"
members: []
"""
    with_calls = """_meta:
  schema_module: team.api
  schema_type: Team
  transformation_module: "./custom_transformations.py"

name: "Has Functions"
members:
  - name: "Alice"
    age:
      _f: calculate_age
      _a: "1990-05-15"
    address:
      street: "Main St"
      city: "Test City"
      country: "Test Country"
      zipCode: 12345
    workExperience: []
    skills: []
    hobbies: []
    bio: "bio"
"""
    here = os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        plain_path = os.path.join(here, "_tmp_plain.yaml")
        calls_path = os.path.join(here, "_tmp_calls.yaml")
        try:
            with open(plain_path, "w") as f:
                f.write(plain)
            with open(calls_path, "w") as f:
                f.write(with_calls)

            t_plain = YamlTransformer(plain_path)
            assert t_plain.has_function_invocations is False, (
                "document without `_f:` reported function invocations"
            )
            assert t_plain.data is t_plain.original_data, (
                "untransformed document should expose the loaded tree as-is"
            )

            t_calls = YamlTransformer(calls_path)
            assert t_calls.has_function_invocations is True, (
                "document with `_f:` reported no function invocations"
            )
        finally:
            for path in (plain_path, calls_path):
                if os.path.exists(path):
                    os.remove(path)

    print("   ✓ flag matches the presence of `_f:` in the source")
    return True


def test_insert_yaml_returns_independent_copies():
    """insert_yaml/repeat_node hand out copies, not aliases of the cached tree."""
    from zs_yaml.built_in_transformations import _copy_yaml_tree, _deep_copy_data

    print("Testing YAML-tree copy semantics...")

    source = {
        "a": [1, 2, {"b": "c"}],
        "d": {"e": [{"f": 1}]},
        "g": None,
        "h": True,
    }
    copied = _deep_copy_data(source)
    assert copied == source, "copy changed the values"
    assert copied is not source, "copy returned the same object"
    assert copied["a"] is not source["a"], "nested list was aliased"
    assert copied["a"][2] is not source["a"][2], "nested dict was aliased"
    assert copied["d"]["e"][0] is not source["d"]["e"][0], "deeply nested dict was aliased"

    copied["a"][2]["b"] = "mutated"
    assert source["a"][2]["b"] == "c", "mutating the copy reached the source"

    # A self-referential tree must not blow the stack; deepcopy handles it.
    cyclic = {"self": None}
    cyclic["self"] = cyclic
    fallback = _deep_copy_data(cyclic)
    assert fallback is not cyclic, "cyclic copy returned the same object"
    assert fallback["self"] is fallback, "cyclic copy lost its self-reference"

    # Plain-tree copy is the fast route and covers what YAML loading produces.
    assert _copy_yaml_tree(source) == source

    # A node that is not a plain dict/list/scalar must still be copied, not
    # aliased — otherwise repeat_node would hand out N views of one object.
    from collections import OrderedDict

    exotic = {"od": OrderedDict(a=[1]), "tup": ([1], 2), "obj": {1, 2}}
    exotic_copy = _deep_copy_data(exotic)
    assert exotic_copy == exotic, "copy changed an exotic node's value"
    for key in exotic:
        assert exotic_copy[key] is not exotic[key], f"{key} was aliased, not copied"
    assert exotic_copy["od"]["a"] is not exotic["od"]["a"], "dict subclass copied shallowly"

    repeated = [_deep_copy_data(exotic) for _ in range(3)]
    repeated[0]["od"]["a"].append(99)
    assert repeated[1]["od"]["a"] == [1], "repeated copies share a mutable node"

    print("   ✓ copies are independent; cyclic trees fall back to deepcopy")
    return True


if __name__ == "__main__":
    try:
        # Run all tests
        test_yaml_to_yaml()
        json_path = test_yaml_to_json()
        test_json_to_yaml(json_path)
        test_bin_to_yaml()
        test_bin_to_yaml_with_type_arg()
        test_yaml_to_yaml_with_template_args()
        test_transform_cache_is_scoped_to_one_transform()
        test_descriptor_cache_keyed_on_object_not_id()
        test_bin_to_dict_skip_nulls()
        test_has_function_invocations()
        test_insert_yaml_returns_independent_copies()

        print("\n✅ All conversion tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)