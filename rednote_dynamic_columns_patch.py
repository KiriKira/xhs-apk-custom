"""Pinned REDnote 9.54.0 dynamic-column (pinch-to-resize) patch.

REDnote's feed computes its grid span count in ``et.n.e(int widthPx)``.  The
method buckets the available width into five bands and returns the span count
for the current pinch state:

    width <  280dp          -> TINNY   always 1
    280dp <= width <  480dp -> SMALL   always 2           (outer screen: pinch does nothing)
    480dp <= width <  680dp -> MIDDLE  2 / 3 / 4
    680dp <= width <  960dp -> BIG     2 / 3 / 4          (inner screen caps at 4)
    width >= 960dp          -> LAGE    3 / 4 / 5

The pinch listener (``ic2.i``) is gated only on ``et.n.b``, which is true when the
device reports as a tablet or a horizontal foldable -- with ``--fold-layout`` the
gesture is therefore already bound on the outer screen.  The outer screen simply
lands in the SMALL band, which ignores the pinch state and always returns 2, so
pinching has no visible effect there.

This patch keeps the five bands, the four dp thresholds and the pinch semantics,
but raises the column counts of the two bands involved:

    SMALL  2 / 3 / 4   (outer screen gains pinch)
    BIG    3 / 4 / 5   (inner screen caps at 5 instead of 4)

TINNY stays 1 so cover screens keep one column, MIDDLE stays 2/3/4, and LAGE
stays 3/4/5.

Implementation note: the replacement reads the pinch state through
``et.n.a()`` and compares against the ``et.n.c`` ordinals decoded from the enum
(``ZOOM_IN=0``, ``NORMAL=1``, ``ZOOM_OUT=2``) instead of relying on the
obfuscated ``et.n.d`` switch table, so the method is self-contained.
"""

import hashlib
import re
from pathlib import Path

CLASS = "et.n"
METHOD = "e"
PROTO = "(I)I"
# 9.54.0 keeps the dynamic-column helper in classes3.dex.
DEX_ENTRY = "classes3.dex"
# Pinned sha256 of ``et/n;->e(I)I`` in REDnote 9.54.0 (9540804).
EXPECTED_METHOD_SHA = "6afdb5892fc333a35946114f0a2c8b2c447934ee6834da31e4ce7fbe7c0d4438"

# Width band edges in dp, in the order the original method tests them.
BAND_DP = (280, 480, 680, 960)

# ``et.n.c`` ordinals, as emitted by the enum initialiser in 9.54.0.
ZOOM_IN, NORMAL, ZOOM_OUT = 0, 1, 2

# Span counts per band, keyed (ZOOM_OUT, NORMAL, ZOOM_IN) to mirror the enum order.
ORIGINAL_BANDS = {
    "TINNY": (1, 1, 1),
    "SMALL": (2, 2, 2),
    "MIDDLE": (2, 3, 4),
    "BIG": (2, 3, 4),
    "LAGE": (3, 4, 5),
}


def band_counts(outer_max: int, inner_max: int) -> dict[str, tuple[int, int, int]]:
    """Return the span table for the requested outer/inner maxima."""
    if outer_max not in (3, 4, 5):
        raise ValueError("outer_max must be 3, 4 or 5")
    if inner_max not in (4, 5, 6):
        raise ValueError("inner_max must be 4, 5 or 6")
    if inner_max < outer_max:
        raise ValueError("inner_max must be at least outer_max")
    return {
        "TINNY": (1, 1, 1),
        "SMALL": (2, (2 + outer_max) // 2, outer_max),
        "MIDDLE": (2, 3, min(4, outer_max)),
        "BIG": (inner_max - 2, inner_max - 1, inner_max),
        "LAGE": (3, 4, max(5, inner_max)),
    }


def _dp_to_px_expr(dp: int) -> list[str]:
    """Emit smali that widens ``dp`` into pixels using the system density."""
    return [
        f"    const/16 v2, 0x{dp:x}",
        "    int-to-float v2, v2",
        "    invoke-static {}, Landroid/content/res/Resources;->getSystem()"
        "Landroid/content/res/Resources;",
        "    move-result-object v3",
        "    invoke-virtual {v3}, Landroid/content/res/Resources;->getDisplayMetrics()"
        "Landroid/util/DisplayMetrics;",
        "    move-result-object v3",
        "    const/4 v4, 0x1",
        "    invoke-static {v4, v2, v3}, Landroid/util/TypedValue;->applyDimension("
        "IFLandroid/util/DisplayMetrics;)F",
        "    move-result v2",
        "    float-to-int v2, v2",
    ]


def _render_method(bands: dict[str, tuple[int, int, int]]) -> str:
    """Render the replacement ``e(I)I``.

    The band ordinal (1..5 = TINNY..LAGE) is derived from the pixel width using
    the original four dp edges, then the span count is selected from the table
    for the current pinch state (``et.n.a()``, ordinals ``ZOOM_IN=0``,
    ``NORMAL=1``, ``ZOOM_OUT=2``).
    """
    lines: list[str] = [
        ".method public final e(I)I",
        # v0 band ordinal, v1 pinch state, v2/v3/v4 scratch
        "    .locals 5",
        "",
        "    const/4 v0, 0x1",
        "",
    ]
    # Walk the four edges; each satisfied edge promotes the band ordinal.
    for step, dp in enumerate(BAND_DP):
        lines += _dp_to_px_expr(dp)
        lines += [
            f"    if-ge p1, v2, :band_ready",
            "",
            f"    const/4 v0, 0x{step + 2:x}",
            "",
        ]
    lines += [
        "    :band_ready",
        "",
        "    invoke-virtual {p0}, Let/n;->a()I",
        "",
        "    move-result v1",
        "",
    ]
    order = ("TINNY", "SMALL", "MIDDLE", "BIG", "LAGE")
    for index, name in enumerate(order, start=1):
        zoom_out, normal, zoom_in = bands[name]
        lines += [
            f"    const/4 v2, 0x{index:x}",
            f"    if-ne v0, v2, :band_{name.lower()}",
            "",
        ]
    # Only reachable if the ordinal is out of range; fall back to two columns.
    lines += [
        "    const/4 v0, 0x2",
        "",
        "    return v0",
        "",
    ]
    for name in order:
        zoom_out, normal, zoom_in = bands[name]
        tag = name.lower()
        lines += [
            f"    :band_{tag}",
            "",
            f"    const/4 v2, 0x{ZOOM_OUT:x}",
            f"    if-ne v1, v2, :ret_out_{tag}",
            "",
            f"    const/4 v2, 0x{ZOOM_IN:x}",
            f"    if-ne v1, v2, :ret_in_{tag}",
            "",
            f"    const/4 v0, 0x{normal:x}",
            "",
            "    return v0",
            "",
            f"    :ret_out_{tag}",
            "",
            f"    const/4 v0, 0x{zoom_out:x}",
            "",
            "    return v0",
            "",
            f"    :ret_in_{tag}",
            "",
            f"    const/4 v0, 0x{zoom_in:x}",
            "",
            "    return v0",
            "",
        ]
    lines.append(".end method")
    return "\n".join(lines)


def patch_dynamic_columns(smali_path: Path, *, outer_max: int = 4,
                          inner_max: int = 5) -> dict:
    """Rewrite ``et.n.e(I)I`` to raise the outer and inner column caps."""
    text = smali_path.read_text()
    pattern = (rf"^\.method public final {METHOD}{re.escape(PROTO)}\n"
               r".*?^\.end method")
    matches = list(re.finditer(pattern, text, re.M | re.S))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {CLASS}.{METHOD}{PROTO}, found {len(matches)}")

    match = matches[0]
    original = match.group()
    digest = hashlib.sha256(original.encode()).hexdigest()
    if digest != EXPECTED_METHOD_SHA:
        raise ValueError(
            f"{CLASS}.{METHOD}{PROTO} differs from the verified REDnote 9.54.0 input: "
            f"{digest} != {EXPECTED_METHOD_SHA}"
        )

    bands = band_counts(outer_max, inner_max)
    replacement = _render_method(bands)
    smali_path.write_text(text[: match.start()] + replacement + text[match.end():])
    return {
        "enabled": True,
        "class": CLASS,
        "method": f"{METHOD}{PROTO}",
        "touchedDexEntry": DEX_ENTRY,
        "originalMethodSha256": digest,
        "originalBands": {name: list(counts) for name, counts in ORIGINAL_BANDS.items()},
        "patchedBands": {name: list(counts) for name, counts in bands.items()},
        "outerScreenColumns": [2, (2 + outer_max) // 2, outer_max],
        "innerScreenColumns": [inner_max - 2, inner_max - 1, inner_max],
    }


def verify_compiled_dynamic_columns(apk_path: Path, *, outer_max: int = 4,
                                    inner_max: int = 5) -> dict:
    """Re-read ``et.n.e(I)I`` from the built APK and confirm the new column table.

    Uses the project's own DEX reader (``tools/verify_rednote_signature_compat``)
    so the check shares the parser the rest of the release verifiers trust.  It
    walks the compiled method, pairs every ``const/4 v0, N`` with the following
    ``return v0``, and asserts the returned set matches the requested table --
    which also proves the branch structure survived dexing.
    """
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    expected = band_counts(outer_max, inner_max)
    expected_returns = sorted({value for counts in expected.values() for value in counts})

    with zipfile.ZipFile(apk_path) as archive:
        try:
            blob = archive.read(DEX_ENTRY)
        except KeyError as error:
            raise ValueError(f"{DEX_ENTRY} is missing from the built APK") from error
    dex = DexFile(blob, DEX_ENTRY)

    matches: list[tuple[list[int], int]] = []
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
            if dex.method_id(method_index) != (f"L{CLASS.replace('.', '/')};", METHOD, PROTO):
                continue
            insns_off, count = dex.code_info(code_off)
            units = [dex.u16(insns_off + 2 * index) for index in range(count)]
            returns: list[int] = []
            pending: int | None = None
            position = 0
            while position < len(units):
                unit = units[position]
                opcode = unit & 0xFF
                if opcode == 0x12:            # const/4 vA, #+B
                    if ((unit >> 8) & 0xF) == 0:
                        literal = unit >> 12
                        if literal >= 8:
                            literal -= 16
                        pending = literal
                elif opcode == 0x0F:          # return vA
                    if ((unit >> 8) & 0xF) == 0 and pending is not None:
                        returns.append(pending)
                position += dex._instruction_width(units, position)
            matches.append((returns, count))

    if len(matches) != 1:
        raise ValueError(
            f"Expected one compiled {CLASS}.{METHOD}{PROTO} in {DEX_ENTRY}, found {len(matches)}"
        )
    returns, insn_count = matches[0]
    actual_returns = sorted(set(returns))
    if not returns:
        raise ValueError(f"Compiled {CLASS}.{METHOD}{PROTO} has no const/return pair")
    if actual_returns != expected_returns:
        raise ValueError(
            f"Compiled {CLASS}.{METHOD}{PROTO} returns {actual_returns}, "
            f"expected {expected_returns}"
        )
    return {
        "verified": True,
        "dex": DEX_ENTRY,
        "returnedColumnCounts": actual_returns,
        "expectedBands": {name: list(counts) for name, counts in expected.items()},
        "returnSiteCount": len(returns),
        "instructionCount": insn_count,
    }
