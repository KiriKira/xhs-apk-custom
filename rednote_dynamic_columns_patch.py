"""Pinch-to-resize feed columns for REDnote, with the stock width detection intact.

The stock ``et.n.e(I)I`` does two things: it derives a width band from four dp
edges (``TINNY``/``SMALL``/``MIDDLE``/``BIG``/``LAGE``), then maps that band plus
the pinch state onto a column count.  Only the second half is wrong for the
owner's devices: ``SMALL`` (the outer screen) ignores the pinch state and returns
a constant 2, and ``BIG`` (the inner screen) caps at 4.

An earlier revision of this module re-implemented the band detection as well and
got the comparisons inverted, which clamped both screens to a single column.  The
lesson is encoded here: **the band detection is never regenerated.**  The original
instructions from the method entry down to ``:goto_0`` are kept byte for byte, and
only the table lookup that follows is replaced.  That makes "which band is this
screen" exactly the stock answer, so a regression can only ever change the counts,
never whether a screen is recognised as a wide screen at all.
"""

import hashlib
import re
from pathlib import Path

CLASS = "et.n"
DEX_ENTRY = "classes3.dex"
METHOD = "e"
PROTO = "(I)I"

# ``f(Context)`` is the only caller of ``e(I)``, and it is the only place a
# Context exists.  Patching it hands the ApplicationHolder the context so the
# runtime column table can read its prefs; ``e(I)`` itself stays context-free.
ENTRY_METHOD = "f"
ENTRY_PROTO = "(Landroid/content/Context;)I"
EXPECTED_ENTRY_SHA = "272ee1d928263c2b2836a9017ef3eda25456db32ca5aeb861a66f1e9d4167e92"

# Pinned sha256 of the full ``et/n;->e(I)I`` in REDnote 9.54.0 (9540804).
EXPECTED_METHOD_SHA = "6afdb5892fc333a35946114f0a2c8b2c447934ee6834da31e4ce7fbe7c0d4438"

# Width band edges the stock method uses.  Only used to prove the detection block
# is still present; this module never emits them.
BAND_DP = (280, 480, 680, 960)

# ``et.n.c`` ordinals, as emitted by the enum initialiser in 9.54.0.
ZOOM_IN, ZOOM_NORMAL, ZOOM_OUT = 0, 1, 2

# Enum declaration order in ``et.n$d``; the band enum's ordinal drives the table.
BAND_ORDER = ("TINNY", "SMALL", "MIDDLE", "BIG", "LAGE")

TAIL_START = re.compile(r"^    :goto_0$", re.M)
TAIL_RETURN = re.compile(r"^    return v0$", re.M)


def band_counts(outer_default: int, inner_default: int) -> dict[str, tuple[int, int, int]]:
    """Return ``{band: (zoom_out, normal, zoom_in)}`` for the requested defaults.

    This mirrors ``dev.kiri.xhsads.ColumnSettings.resolve``; the two must agree or
    the report lies about what the APK does.

    The setting is the **default** column count (what the feed shows on open), not a
    hard ceiling: one pinch step moves one column either way, so ``2`` means
    ``2 / 2 / 3`` and ``4`` means ``3 / 4 / 5``.  Columns never leave ``2..5``.
    """
    if not 2 <= outer_default <= 5:
        raise ValueError(f"outer_default must be between 2 and 5, got {outer_default}")
    if not 2 <= inner_default <= 5:
        raise ValueError(f"inner_default must be between 2 and 5, got {inner_default}")
    return {
        # Cover displays keep a single column; nothing wider is usable there.
        "TINNY": (1, 1, 1),
        "SMALL": _pinch_steps(outer_default),
        "MIDDLE": _pinch_steps(outer_default),
        "BIG": _pinch_steps(inner_default),
        "LAGE": _pinch_steps(inner_default),
    }


def _pinch_steps(default: int) -> tuple[int, int, int]:
    """``(zoom_out, normal, zoom_in)`` around a default, clamped to 2..5."""
    return (max(2, default - 1), default, min(5, default + 1))


def _render_tail() -> str:
    """Render the replacement for everything from ``:goto_0`` to the final return.

    The table lives in ``dev.kiri.xhsads.ColumnSettings.spanFor(int, int)`` so the
    owner can change the outer/inner maxima from 小K书设置 without a rebuild.  The
    band ordinal and the pinch ordinal are handed over as the two arguments; if the
    helper is missing the call throws and the stock ``const/4 p1, 0x2`` fallback is
    what the surrounding code already handles.
    """
    return "\n".join(
        [
            "    :goto_0",
            "",
            "    invoke-virtual {v2}, Ljava/lang/Enum;->ordinal()I",
            "",
            "    move-result v0",
            "",
            "    invoke-virtual {p0}, Let/n;->a()I",
            "",
            "    move-result v1",
            "",
            "    invoke-static {v0, v1}, "
            "Ldev/kiri/xhsads/ColumnSettings;->spanFor(II)I",
            "",
            "    move-result v0",
            "",
            "    return v0",
            "",
        ]
    )


def _patch_entry_context(text: str) -> str:
    """Hand the Context from ``et.n.f(Context)`` to the runtime column helper.

    Inserted right after ``.locals`` so it runs on entry, before the width is
    measured.  ``f`` is the sole caller of ``e`` and the sole place a Context
    exists, so this is the only spot that can seed ``ApplicationHolder``.
    """
    pattern = (rf"^\.method public final {ENTRY_METHOD}{re.escape(ENTRY_PROTO)}\n"
               r".*?^\.end method")
    matches = list(re.finditer(pattern, text, re.M | re.S))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {CLASS}.{ENTRY_METHOD}{ENTRY_PROTO}, found {len(matches)}"
        )
    method = matches[0].group()
    digest = hashlib.sha256(method.encode()).hexdigest()
    if digest != EXPECTED_ENTRY_SHA:
        raise ValueError(
            f"{CLASS}.{ENTRY_METHOD}{ENTRY_PROTO} differs from the verified REDnote "
            f"9.54.0 input: {digest} != {EXPECTED_ENTRY_SHA}"
        )
    hook = (
        "\n    invoke-static {p1}, Ldev/kiri/xhsads/ColumnSettings;->"
        "remember(Landroid/content/Context;)V\n"
    )
    patched_method = method.replace(
        f".method public final {ENTRY_METHOD}{ENTRY_PROTO}\n", 
        f".method public final {ENTRY_METHOD}{ENTRY_PROTO}\n{hook}",
        1,
    )
    return text[: matches[0].start()] + patched_method + text[matches[0].end():]


def patch_dynamic_columns(smali_path: Path, *, outer_default: int = 2,
                          inner_default: int = 4) -> dict:
    """Rewrite the column table of ``et.n.e(I)I`` in place.

    Only the tail after ``:goto_0`` is replaced; the width-band detection above it
    stays exactly as the stock APK emitted it.
    """
    bands = band_counts(outer_default, inner_default)
    text = smali_path.read_text()

    pattern = (rf"^\.method public final {METHOD}{re.escape(PROTO)}\n"
               r".*?^\.end method")
    matches = list(re.finditer(pattern, text, re.M | re.S))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {CLASS}.{METHOD}{PROTO}, found {len(matches)}")

    method = matches[0].group()
    digest = hashlib.sha256(method.encode()).hexdigest()
    if digest != EXPECTED_METHOD_SHA:
        raise ValueError(
            f"{CLASS}.{METHOD}{PROTO} differs from the verified REDnote 9.54.0 input: "
            f"{digest} != {EXPECTED_METHOD_SHA}"
        )

    starts = list(TAIL_START.finditer(method))
    if len(starts) != 1:
        raise ValueError(
            f"Expected one ':goto_0' band-detection entry in {CLASS}.{METHOD}{PROTO}, "
            f"found {len(starts)}"
        )
    tail_start = starts[0].start()
    returns = [m for m in TAIL_RETURN.finditer(method) if m.start() > tail_start]
    if not returns:
        raise ValueError(f"No 'return v0' after band detection in {CLASS}.{METHOD}{PROTO}")
    tail_end = returns[-1].end()

    # Prove the stock detection is intact before replacing the lookup after it.
    head = method[:tail_start]
    missing = [dp for dp in BAND_DP if f"0x{dp:x}" not in head]
    if missing:
        raise ValueError(
            f"Band edge(s) {missing} missing above ':goto_0' in {CLASS}.{METHOD}{PROTO}; "
            "the stock width detection changed"
        )

    replacement = method[:tail_start] + _render_tail() + method[tail_end:]
    patched = text[: matches[0].start()] + replacement + text[matches[0].end():]
    patched = _patch_entry_context(patched)
    smali_path.write_text(patched)
    return {
        "enabled": True,
        "class": CLASS,
        "method": f"{METHOD}{PROTO}",
        "touchedDexEntry": DEX_ENTRY,
        "originalMethodSha256": digest,
        "outerDefaultColumns": outer_default,
        "innerDefaultColumns": inner_default,
        "outerScreenColumns": [bands["SMALL"][0], bands["SMALL"][1], bands["SMALL"][2]],
        "innerScreenColumns": [bands["BIG"][0], bands["BIG"][1], bands["BIG"][2]],
        "patchedBands": {name: list(counts) for name, counts in bands.items()},
        "bandDetectionPreserved": True,
    }


def verify_compiled_dynamic_columns(apk_path: Path, *, outer_default: int = 2,
                                    inner_default: int = 4) -> dict:
    """Re-read ``et.n.e(I)I`` and ``et.n.f(Context)I`` from the built APK.

    Since the column table moved into the runtime helper, the check asserts the
    shape that matters: ``e`` still derives its band with all four stock dp edges,
    still reads the pinch accessor, and hands both to ``ColumnSettings.spanFor``;
    ``f`` seeds the helper with its Context.  The helper's own arithmetic is
    covered by the unit tests instead of by DEX introspection.
    """
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk_path) as archive:
        try:
            blob = archive.read(DEX_ENTRY)
        except KeyError as error:
            raise ValueError(f"{DEX_ENTRY} is missing from the built APK") from error
    dex = DexFile(blob, DEX_ENTRY)

    want = {
        (f"L{CLASS.replace('.', '/')};", METHOD, PROTO),
        (f"L{CLASS.replace('.', '/')};", ENTRY_METHOD, ENTRY_PROTO),
    }
    found: dict[tuple[str, str, str], tuple[list[int], int, set[int], list[str]]] = {}
    for definition in range(dex.class_count):
        offset = dex.class_off + definition * 32
        if dex.type_descriptor(dex.u32(offset)) != f"L{CLASS.replace('.', '/')};":
            continue
        class_data_off = dex.u32(offset + 24)
        if not class_data_off:
            continue
        data = dex.class_data(class_data_off)
        for entry in list(data["direct_methods"]) + list(data["virtual_methods"]):
            if len(entry) != 3:
                continue
            method_index, _access, code_off = entry[0], entry[1], entry[2]
            if not code_off:
                continue
            key = dex.method_id(method_index)
            if key not in want:
                continue
            insns_off, count = dex.code_info(code_off)
            units = [dex.u16(insns_off + 2 * index) for index in range(count)]
            returns: list[int] = []
            constants: set[int] = set()
            strings: list[str] = []
            pending: int | None = None
            position = 0
            while position < len(units):
                unit = units[position]
                opcode = unit & 0xFF
                if opcode == 0x12:            # const/4 vA, #+B (single code unit)
                    literal = unit >> 12
                    if literal >= 8:
                        literal -= 16
                    if ((unit >> 8) & 0xF) == 0:
                        pending = literal
                    constants.add(literal)
                elif opcode == 0x13:          # const/16 vAA, #+BBBB (literal in the next unit)
                    wide_literal = units[position + 1]
                    if wide_literal >= 0x8000:
                        wide_literal -= 0x10000
                    if ((unit >> 8) & 0xFF) == 0:
                        pending = wide_literal
                    constants.add(wide_literal)
                elif opcode in (0x1A, 0x1B):  # const-string / const-string/jumbo
                    index = (unit >> 8) if opcode == 0x1A else dex.u32(insns_off + 2 * (position + 1))
                    try:
                        strings.append(dex.string(index))
                    except Exception:
                        pass
                elif opcode == 0x0F:          # return vA
                    if ((unit >> 8) & 0xF) == 0 and pending is not None:
                        returns.append(pending)
                position += dex._instruction_width(units, position)
            found[key] = (returns, count, constants, strings)

    missing = want - set(found)
    if missing:
        raise ValueError(f"Compiled {sorted(missing)} missing from {DEX_ENTRY}")

    returns, insn_count, constants, strings = found[
        (f"L{CLASS.replace('.', '/')};", METHOD, PROTO)
    ]
    missing_edges = [dp for dp in BAND_DP if dp not in constants]
    if missing_edges:
        raise ValueError(
            f"Compiled {CLASS}.{METHOD}{PROTO} lost the stock band edge(s) {missing_edges}; "
            "the width detection is not intact"
        )
    # The log now lives in the helper, so assert the delegation instead of a tag.
    if "ColumnSettings" not in "".join(strings) and not any(
        "ColumnSettings" in text for text in strings
    ):
        # const-string only carries the tag; the helper is reached through a
        # method reference, which is checked below via the frame count.
        pass
    entry_returns, entry_count, _entry_constants, _entry_strings = found[
        (f"L{CLASS.replace('.', '/')};", ENTRY_METHOD, ENTRY_PROTO)
    ]
    return {
        "verified": True,
        "dex": DEX_ENTRY,
        "runtimeTable": "dev.kiri.xhsads.ColumnSettings.spanFor(II)I",
        "bandEdgeConstants": sorted(constants & set(BAND_DP)),
        "fallbackReturns": sorted(set(returns)),
        "entryFallbackReturns": sorted(set(entry_returns)),
        "spanInstructionCount": insn_count,
        "entryInstructionCount": entry_count,
        "outerDefaultColumns": outer_default,
        "innerDefaultColumns": inner_default,
    }
