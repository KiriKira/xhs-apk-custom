"""Verify the release preserves the source main-process name comparison.

The gate no longer lives in a fixed class: 9.48.1 stored the process name in
``ddc/b.b`` and compared it in ``ddc/a.invoke()``; 9.54.0 resolves a process-type
enum inside an obfuscated helper. Both compile the same shape -- load the package
literal, compare it through ``Intrinsics`` -- so the check locates the comparison
by shape instead of by name.

Release builds keep the source application process label, so every app-local
process-name comparison must still name the source package and none may point at
the clone package.
"""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_rednote_signature_compat import DexFile  # noqa: E402

INTRINSICS_TARGETS = {
    ("Lkotlin/jvm/internal/Intrinsics;", "areEqual",
     "(Ljava/lang/Object;Ljava/lang/Object;)Z"),
    ("Lkotlin/jvm/internal/Intrinsics;", "f",
     "(Ljava/lang/Object;Ljava/lang/Object;)Z"),
}
INVOKE_STATIC_OPCODES = (0x71, 0x77)


def _comparisons(dex: DexFile, literals: set[str]) -> list[dict]:
    """Return every package-literal comparison through ``Intrinsics`` in this DEX.

    Instruction widths come from the shared DEX parser so a jumbo string or a wide
    instruction cannot desynchronise the walk.
    """
    hits: list[dict] = []
    for definition in range(dex.class_count):
        offset = dex.class_off + definition * 32
        class_descriptor = dex.type_descriptor(dex.u32(offset))
        class_data = dex.u32(offset + 24)
        if not class_data:
            continue
        data = dex.class_data(class_data)
        methods = list(data["direct_methods"]) + list(data["virtual_methods"])
        for entry in methods:
            if len(entry) != 3:
                continue
            method_index, _access, code = entry[0], entry[1], entry[2]
            if not code:
                continue
            insns_off, count = dex.code_info(code)
            units = [dex.u16(insns_off + 2 * index) for index in range(count)]
            method_id = dex.method_id(method_index)
            position = 0
            while position < len(units):
                opcode = units[position] & 0xFF
                literal = None
                if opcode == 0x1A and position + 1 < len(units):
                    literal = dex.string(units[position + 1])
                elif opcode == 0x1B and position + 2 < len(units):
                    literal = dex.string(units[position + 1] | (units[position + 2] << 16))
                if literal in literals:
                    scan = position
                    limit = min(len(units), position + 16)
                    while scan < limit:
                        inner = units[scan] & 0xFF
                        if inner in INVOKE_STATIC_OPCODES and scan + 1 < len(units):
                            if dex.method_id(units[scan + 1]) in INTRINSICS_TARGETS:
                                hits.append({
                                    "class": class_descriptor,
                                    "method": method_id,
                                    "literal": literal,
                                })
                                break
                        scan += dex._instruction_width(units, scan)
                position += dex._instruction_width(units, position)
    return hits


def verify_process_gate(apk, expected_package, clone_package=None):
    literals = {expected_package}
    if clone_package:
        literals.add(clone_package)

    found: list[dict] = []
    with zipfile.ZipFile(apk) as archive:
        entries = [name for name in archive.namelist()
                   if name.startswith("classes") and name.endswith(".dex")]
        for entry in entries:
            dex = DexFile(archive.read(entry), entry)
            for hit in _comparisons(dex, literals):
                found.append({**hit, "dex": entry})

    source_hits = [item for item in found if item["literal"] == expected_package]
    clone_hits = [item for item in found
                  if clone_package and item["literal"] == clone_package]

    if not source_hits:
        raise ValueError(
            f"No main-process name comparison against {expected_package!r} was found"
        )
    if clone_hits:
        raise ValueError(
            f"{len(clone_hits)} main-process name comparisons were rebased onto "
            f"{clone_package!r}; the release must preserve the source process name"
        )
    return {
        "verified": True,
        "dex": sorted({item["dex"] for item in source_hits}),
        "classes": sorted({item["class"] for item in source_hits}),
        "processNameConstant": expected_package,
        "sourcePackageComparisonCount": len(source_hits),
        "clonePackageComparisonCount": 0,
    }
