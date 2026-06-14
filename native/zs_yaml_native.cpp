/*
 * zs_yaml_native: C-level YAML loader for zs-yaml.
 *
 * Parses with the vendored rapidyaml (single-header amalgamation) and builds
 * the Python dict/list/scalar tree entirely in C. Replaces the per-node
 * python<->binding round trips of the `ryml` python-binding loader (~0.6us
 * per node, dominating load time on multi-hundred-MB documents).
 *
 * Output contract: identical to zs_yaml._ryml_loader._walk (which in turn is
 * identical to yaml.load(..., yaml.CLoader) for the YAML subset used by
 * zs-yaml). Scalar coercion fast-paths cover plain decimal integers and
 * dot-floats with signed exponents - shapes whose PyYAML 1.1 resolution is
 * unambiguous - and everything else funnels through a memoized callback into
 * the python-side _coerce_plain_scalar, so resolution semantics stay anchored
 * to PyYAML itself.
 *
 * Built against the CPython Limited API (abi3, floor 3.11): one wheel per
 * platform serves all current and future Python versions.
 *
 * rapidyaml is vendored as the unmodified source tree of the rapidyaml 0.15.0
 * PyPI sdist (the same artifact the optional `rapidyaml` binding dependency is
 * built from) under vendor/rapidyaml/, MIT licensed.
 */

#ifndef Py_LIMITED_API
    #define Py_LIMITED_API 0x030B0000
#endif

#include <Python.h>

#include <cstring>
#include <exception>
#include <stdexcept>
#include <string>

#include <ryml.hpp>
#include <ryml_std.hpp>

namespace
{

constexpr Py_ssize_t SCALAR_MEMO_LIMIT = 1 << 20;

// ---------------------------------------------------------------- ryml error bridge

[[noreturn]] void onErrorBasic(c4::csubstr msg, ryml::ErrorDataBasic const&, void*)
{
    throw std::runtime_error(std::string(msg.str, msg.len));
}

[[noreturn]] void onErrorParse(c4::csubstr msg, ryml::ErrorDataParse const&, void*)
{
    throw std::runtime_error(std::string(msg.str, msg.len));
}

[[noreturn]] void onErrorVisit(c4::csubstr msg, ryml::ErrorDataVisit const&, void*)
{
    throw std::runtime_error(std::string(msg.str, msg.len));
}

// ---------------------------------------------------------------- scalar coercion

struct WalkContext
{
    const ryml::Tree* tree;
    PyObject* coerce; // python callable: str -> coerced scalar
    PyObject* memo;   // per-call dict: str -> coerced scalar
};

inline PyObject* makeString(c4::csubstr s)
{
    return PyUnicode_FromStringAndSize(s.len ? s.str : "", static_cast<Py_ssize_t>(s.len));
}

/*
 * Plain decimal integer per the PyYAML 1.1 int resolver: [-+]?(0|[1-9][0-9]*)
 * restricted to shapes a C int64 can hold and without '_' separators ('+' and
 * separators are rare and fall back to the callback). Multi-digit tokens with
 * a leading zero are octal in YAML 1.1 and must NOT take this path.
 */
inline bool tryFastInt(c4::csubstr s, PyObject** out)
{
    const char* p = s.str;
    size_t len = s.len;
    bool negative = false;
    if (len > 0 && p[0] == '-')
    {
        negative = true;
        ++p;
        --len;
    }
    if (len == 0 || len > 18)
        return false;
    if (len > 1 && p[0] == '0')
        return false;
    int64_t value = 0;
    for (size_t i = 0; i < len; ++i)
    {
        const char c = p[i];
        if (c < '0' || c > '9')
            return false;
        value = value * 10 + (c - '0');
    }
    *out = PyLong_FromLongLong(negative ? -value : value);
    return true;
}

/*
 * Plain float per the PyYAML 1.1 float resolver, fast shape only:
 * -?[0-9]+\.[0-9]*([eE][-+][0-9]+)?  - note the resolver REQUIRES the dot and
 * a signed exponent (an unsigned exponent resolves to str in PyYAML 1.1!),
 * so only this exact shape may take the C path. No '_' separators.
 */
inline bool tryFastFloat(c4::csubstr s, PyObject** out)
{
    const char* p = s.str;
    const size_t len = s.len;
    if (len < 2 || len > 60)
        return false;
    size_t i = 0;
    if (p[i] == '-')
        ++i;
    size_t intDigits = 0;
    while (i < len && p[i] >= '0' && p[i] <= '9')
    {
        ++i;
        ++intDigits;
    }
    if (intDigits == 0 || i >= len || p[i] != '.')
        return false;
    ++i; // consume '.'
    while (i < len && p[i] >= '0' && p[i] <= '9')
        ++i;
    if (i < len)
    {
        if (p[i] != 'e' && p[i] != 'E')
            return false;
        ++i;
        if (i >= len || (p[i] != '+' && p[i] != '-'))
            return false; // unsigned exponent is NOT a float in YAML 1.1
        ++i;
        size_t expDigits = 0;
        while (i < len && p[i] >= '0' && p[i] <= '9')
        {
            ++i;
            ++expDigits;
        }
        if (expDigits == 0)
            return false;
    }
    if (i != len)
        return false;
    char buffer[64];
    std::memcpy(buffer, s.str, len);
    buffer[len] = '\0';
    const double value = PyOS_string_to_double(buffer, nullptr, nullptr);
    if (value == -1.0 && PyErr_Occurred())
        return false; // defensive; the scanned shape always converts
    *out = PyFloat_FromDouble(value);
    return true;
}

PyObject* coercePlainScalar(WalkContext& ctx, c4::csubstr s)
{
    PyObject* fast = nullptr;
    if (tryFastInt(s, &fast))
        return fast;
    if (tryFastFloat(s, &fast))
        return fast;

    PyObject* key = makeString(s);
    if (key == nullptr)
        return nullptr;
    PyObject* hit = PyDict_GetItemWithError(ctx.memo, key); // borrowed
    if (hit != nullptr)
    {
        Py_INCREF(hit);
        Py_DECREF(key);
        return hit;
    }
    if (PyErr_Occurred())
    {
        Py_DECREF(key);
        return nullptr;
    }
    PyObject* result = PyObject_CallFunctionObjArgs(ctx.coerce, key, nullptr);
    if (result != nullptr && PyDict_Size(ctx.memo) < SCALAR_MEMO_LIMIT)
        PyDict_SetItem(ctx.memo, key, result);
    Py_DECREF(key);
    return result;
}

// ---------------------------------------------------------------- tree walk

PyObject* walkNode(WalkContext& ctx, ryml::id_type node)
{
    const ryml::Tree& tree = *ctx.tree;

    if (tree.is_seq(node))
    {
        if (Py_EnterRecursiveCall(" while building YAML tree"))
            return nullptr;
        PyObject* list = PyList_New(0);
        if (list != nullptr)
        {
            for (ryml::id_type child = tree.first_child(node); child != ryml::NONE;
                    child = tree.next_sibling(child))
            {
                PyObject* item = walkNode(ctx, child);
                if (item == nullptr || PyList_Append(list, item) < 0)
                {
                    Py_XDECREF(item);
                    Py_DECREF(list);
                    list = nullptr;
                    break;
                }
                Py_DECREF(item);
            }
        }
        Py_LeaveRecursiveCall();
        return list;
    }

    if (tree.is_map(node))
    {
        if (Py_EnterRecursiveCall(" while building YAML tree"))
            return nullptr;
        PyObject* dict = PyDict_New();
        if (dict != nullptr)
        {
            for (ryml::id_type child = tree.first_child(node); child != ryml::NONE;
                    child = tree.next_sibling(child))
            {
                PyObject* key;
                const c4::csubstr keyStr = tree.has_key(child) ? tree.key(child) : c4::csubstr{};
                if (tree.has_key(child) && tree.is_key_quoted(child))
                    key = makeString(keyStr);
                else if (keyStr.len > 0)
                    key = coercePlainScalar(ctx, keyStr);
                else
                {
                    key = Py_None;
                    Py_INCREF(key);
                }
                PyObject* value = (key != nullptr) ? walkNode(ctx, child) : nullptr;
                if (key == nullptr || value == nullptr || PyDict_SetItem(dict, key, value) < 0)
                {
                    Py_XDECREF(key);
                    Py_XDECREF(value);
                    Py_DECREF(dict);
                    dict = nullptr;
                    break;
                }
                Py_DECREF(key);
                Py_DECREF(value);
            }
        }
        Py_LeaveRecursiveCall();
        return dict;
    }

    if (tree.has_val(node))
    {
        const c4::csubstr value = tree.val(node);
        if (tree.is_val_quoted(node))
            return makeString(value);
        return coercePlainScalar(ctx, value);
    }

    Py_RETURN_NONE;
}

// ---------------------------------------------------------------- entry point

PyObject* load(PyObject*, PyObject* const* args, Py_ssize_t nargs)
{
    if (nargs != 2)
    {
        PyErr_SetString(PyExc_TypeError, "zs_yaml_native: load expects (data, coerce_callback)!");
        return nullptr;
    }

    const char* data = nullptr;
    Py_ssize_t size = 0;
    if (PyBytes_Check(args[0]))
    {
        if (PyBytes_AsStringAndSize(args[0], const_cast<char**>(&data), &size) < 0)
            return nullptr;
    }
    else if (PyUnicode_Check(args[0]))
    {
        data = PyUnicode_AsUTF8AndSize(args[0], &size);
        if (data == nullptr)
            return nullptr;
    }
    else
    {
        PyErr_SetString(PyExc_TypeError, "zs_yaml_native: load expects str or bytes data!");
        return nullptr;
    }
    if (!PyCallable_Check(args[1]))
    {
        PyErr_SetString(PyExc_TypeError, "zs_yaml_native: coerce callback must be callable!");
        return nullptr;
    }

    // parse_in_place on our own mutable copy: the tree then references the
    // buffer directly (no second arena copy of a multi-hundred-MB document)
    std::string buffer;
    ryml::Tree tree;
    bool parsed = false;
    std::string errorMessage;
    Py_BEGIN_ALLOW_THREADS
    try
    {
        buffer.assign(data, static_cast<size_t>(size));
        tree = ryml::parse_in_place(c4::substr(buffer.data(), buffer.size()));
        parsed = true;
    }
    catch (const std::exception& excpt)
    {
        errorMessage = excpt.what();
    }
    Py_END_ALLOW_THREADS
    if (!parsed)
    {
        PyErr_SetString(PyExc_ValueError, errorMessage.c_str());
        return nullptr;
    }

    PyObject* memo = PyDict_New();
    if (memo == nullptr)
        return nullptr;
    WalkContext ctx{&tree, args[1], memo};
    PyObject* result = nullptr;
    try
    {
        result = walkNode(ctx, tree.root_id());
    }
    catch (const std::exception& excpt)
    {
        PyErr_SetString(PyExc_ValueError, excpt.what());
        result = nullptr;
    }
    Py_DECREF(memo);
    return result;
}

typedef PyObject* (*FastFunction)(PyObject*, PyObject* const*, Py_ssize_t);

PyMethodDef moduleMethods[] = {
        {"load", reinterpret_cast<PyCFunction>(reinterpret_cast<FastFunction>(load)),
                METH_FASTCALL,
                "load(data, coerce_callback) -> python tree (dicts/lists/scalars)"},
        {nullptr, nullptr, 0, nullptr}};

PyModuleDef moduleDef = {
        PyModuleDef_HEAD_INIT,
        "zs_yaml_native", // m_name
        "C-level rapidyaml-backed YAML loader for zs-yaml", // m_doc
        -1, // m_size
        moduleMethods, // m_methods
        nullptr, nullptr, nullptr, nullptr};

} // namespace

PyMODINIT_FUNC PyInit_zs_yaml_native()
{
    ryml::Callbacks callbacks;
    callbacks.set_error_basic(onErrorBasic);
    callbacks.set_error_parse(onErrorParse);
    callbacks.set_error_visit(onErrorVisit);
    ryml::set_callbacks(callbacks);

    return PyModule_Create(&moduleDef);
}
