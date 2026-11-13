"""Pinned REDnote 9.48.1 discovery-feed display patch; original bind stays intact."""

import hashlib
import re
from pathlib import Path
import struct
import sys
import zipfile

ADAPTER = "com.xingin.xhs.homepage.explorefeed.mainfeed.view.FeedCustomMultiTypeAdapter"
DESCRIPTOR = "L" + ADAPTER.replace(".", "/") + ";"
PROTO = "(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;ILjava/util/List;)V"
HELPER = "Ldev/kiri/xhsads/FeedAdDisplay;"
# Pinned sha256 of the discovery-feed bind method in REDnote 9.54.0 (9540804),
# APKEditor 1.4.9 / jf decode. Recompute for a new base build.
EXPECTED_METHOD_SHA = "caad7d83ccf094a6109a0898c1b57c79f5f9c705a51771f5060da810a0d050cf"
SUPER_BIND = "    invoke-super {p0, p1, p2, p3}, Lcom/drakeet/multitype/MultiTypeAdapter;->onBindViewHolder" + PROTO
# Obfuscated per build: 9.48.1 exposed the item list as ``B0()``, 9.54.0 as ``A0()``.
ITEMS_ACCESSOR = "A0"

RESTORE = """    # rednote-feed-ad-restore-before-bind
    iget-object v0, p1, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;->itemView:Landroid/view/View;
    const/4 v1, 0x0
    invoke-static {v0, v1}, Ldev/kiri/xhsads/FeedAdDisplay;->apply(Landroid/view/View;Z)V

"""

HIDE = (
    "\n\n    # rednote-feed-ad-hide-after-bind\n"
    "    invoke-virtual {p0}, Lcom/drakeet/multitype/MultiTypeAdapter;->"
    + ITEMS_ACCESSOR
    + "()Ljava/util/List;\n"
    "    move-result-object v1\n"
    "    invoke-interface {v1, p2}, Ljava/util/List;->get(I)Ljava/lang/Object;\n"
    "    move-result-object v1\n"
    "    move-object v2, v1\n"
    "    iget-object v0, p1, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;->"
    "itemView:Landroid/view/View;\n"
    "    invoke-static {v0, v1}, Ldev/kiri/xhsads/FeedInspector;->"
    "onBind(Landroid/view/View;Ljava/lang/Object;)V\n"
    "    invoke-static {v1}, Ldev/kiri/xhsads/FeedAdDetector;->isAd(Ljava/lang/Object;)Z\n"
    "    move-result v1\n"
    "\n"
    "    :rednote_feed_ad_apply\n"
    "    iget-object v0, p1, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;->"
    "itemView:Landroid/view/View;\n"
    "    invoke-static {v0, v1}, Ldev/kiri/xhsads/FeedAdDisplay;->"
    "apply(Landroid/view/View;Z)V\n"
)


def patch_feed_bind(smali_path: Path) -> dict:
    text = smali_path.read_text()
    pattern = r"^\.method public onBindViewHolder" + re.escape(PROTO) + r"\n.*?^\.end method"
    methods = list(re.finditer(pattern, text, re.M | re.S))
    if len(methods) != 1:
        raise ValueError("Expected exactly one discovery-feed payload bind method")
    match = methods[0]
    original = match.group()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED_METHOD_SHA:
        raise ValueError("Feed bind method differs from the verified REDnote input")
    if original.count(SUPER_BIND) != 1 or "    .locals 4\n" not in original:
        raise ValueError("Unexpected feed bind register or superclass layout")
    patched = original.replace(SUPER_BIND, RESTORE + SUPER_BIND + HIDE)
    smali_path.write_text(text[:match.start()] + patched + text[match.end():])
    return {
        "adapterClass": ADAPTER,
        "method": "onBindViewHolder" + PROTO,
        "originalMethodSha256": EXPECTED_METHOD_SHA,
        "originalBindPreserved": True,
        "restoreBeforeBind": True,
        "hideAfterBind": True,
        "predicate": "FeedAdDetector reads isAd/isShowAdTips/adsInfo by name on com.xingin.entities items, and treats AdsInfo items and com.xingin.advert.* items as ads",
        "scope": "Discovery/home feed cards using FeedCustomMultiTypeAdapter; requests and feed items are unchanged",
    }


def verify_compiled_feed_patch(apk: Path) -> dict:
    # Reuse the independent DEX parser used for production signature verification.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile
    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read("classes19.dex"), "classes19.dex")
    definitions = dex.class_definitions(DESCRIPTOR)
    if len(definitions) != 1:
        raise ValueError("Expected one feed adapter in classes19.dex")
    records = dex.method_records(definitions[0])
    matches = [(index, code) for index, _, code in records
               if dex.method_id(index) == (DESCRIPTOR, "onBindViewHolder", PROTO)]
    if len(matches) != 1:
        raise ValueError("Expected one compiled feed bind")
    _, code = matches[0]
    _, count = dex.code_info(code)
    units = list(struct.unpack_from("<" + "H" * count, dex.data, code + 16))
    calls, fields, types = [], [], []
    position = 0
    while position < len(units):
        opcode = units[position] & 0xff
        if opcode in range(0x6e, 0x73) or opcode in range(0x74, 0x79):
            calls.append((opcode, dex.method_id(units[position + 1])))
        elif opcode == 0x55:  # iget-boolean
            fields.append(dex.field_id(units[position + 1]))
        elif opcode == 0x20:  # instance-of
            types.append(dex.type_descriptor(units[position + 1]))
        position += dex._instruction_width(units, position)
    helper_call = (HELPER, "apply", "(Landroid/view/View;Z)V")
    detector_call = ("Ldev/kiri/xhsads/FeedAdDetector;", "isAd", "(Ljava/lang/Object;)Z")
    inspector_call = ("Ldev/kiri/xhsads/FeedInspector;", "onBind",
                      "(Landroid/view/View;Ljava/lang/Object;)V")
    parent_call = ("Lcom/drakeet/multitype/MultiTypeAdapter;", "onBindViewHolder", PROTO)
    helper_positions = [i for i, (_, method) in enumerate(calls) if method == helper_call]
    super_positions = [i for i, (op, method) in enumerate(calls) if op in (0x6f, 0x75) and method == parent_call]
    if len(helper_positions) != 2 or len(super_positions) != 1:
        raise ValueError("Compiled feed hook must have two helper calls and one original superclass bind")
    if not helper_positions[0] < super_positions[0] < helper_positions[1]:
        raise ValueError("Compiled restore/bind/hide order is incorrect")
    detector_positions = [i for i, (_, method) in enumerate(calls) if method == detector_call]
    if len(detector_positions) != 1:
        raise ValueError("Compiled feed hook must call FeedAdDetector exactly once")
    inspector_positions = [i for i, (_, method) in enumerate(calls) if method == inspector_call]
    if len(inspector_positions) != 1:
        raise ValueError("Compiled feed hook must call FeedInspector exactly once")
    if not super_positions[0] < inspector_positions[0] < detector_positions[0] < helper_positions[1]:
        raise ValueError("Compiled bind/inspect/detect/hide order is incorrect")
    return {"verified": True, "dex": "classes19.dex", "adapter": ADAPTER,
            "originalBindRetained": True, "restoreBindHideOrder": True,
            "adDetectorCall": True, "debugInspectorCall": True}
